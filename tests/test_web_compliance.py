import base64
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from src.lolscout.riot_client import RiotApiError, RiotClient
from src.lolscout.web_access import access_denial
from src.lolscout import web_app


class WebComplianceTests(unittest.TestCase):
    def request(self, authorization=""):
        return SimpleNamespace(
            url=SimpleNamespace(path="/api/ranking"),
            client=SimpleNamespace(host="127.0.0.1"),
            headers={"authorization": authorization},
        )

    def test_hosted_prototype_fails_closed_without_password(self):
        with patch.dict(os.environ, {"RENDER": "true", "MMRLOL_VIEWER_PASSWORD": "", "MMRLOL_ACCESS_MODE": "prototype"}):
            self.assertEqual(access_denial(self.request()).status_code, 503)

    def test_private_password_and_admin_token_are_separate_credentials(self):
        with patch.dict(os.environ, {
            "RENDER": "true", "MMRLOL_ACCESS_MODE": "private",
            "MMRLOL_VIEWER_USER": "mmr", "MMRLOL_VIEWER_PASSWORD": "viewer",
            "MMRLOL_ADMIN_TOKEN": "admin",
        }):
            self.assertEqual(access_denial(self.request()).status_code, 401)
            basic = base64.b64encode(b"mmr:viewer").decode()
            self.assertIsNone(access_denial(self.request("Basic " + basic)))
            self.assertIsNone(access_denial(self.request("Bearer admin")))
            with self.assertRaises(HTTPException):
                web_app._require_admin("Bearer viewer")

    def test_public_access_requires_production_declaration(self):
        with patch.dict(os.environ, {"MMRLOL_ACCESS_MODE": "public", "RIOT_KEY_TYPE": "development"}):
            self.assertEqual(access_denial(self.request()).status_code, 503)
        with patch.dict(os.environ, {"MMRLOL_ACCESS_MODE": "public", "RIOT_KEY_TYPE": "production"}):
            self.assertIsNone(access_denial(self.request()))

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
