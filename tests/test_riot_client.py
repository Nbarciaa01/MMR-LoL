from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.lolscout.models import MatchSummary, PlayerSummary, RankedEntry
from src.lolscout.riot_client import RiotClient, RiotIdentity
from src.lolscout.scraping_client import ScrapingClient, _TodayLpBaselineCandidate
from src.lolscout.time_utils import app_now


class RiotClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = RiotClient("test-key")

    def test_resolves_euw_identity_through_europe_and_platform_routes(self) -> None:
        account_response = Mock(status_code=200)
        account_response.json.return_value = {
            "puuid": "player-puuid",
            "gameName": "Player",
            "tagLine": "EUW",
        }
        account_response.raise_for_status.return_value = None
        summoner_response = Mock(status_code=200)
        summoner_response.json.return_value = {
            "id": "summoner-id",
            "puuid": "player-puuid",
            "summonerLevel": 123,
            "profileIconId": 456,
        }
        summoner_response.raise_for_status.return_value = None
        self.client.session.get = Mock(side_effect=[account_response, summoner_response])

        identity = self.client.resolve_identity("EUW1", "Player", "EUW")

        self.assertEqual(identity.puuid, "player-puuid")
        self.assertEqual(identity.summoner_id, "summoner-id")
        self.assertIn("europe.api.riotgames.com", self.client.session.get.call_args_list[0].args[0])
        self.assertIn("euw1.api.riotgames.com", self.client.session.get.call_args_list[1].args[0])

    def test_builds_ranked_summary(self) -> None:
        account_response = Mock(status_code=200)
        account_response.json.return_value = {
            "puuid": "player-puuid",
            "gameName": "Player",
            "tagLine": "EUW",
        }
        account_response.raise_for_status.return_value = None
        summoner_response = Mock(status_code=200)
        summoner_response.json.return_value = {
            "id": "summoner-id",
            "puuid": "player-puuid",
            "summonerLevel": 50,
            "profileIconId": 12,
        }
        summoner_response.raise_for_status.return_value = None
        league_response = Mock(status_code=200)
        league_response.json.return_value = [{
            "queueType": "RANKED_SOLO_5x5",
            "tier": "GOLD",
            "rank": "II",
            "leaguePoints": 35,
            "wins": 20,
            "losses": 10,
        }]
        league_response.raise_for_status.return_value = None
        self.client.session.get = Mock(
            side_effect=[account_response, summoner_response, league_response]
        )

        summary = self.client.fetch_player_ranking("Player", "EUW", "EUW1")

        self.assertEqual(summary.soloq.league_points, 35)
        self.assertIn("entries/by-puuid/player-puuid", self.client.session.get.call_args_list[2].args[0])
        self.assertEqual(summary.ranked_games, 30)
        self.assertEqual(summary.global_winrate, 66.7)
        self.assertIsNotNone(summary.estimated_mmr)

    def test_fetches_today_ranked_matches_from_match_v5(self) -> None:
        now = datetime.now().astimezone().replace(hour=16, minute=0, second=0, microsecond=0)
        played_at = now.replace(hour=12)
        detail = {
            "metadata": {"matchId": "EUW1_123"},
            "info": {
                "queueId": 420,
                "gameDuration": 1800,
                "gameEndTimestamp": int(played_at.timestamp() * 1000),
                "participants": [{
                    "puuid": "player-puuid",
                    "championId": 103,
                    "championName": "Ahri",
                    "teamPosition": "MIDDLE",
                    "win": True,
                    "kills": 8,
                    "deaths": 2,
                    "assists": 11,
                    "totalMinionsKilled": 190,
                    "neutralMinionsKilled": 4,
                    "totalDamageDealtToChampions": 22000,
                    "goldEarned": 13000,
                }],
            },
        }
        self.client._get_json = Mock(side_effect=[["EUW1_123"], detail])

        matches = self.client.fetch_today_matches("EUW1", "player-puuid", now_local=now)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].champion, "Ahri")
        self.assertEqual(matches[0].cs, 194)
        list_url = self.client._get_json.call_args_list[0].args[0]
        self.assertIn("matches/by-puuid/player-puuid/ids", list_url)
        self.assertIn("queue=420", list_url)

    def test_today_summary_recovers_pre_match_baseline_from_history(self) -> None:
        now = app_now()
        played_at = now - timedelta(minutes=10)
        soloq = RankedEntry(
            queue_type="RANKED_SOLO_5x5",
            tier="PLATINUM",
            rank="III",
            league_points=98,
            wins=21,
            losses=10,
        )
        player = PlayerSummary(
            game_name="Dark Nøwel",
            tag_line="007",
            summoner_level=100,
            profile_icon_id=1,
            platform="EUW1",
            soloq=soloq,
        )
        match = MatchSummary(
            match_id="EUW1_123",
            champion="Ahri",
            champion_id=103,
            role="MIDDLE",
            queue_name="Ranked Solo/Duo",
            won=True,
            kills=8,
            deaths=2,
            assists=10,
            cs=190,
            duration_min=30,
            damage=20000,
            gold=12000,
            kda=9.0,
            played_at_iso=played_at.isoformat(),
        )
        current_score = ScrapingClient._lp_score_from_ranked_entry(soloq)
        self.assertIsNotNone(current_score)
        current_candidate = _TodayLpBaselineCandidate(
            score=current_score,
            rank_text=soloq.display_rank,
            observed_at=now,
            source="Cache local",
            wins=21,
            losses=10,
        )
        historical_candidate = _TodayLpBaselineCandidate(
            score=current_score - 19,
            rank_text="Platinum III - 79 LP",
            observed_at=played_at - timedelta(minutes=10),
            source="OP.GG",
            wins=20,
            losses=10,
        )
        self.client.resolve_identity = Mock(return_value=RiotIdentity(
            puuid="player-puuid",
            summoner_id="summoner-id",
            game_name="Dark Nøwel",
            tag_line="007",
            summoner_level=100,
            profile_icon_id=1,
        ))
        self.client._ranking_from_identity = Mock(return_value=player)
        self.client.fetch_today_matches = Mock(return_value=[match])

        with (
            patch.object(ScrapingClient, "_load_daily_lp_snapshot_candidates", return_value=[current_candidate]),
            patch.object(ScrapingClient, "_load_opgg_profile_page", return_value="profile") as load_history,
            patch.object(ScrapingClient, "_build_today_candidates_from_opgg_page", return_value=[historical_candidate]),
            patch.object(ScrapingClient, "_append_daily_lp_snapshot"),
        ):
            summary = self.client.fetch_today_summary("Dark Nøwel", "007", "EUW1")

        self.assertEqual(summary.lp_change, 19)
        self.assertEqual(summary.baseline_lp_score, current_score - 19)
        load_history.assert_called_once()

    def test_spectator_v5_uses_puuid_and_handles_not_in_game(self) -> None:
        self.client.resolve_identity = Mock(return_value=RiotIdentity(
            puuid="player-puuid",
            summoner_id="summoner-id",
            game_name="Player",
            tag_line="EUW",
            summoner_level=50,
            profile_icon_id=12,
        ))
        self.client._get_json = Mock(return_value=None)

        summary = self.client.fetch_live_game_summary("Player", "EUW", "EUW1")

        self.assertFalse(summary.in_game)
        spectator_url = self.client._get_json.call_args.args[0]
        self.assertIn("spectator/v5/active-games/by-summoner/player-puuid", spectator_url)


if __name__ == "__main__":
    unittest.main()
