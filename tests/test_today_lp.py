from __future__ import annotations

import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from lolscout.models import MatchSummary, PlayerSummary, RankedEntry
from lolscout.scraping_client import ScrapingClient, ScrapingError, _TodayLpBaselineCandidate


class StubTodayClient(ScrapingClient):
    def __init__(
        self,
        ranking_summary: PlayerSummary,
        public_matches: list[MatchSummary],
        candidates: list[_TodayLpBaselineCandidate],
    ) -> None:
        super().__init__()
        self._ranking_summary = copy.deepcopy(ranking_summary)
        self._public_matches = copy.deepcopy(public_matches)
        self._candidates = copy.deepcopy(candidates)

    def fetch_player_ranking(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
        force_refresh: bool = False,
        store_today_snapshot: bool = True,
    ) -> PlayerSummary:
        return copy.deepcopy(self._ranking_summary)

    def _load_today_matches_from_leagueofgraphs(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        force_refresh: bool = False,
    ) -> list[MatchSummary]:
        return copy.deepcopy(self._public_matches)

    def _load_daily_lp_snapshot_candidates(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
    ) -> list[_TodayLpBaselineCandidate]:
        return copy.deepcopy(self._candidates)

    def _load_opgg_profile_page(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        force_refresh: bool = False,
    ) -> str | None:
        return None

    def _append_daily_lp_snapshot(
        self,
        summary: PlayerSummary,
        cache_game_name: str | None = None,
        cache_tag_line: str | None = None,
    ) -> None:
        return None


class StubFallbackClient(ScrapingClient):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def _load_opgg_profile_page(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        force_refresh: bool = False,
    ) -> str | None:
        self.calls.append("opgg")
        return (
            f"<title>{game_name}#{tag_line} - Summoner Stats</title>"
            '"summonerLevel":123'
            '/profileicon/1.png'
        )

    def _get_text(
        self,
        url: str,
        context: str,
        headers: dict[str, str] | None = None,
        force_refresh: bool = False,
    ) -> str:
        self.calls.append("leagueofgraphs")
        raise ScrapingError(f"{context}: error HTTP (403).")

    def _load_profile_from_ugg(self, platform: str, game_name: str, tag_line: str):
        self.calls.append("ugg")
        return None


class TodayLpTests(unittest.TestCase):
    def _ranked_entry(self, lp: int, wins: int, losses: int) -> RankedEntry:
        return RankedEntry(
            queue_type="RANKED_SOLO_5x5",
            tier="GOLD",
            rank="I",
            league_points=lp,
            wins=wins,
            losses=losses,
        )

    def _player_summary(self, entry: RankedEntry) -> PlayerSummary:
        return PlayerSummary(
            game_name="Tester",
            tag_line="EUW",
            summoner_level=100,
            profile_icon_id=1,
            platform="EUW1",
            soloq=entry,
            ranked_available=True,
        )

    def _candidate(
        self,
        observed_at: datetime,
        lp: int,
        wins: int | None,
        losses: int | None,
    ) -> _TodayLpBaselineCandidate:
        score = ScrapingClient._lp_score_from_parts("GOLD", "I", lp)
        assert score is not None
        return _TodayLpBaselineCandidate(
            score=score,
            rank_text=f"Gold I - {lp} LP",
            observed_at=observed_at,
            source="Cache local",
            wins=wins,
            losses=losses,
        )

    def _today_match(self, index: int, played_at: datetime) -> MatchSummary:
        return MatchSummary(
            match_id=f"EUW1_{index}",
            champion="Ahri",
            champion_id=103,
            role="MIDDLE",
            queue_name="Ranked Solo/Duo",
            won=index % 2 == 0,
            kills=10,
            deaths=3,
            assists=8,
            cs=200,
            duration_min=29,
            damage=23000,
            gold=14000,
            kda=6.0,
            played_at_iso=played_at.isoformat(),
            played_at_text="today",
        )

    def test_fetch_today_lp_falls_back_to_zero_when_no_games_detected(self) -> None:
        now = datetime.now().astimezone()
        yesterday = now - timedelta(days=1)
        current_entry = self._ranked_entry(lp=50, wins=70, losses=70)
        player = self._player_summary(current_entry)
        stale_candidate = self._candidate(
            observed_at=yesterday.replace(hour=15, minute=30, second=0, microsecond=0),
            lp=30,
            wins=69,
            losses=70,
        )
        client = StubTodayClient(player, [], [stale_candidate])

        summary = client.fetch_player_today_lp("Tester", "EUW", "EUW1")

        self.assertEqual(summary.lp_change, 0)
        self.assertEqual(summary.current_lp_score, summary.baseline_lp_score)
        self.assertEqual(summary.baseline_source, "Referencia actual")
        self.assertEqual(summary.today_matches, [])

    def test_fetch_today_lp_uses_all_detected_matches_for_baseline_count(self) -> None:
        now = datetime.now().astimezone()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        current_entry = self._ranked_entry(lp=80, wins=50, losses=50)
        player = self._player_summary(current_entry)
        matches = [self._today_match(index, start_of_day + timedelta(hours=index + 1)) for index in range(7)]
        wrong_candidate = self._candidate(
            observed_at=start_of_day - timedelta(minutes=5),
            lp=45,
            wins=47,
            losses=48,
        )
        correct_candidate = self._candidate(
            observed_at=start_of_day - timedelta(hours=1),
            lp=20,
            wins=46,
            losses=47,
        )
        client = StubTodayClient(player, matches, [wrong_candidate, correct_candidate])

        summary = client.fetch_player_today_lp("Tester", "EUW", "EUW1")

        self.assertEqual(summary.baseline_lp_score, correct_candidate.score)
        self.assertEqual(summary.lp_change, summary.current_lp_score - correct_candidate.score)
        self.assertEqual(len(summary.today_matches), 5)

    def test_select_today_baseline_prefers_same_day_candidate_before_first_match(self) -> None:
        now = datetime.now().astimezone().replace(hour=18, minute=0, second=0, microsecond=0)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        first_match_at = start_of_day + timedelta(hours=13)
        near_midnight = self._candidate(
            observed_at=start_of_day - timedelta(minutes=10),
            lp=25,
            wins=None,
            losses=None,
        )
        same_day = self._candidate(
            observed_at=start_of_day + timedelta(hours=11),
            lp=28,
            wins=None,
            losses=None,
        )

        baseline = ScrapingClient._select_today_baseline_candidate(
            [near_midnight, same_day],
            start_of_day,
            now,
            first_match_at=first_match_at,
            current_total_games=100,
            today_match_count=2,
            current_lp_score=ScrapingClient._lp_score_from_parts("GOLD", "I", 80),
        )

        self.assertIsNotNone(baseline)
        self.assertEqual(baseline.observed_at, same_day.observed_at)

    def test_select_today_baseline_rejects_snapshot_after_first_match(self) -> None:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        first_match_at = start_of_day + timedelta(minutes=20)
        current_candidate = _TodayLpBaselineCandidate(
            score=1798,
            rank_text="Platinum III - 98 LP",
            observed_at=first_match_at + timedelta(hours=10),
            source="Cache local",
            wins=153,
            losses=156,
        )

        baseline = ScrapingClient._select_today_baseline_candidate(
            [current_candidate],
            start_of_day,
            now,
            first_match_at=first_match_at,
            current_total_games=309,
            today_match_count=1,
            current_lp_score=1798,
        )

        self.assertIsNone(baseline)

    def test_select_today_baseline_infers_game_from_ranked_total_when_matches_unavailable(self) -> None:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_state = _TodayLpBaselineCandidate(
            score=1779,
            rank_text="Platinum III - 79 LP",
            observed_at=start_of_day - timedelta(hours=5),
            source="Cache local",
            wins=152,
            losses=156,
        )
        current_state = _TodayLpBaselineCandidate(
            score=1798,
            rank_text="Platinum III - 98 LP",
            observed_at=now,
            source="Cache local",
            wins=153,
            losses=156,
        )

        baseline = ScrapingClient._select_today_baseline_candidate(
            [previous_state, current_state],
            start_of_day,
            now,
            current_total_games=309,
            today_match_count=0,
            current_lp_score=1798,
        )

        self.assertIsNotNone(baseline)
        self.assertEqual(baseline.score, 1779)
        self.assertEqual(baseline.total_games, 308)

    def test_ranking_profile_prefers_opgg_before_leagueofgraphs(self) -> None:
        client = StubFallbackClient()

        profile, league_page, opgg_page = client._load_profile_with_fallbacks(
            "EUW1",
            "Tester",
            "EUW",
            include_matches=False,
        )

        self.assertEqual(profile.game_name, "Tester")
        self.assertIsNone(league_page)
        self.assertIsNotNone(opgg_page)
        self.assertEqual(client.calls, ["opgg"])


if __name__ == "__main__":
    unittest.main()
