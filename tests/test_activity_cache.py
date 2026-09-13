import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from src.lolscout.riot_client import RiotClient
from src.lolscout.time_utils import app_now


class ActivityCacheTests(unittest.TestCase):
    def test_recent_history_covers_today_when_it_reaches_yesterday(self):
        client = RiotClient("test")
        now = app_now().replace(hour=12)
        today = Mock(played_at_iso=now.isoformat())
        yesterday = Mock(played_at_iso=(now - timedelta(days=1)).isoformat())
        with patch("src.lolscout.riot_client.app_now", return_value=now):
            self.assertEqual(client._today_from_recent([today] * 4 + [yesterday]), [today] * 4)
            self.assertIsNone(client._today_from_recent([today] * 5))
            self.assertEqual(client._today_from_recent([]), [])
            self.assertIsNone(client._today_from_recent(None))
            self.assertIsNone(client._today_from_recent([Mock(played_at_iso=None)]))

    def test_completed_match_cache_survives_new_client(self):
        url = "https://europe.api.riotgames.com/lol/match/v5/matches/EUW1_123"
        payload = {"info": {"queueId": 420}}
        store = Mock()
        store.get_cached_response.return_value = payload
        client = RiotClient("test", persistent_match_cache=True)
        client.session.get = Mock()
        with patch("src.lolscout.riot_client.get_store", return_value=store):
            self.assertEqual(client._get_json(url, ttl_seconds=86400), payload)
            self.assertEqual(client._get_json(url, ttl_seconds=86400), payload)
        client.session.get.assert_not_called()
        store.get_cached_response.assert_called_once()

    def test_history_ids_are_not_persisted_and_cache_failure_is_optional(self):
        for path, fails in [("by-puuid/test/ids?count=5", False), ("EUW1_123", True)]:
            client = RiotClient("test", persistent_match_cache=True)
            response = Mock(status_code=200)
            response.json.return_value = {"info": {}}
            client.session.get = Mock(return_value=response)
            with patch("src.lolscout.riot_client.get_store", side_effect=RuntimeError) as store:
                client._get_json(f"https://europe.api.riotgames.com/lol/match/v5/matches/{path}", ttl_seconds=90)
            self.assertEqual(store.called, fails)
            client.session.get.assert_called_once()
