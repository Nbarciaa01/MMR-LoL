import asyncio
import os
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from src.lolscout.riot_client import RiotApiError, RiotClient
from src.lolscout import web_app


class WebComplianceTests(unittest.TestCase):
    def test_anonymous_requests_ignore_legacy_viewer_settings(self):
        from starlette.requests import Request
        from starlette.responses import Response

        async def exercise():
            for path in ("/", "/api/config", "/api/ranking", "/api/today", "/api/live"):
                request = Request({"type": "http", "method": "GET", "path": path,
                                   "headers": [], "query_string": b""})
                async def next_handler(request):
                    return Response("ok")
                response = await web_app.security_headers(request, next_handler)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("www-authenticate", response.headers)

        with patch.dict(os.environ, {
            "RENDER": "true", "MMRLOL_ACCESS_MODE": "private",
            "MMRLOL_VIEWER_PASSWORD": "old-password", "RIOT_KEY_TYPE": "development",
        }):
            asyncio.run(exercise())

    def test_anonymous_edits_still_require_admin_token(self):
        with patch.dict(os.environ, {"MMRLOL_ADMIN_TOKEN": "admin"}):
            with self.assertRaises(HTTPException) as error:
                web_app._require_admin(None)
            self.assertEqual(error.exception.status_code, 401)

    def test_riot_failure_does_not_fetch_other_sources(self):
        client = Mock()
        client.fetch_player_ranking.side_effect = RiotApiError("Unavailable")
        with (
            patch.object(web_app, "_players", return_value=[("Player", "EUW")]),
            patch.object(web_app, "_riot_client", return_value=client),
            patch.object(web_app, "_get_cached_response", return_value=None),
            patch.object(web_app, "_set_cached_response"),
        ):
            response = web_app.ranking()
        self.assertFalse(response["players"][0]["ok"])
        self.assertEqual(response["players"][0]["source"], "riot")

    def test_riot_token_is_never_sent_to_other_hosts_or_redirects(self):
        client = RiotClient("test-secret")
        client.session = Mock()
        with self.assertRaises(RiotApiError):
            client._get_json("https://example.com/")
        client.session.get.assert_not_called()
        client.session.get.return_value.status_code = 302
        with self.assertRaises(RiotApiError):
            client._get_json("https://euw1.api.riotgames.com/test")
        self.assertFalse(client.session.get.call_args.kwargs["allow_redirects"])
