import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from src.lolscout import web_app
from src.lolscout.riot_client import RiotApiError


class RankingActivityTests(unittest.TestCase):
    def test_unconfigured_player_is_rejected_without_riot_request(self):
        with patch.object(web_app, "_players", return_value=[]), patch.object(web_app, "_riot_client") as client:
            with self.assertRaises(HTTPException) as error:
                web_app.ranking_activity("Unknown", "EUW")
            self.assertEqual(error.exception.status_code, 404)
            client.assert_not_called()

    def test_daily_failure_preserves_recent_matches(self):
        client = Mock()
        client.fetch_recent_matches.return_value = []
        client.fetch_today_summary.side_effect = RiotApiError("Limit")
        with (
            patch.object(web_app, "_players", return_value=[("Player", "EUW")]),
            patch.object(web_app, "_get_cached_response", return_value=None),
            patch.object(web_app, "_set_cached_response"),
            patch.object(web_app, "_riot_client", return_value=client),
        ):
            result = web_app.ranking_activity("Player", "EUW")
        self.assertEqual(result["recent_matches"], [])
        self.assertIsNone(result["lp_change"])
        self.assertEqual(result["today_error"], "Limit")

    def test_history_failure_preserves_daily_lp(self):
        client = Mock()
        client.fetch_recent_matches.side_effect = RiotApiError("History unavailable")
        client.fetch_today_summary.return_value = Mock(lp_change=19, baseline_note="Snapshot")
        with (
            patch.object(web_app, "_players", return_value=[("Player", "EUW")]),
            patch.object(web_app, "_get_cached_response", return_value=None),
            patch.object(web_app, "_set_cached_response"),
            patch.object(web_app, "_riot_client", return_value=client),
        ):
            result = web_app.ranking_activity("Player", "EUW")
        self.assertEqual(result["lp_change"], 19)
        self.assertIsNone(result["recent_matches"])

    def test_cached_activity_does_not_consume_riot_requests(self):
        payload = {"recent_matches": [], "lp_change": 0}
        with (
            patch.object(web_app, "_players", return_value=[("Player", "EUW")]),
            patch.object(web_app, "_get_cached_response", return_value=payload),
            patch.object(web_app, "_riot_client") as client,
        ):
            self.assertEqual(web_app.ranking_activity("Player", "EUW"), payload)
            client.assert_not_called()
