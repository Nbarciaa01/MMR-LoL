from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import html
import json
from pathlib import Path
import re
from threading import Lock
import time
from typing import Callable
import unicodedata
from urllib.parse import parse_qsl, quote, quote_plus, urlencode, urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import APP_DIR
from .persistence import get_store
from .time_utils import app_now, to_app_timezone
from .models import (
    ChampionPlayStat,
    LiveGameParticipantSummary,
    LiveGamePlayerDetails,
    LiveGameSummary,
    MatchSummary,
    PlayerSummary,
    RankedEntry,
    RolePlayStat,
    TodayLpSummary,
)


class ScrapingError(Exception):
    pass


MATCH_PAGE_SIZE = 10
MAX_RECENT_MATCHES = 10
RANKING_CACHE_TTL_SECONDS = 300
OPGG_AUTO_RENEW_AGE_SECONDS = 7 * 60
CACHE_DIR = APP_DIR / "cache"
LEGACY_CACHE_DIR = Path.cwd() / ".lolscout_cache"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/135.0.0.0 Safari/537.36"
)
DEFAULT_BROWSER_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
LEAGUEOFGRAPHS_MIN_INTERVAL_SECONDS = 0.65
LEAGUEOFGRAPHS_BLOCKED_BACKOFF_SECONDS = 90
_LEAGUEOFGRAPHS_LOCK = Lock()
_LEAGUEOFGRAPHS_LAST_REQUEST_AT = 0.0
_LEAGUEOFGRAPHS_BLOCKED_UNTIL = 0.0
CDRAGON_CHAMPION_SUMMARY_URL = (
    "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-summary.json"
)
_CHAMPION_ID_LOOKUP_CACHE: dict[str, int] | None = None

PLATFORM_TO_OPGG_REGION = {
    "BR1": "br",
    "EUN1": "eune",
    "EUW1": "euw",
    "KR": "kr",
    "LA1": "lan",
    "LA2": "las",
    "ME1": "me",
    "NA1": "na",
    "OC1": "oce",
    "RU": "ru",
    "TR1": "tr",
}
PLATFORM_TO_UGG_REGION = {
    "BR1": "br1",
    "EUN1": "eun1",
    "EUW1": "euw1",
    "KR": "kr",
    "LA1": "la1",
    "LA2": "la2",
    "ME1": "me1",
    "NA1": "na1",
    "OC1": "oc1",
    "RU": "ru",
    "TR1": "tr1",
}
PLATFORM_TO_POROFESSOR_REGION = {
    "BR1": "br",
    "EUN1": "eune",
    "EUW1": "euw",
    "KR": "kr",
    "LA1": "lan",
    "LA2": "las",
    "ME1": "me",
    "NA1": "na",
    "OC1": "oce",
    "RU": "ru",
    "TR1": "tr",
}
PLATFORM_TO_LEAGUEOFGRAPHS_REGION = {
    "BR1": "br",
    "EUN1": "eune",
    "EUW1": "euw",
    "KR": "kr",
    "LA1": "lan",
    "LA2": "las",
    "ME1": "me",
    "NA1": "na",
    "OC1": "oce",
    "RU": "ru",
    "TR1": "tr",
}
TIER_ALIASES = {
    "iron": "IRON",
    "bronze": "BRONZE",
    "silver": "SILVER",
    "gold": "GOLD",
    "platinum": "PLATINUM",
    "emerald": "EMERALD",
    "diamond": "DIAMOND",
    "master": "MASTER",
    "grandmaster": "GRANDMASTER",
    "challenger": "CHALLENGER",
}
DIVISION_ALIASES = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
    "I": "I",
    "II": "II",
    "III": "III",
    "IV": "IV",
}
ROLE_ALIASES = {
    "TOP": "TOP",
    "TOPLANE": "TOP",
    "TOP LANE": "TOP",
    "JUNGLE": "JUNGLE",
    "JGL": "JUNGLE",
    "JG": "JUNGLE",
    "MID": "MIDDLE",
    "MIDLANE": "MIDDLE",
    "MID LANE": "MIDDLE",
    "MIDDLE": "MIDDLE",
    "MIDDLE LANE": "MIDDLE",
    "ADC": "BOTTOM",
    "DUO": "BOTTOM",
    "DUO_CARRY": "BOTTOM",
    "CARRY": "BOTTOM",
    "BOTTOM": "BOTTOM",
    "BOTTOM LANE": "BOTTOM",
    "BOT": "BOTTOM",
    "BOTLANE": "BOTTOM",
    "BOT LANE": "BOTTOM",
    "SUPPORT": "UTILITY",
    "SUP": "UTILITY",
    "UTILITY": "UTILITY",
    "DUO_SUPPORT": "UTILITY",
    "ADCARRY": "BOTTOM",
    "AD CARRY": "BOTTOM",
}
LEAGUEOFGRAPHS_ROLE_SLUGS = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "middle",
    "BOTTOM": "adc",
    "UTILITY": "support",
}
SOLOQUEUE_LABELS = (
    "ranked solo",
    "ranked solo/duo",
    "solo/duo",
    "soloq",
    "solo queue",
    "soloqueue",
)
TIER_BASE = {
    "IRON": 800,
    "BRONZE": 950,
    "SILVER": 1100,
    "GOLD": 1275,
    "PLATINUM": 1450,
    "EMERALD": 1600,
    "DIAMOND": 1800,
    "MASTER": 2050,
    "GRANDMASTER": 2200,
    "CHALLENGER": 2350,
}
RANK_OFFSET = {"IV": 0, "III": 65, "II": 130, "I": 195}
LP_TRACKING_TIER_SCORE = {
    "IRON": 0,
    "BRONZE": 400,
    "SILVER": 800,
    "GOLD": 1200,
    "PLATINUM": 1600,
    "EMERALD": 2000,
    "DIAMOND": 2400,
    "MASTER": 2800,
    "GRANDMASTER": 3200,
    "CHALLENGER": 3600,
}
LP_TRACKING_DIVISION_SCORE = {"IV": 0, "III": 100, "II": 200, "I": 300}
TODAY_LP_SNAPSHOT_LIMIT = 96
TODAY_LP_SNAPSHOT_DEDUP_SECONDS = 10 * 60
TODAY_BASELINE_GRACE_HOURS = 4


@dataclass
class ExternalProfile:
    game_name: str
    tag_line: str
    summoner_level: int = 0
    profile_icon_id: int = 0
    matches: list[MatchSummary] = field(default_factory=list)


@dataclass
class _TodayLpBaselineCandidate:
    score: int
    rank_text: str
    observed_at: datetime
    source: str
    wins: int | None = None
    losses: int | None = None

    @property
    def total_games(self) -> int | None:
        if self.wins is None or self.losses is None:
            return None
        return self.wins + self.losses


@dataclass
class ScrapingClient:
    timeout: int = 20
    progress_callback: Callable[[str], None] | None = None
    session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            status=2,
            backoff_factor=0.35,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            try:
                LEGACY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass

    def _emit_progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    @staticmethod
    def _summary_has_loaded_data(summary: PlayerSummary) -> bool:
        return (
            summary.summoner_level > 0
            or summary.profile_icon_id > 0
            or summary.soloq is not None
            or summary.flex is not None
            or bool(summary.most_played_champions)
            or summary.top_mastery_champion_id > 0
        )

    @staticmethod
    def _summary_has_valid_identity(summary: PlayerSummary) -> bool:
        game_name = str(summary.game_name or "").strip()
        tag_line = str(summary.tag_line or "").strip()
        if not game_name or not tag_line:
            return False
        if any(token in game_name for token in ('"', "<", ">", "=")):
            return False
        return bool(re.fullmatch(r"[A-Za-z0-9]{2,8}", tag_line))

    @staticmethod
    def _cache_file_candidates(file_name: str) -> list[Path]:
        primary_path = CACHE_DIR / file_name
        legacy_path = LEGACY_CACHE_DIR / file_name
        if legacy_path == primary_path:
            return [primary_path]
        return [primary_path, legacy_path]

    @staticmethod
    def _write_cache_path(file_name: str) -> Path:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            return CACHE_DIR / file_name
        except OSError:
            try:
                LEGACY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                return LEGACY_CACHE_DIR / file_name
            except OSError:
                return CACHE_DIR / file_name

    @staticmethod
    def _ranking_cache_path(platform: str, game_name: str, tag_line: str) -> Path:
        raw_key = f"{platform}:{game_name}#{tag_line}".casefold()
        safe_key = re.sub(r"[^a-z0-9_-]+", "_", raw_key)
        return ScrapingClient._write_cache_path(f"ranking_{safe_key}.json")

    @staticmethod
    def _ranking_cache_paths(platform: str, game_name: str, tag_line: str) -> list[Path]:
        raw_key = f"{platform}:{game_name}#{tag_line}".casefold()
        safe_key = re.sub(r"[^a-z0-9_-]+", "_", raw_key)
        return ScrapingClient._cache_file_candidates(f"ranking_{safe_key}.json")

    @staticmethod
    def _ranked_entry_to_dict(entry: RankedEntry | None) -> dict | None:
        if entry is None:
            return None
        return {
            "queue_type": entry.queue_type,
            "tier": entry.tier,
            "rank": entry.rank,
            "league_points": entry.league_points,
            "wins": entry.wins,
            "losses": entry.losses,
        }

    @staticmethod
    def _ranked_entry_from_dict(data: dict | None) -> RankedEntry | None:
        if not isinstance(data, dict):
            return None
        return RankedEntry(
            queue_type=str(data.get("queue_type", "")),
            tier=str(data.get("tier", "")),
            rank=str(data.get("rank", "")),
            league_points=int(data.get("league_points", 0) or 0),
            wins=int(data.get("wins", 0) or 0),
            losses=int(data.get("losses", 0) or 0),
        )

    def _serialize_ranking_summary(self, summary: PlayerSummary) -> dict:
        return {
            "game_name": summary.game_name,
            "tag_line": summary.tag_line,
            "summoner_level": summary.summoner_level,
            "profile_icon_id": summary.profile_icon_id,
            "platform": summary.platform,
            "opgg_url": summary.opgg_url,
            "soloq": self._ranked_entry_to_dict(summary.soloq),
            "flex": self._ranked_entry_to_dict(summary.flex),
            "estimated_mmr": summary.estimated_mmr,
            "global_winrate": summary.global_winrate,
            "ranked_games": summary.ranked_games,
            "recent_winrate": summary.recent_winrate,
            "ranked_available": summary.ranked_available,
            "top_mastery_champion_id": summary.top_mastery_champion_id,
            "top_mastery_level": summary.top_mastery_level,
            "top_mastery_points": summary.top_mastery_points,
            "most_played_champions": [
                {
                    "champion": champion.champion,
                    "champion_id": champion.champion_id,
                    "games": champion.games,
                }
                for champion in summary.most_played_champions
            ],
        }

    def _deserialize_ranking_summary(self, data: dict) -> PlayerSummary:
        return PlayerSummary(
            game_name=str(data.get("game_name", "")),
            tag_line=str(data.get("tag_line", "")),
            summoner_level=int(data.get("summoner_level", 0) or 0),
            profile_icon_id=int(data.get("profile_icon_id", 0) or 0),
            platform=str(data.get("platform", "")),
            opgg_url=str(data.get("opgg_url")) if data.get("opgg_url") else None,
            soloq=self._ranked_entry_from_dict(data.get("soloq")),
            flex=self._ranked_entry_from_dict(data.get("flex")),
            estimated_mmr=int(data["estimated_mmr"]) if data.get("estimated_mmr") is not None else None,
            global_winrate=float(data["global_winrate"]) if data.get("global_winrate") is not None else None,
            ranked_games=int(data["ranked_games"]) if data.get("ranked_games") is not None else None,
            recent_winrate=float(data.get("recent_winrate", 0.0) or 0.0),
            most_played_champions=[
                ChampionPlayStat(
                    champion=str(champion.get("champion", "")),
                    champion_id=int(champion.get("champion_id", 0) or 0),
                    games=int(champion.get("games", 0) or 0),
                )
                for champion in data.get("most_played_champions", [])
                if isinstance(champion, dict)
            ],
            ranked_available=bool(data.get("ranked_available", True)),
            top_mastery_champion_id=int(data.get("top_mastery_champion_id", 0) or 0),
            top_mastery_level=int(data["top_mastery_level"]) if data.get("top_mastery_level") is not None else None,
            top_mastery_points=int(data["top_mastery_points"]) if data.get("top_mastery_points") is not None else None,
        )

    def _fetch_top_champion_mastery(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        page: str | None = None,
    ) -> tuple[int, int | None, int | None]:
        return self._fetch_top_champion_mastery_public(platform, game_name, tag_line, page=page)

    @staticmethod
    def _parse_top_champion_mastery_from_page(page: str) -> tuple[int, int | None, int | None]:
        pattern = re.compile(
            r'tooltip="(?P<tooltip>[^"]*Mastery Level\s+(?P<level>\d+)[^"]*?Points:\s*(?P<points>[\d,]+)[^"]*)"'
            r'[\s\S]{0,700}?<img[^>]+alt="(?P<champion>[^"]+)"[^>]+class="champion-(?P<champion_id>\d+)-',
            re.IGNORECASE,
        )
        best: tuple[int, int | None, int | None] = (0, None, None)
        best_points = -1
        seen_champions: set[int] = set()

        for match in pattern.finditer(page):
            try:
                champion_id = int(match.group("champion_id"))
                mastery_level = int(match.group("level"))
                mastery_points = int(match.group("points").replace(",", ""))
            except (TypeError, ValueError):
                continue
            if champion_id <= 0 or champion_id in seen_champions:
                continue
            seen_champions.add(champion_id)
            if mastery_points > best_points:
                best_points = mastery_points
                best = (champion_id, mastery_level, mastery_points)

        return best

    def _fetch_top_champion_mastery_public(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        page: str | None = None,
    ) -> tuple[int, int | None, int | None]:
        try:
            region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
            if not region:
                return 0, None, None
            source = page or self._get_text(
                f"https://www.leagueofgraphs.com/summoner/{region}/{self._slug(game_name, tag_line)}",
                context="LeagueOfGraphs perfil",
            )
        except ScrapingError:
            return 0, None, None
        return self._parse_top_champion_mastery_from_page(source)

    def _load_cached_ranking_summary(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        max_age_seconds: int | None = RANKING_CACHE_TTL_SECONDS,
    ) -> PlayerSummary | None:
        cache_path = next((path for path in self._ranking_cache_paths(platform, game_name, tag_line) if path.exists()), None)
        if cache_path is None:
            return None

        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        cached_at = float(payload.get("cached_at", 0) or 0)
        if max_age_seconds is not None and cached_at > 0:
            if time.time() - cached_at > max_age_seconds:
                return None

        data = payload.get("summary")
        if not isinstance(data, dict):
            return None
        summary = self._deserialize_ranking_summary(data)
        if not self._summary_has_loaded_data(summary):
            return None
        if not self._summary_has_valid_identity(summary):
            return None
        return summary

    def _store_cached_ranking_summary(
        self,
        summary: PlayerSummary,
        cache_game_name: str | None = None,
        cache_tag_line: str | None = None,
    ) -> None:
        cache_path = self._ranking_cache_path(
            summary.platform,
            cache_game_name or summary.game_name,
            cache_tag_line or summary.tag_line,
        )
        payload = {
            "cached_at": time.time(),
            "summary": self._serialize_ranking_summary(summary),
        }
        try:
            cache_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        except OSError:
            return

    @staticmethod
    def _daily_lp_cache_path(platform: str, game_name: str, tag_line: str) -> Path:
        raw_key = f"{platform}:{game_name}#{tag_line}".casefold()
        safe_key = re.sub(r"[^a-z0-9_-]+", "_", raw_key)
        return ScrapingClient._write_cache_path(f"today_lp_{safe_key}.json")

    @staticmethod
    def _daily_lp_cache_paths(platform: str, game_name: str, tag_line: str) -> list[Path]:
        raw_key = f"{platform}:{game_name}#{tag_line}".casefold()
        safe_key = re.sub(r"[^a-z0-9_-]+", "_", raw_key)
        return ScrapingClient._cache_file_candidates(f"today_lp_{safe_key}.json")

    @staticmethod
    def _normalize_rank_division(rank: str) -> str:
        return DIVISION_ALIASES.get(str(rank or "").strip().upper(), "")

    @classmethod
    def _lp_score_from_parts(cls, tier: str, rank: str, league_points: int) -> int | None:
        normalized_tier = str(tier or "").strip().upper()
        if normalized_tier not in LP_TRACKING_TIER_SCORE:
            return None
        normalized_rank = cls._normalize_rank_division(rank)
        return LP_TRACKING_TIER_SCORE[normalized_tier] + LP_TRACKING_DIVISION_SCORE.get(normalized_rank, 0) + league_points

    @classmethod
    def _lp_score_from_ranked_entry(cls, entry: RankedEntry | None) -> int | None:
        if entry is None or not entry.tier:
            return None
        return cls._lp_score_from_parts(entry.tier, entry.rank, int(entry.league_points or 0))

    @classmethod
    def _format_rank_text(cls, tier: str, rank: str, league_points: int) -> str:
        normalized_tier = str(tier or "").strip()
        normalized_rank = cls._normalize_rank_division(rank)
        if not normalized_tier:
            return "Sin SoloQ"
        title = normalized_tier.title()
        if normalized_rank:
            return f"{title} {normalized_rank} - {league_points} LP"
        return f"{title} - {league_points} LP"

    @classmethod
    def _score_from_opgg_tier_info(cls, tier_info: dict) -> tuple[int | None, str]:
        tier = str(tier_info.get("tier", "") or "").strip().upper()
        label = str(tier_info.get("label", "") or "").strip()
        division = cls._normalize_rank_division(label.split()[-1] if label else "")
        league_points = int(tier_info.get("lp", 0) or 0)
        score = cls._lp_score_from_parts(tier, division, league_points)
        return score, cls._format_rank_text(tier, division, league_points)

    @staticmethod
    def _extract_json_array_after_key(source: str, key: str) -> str | None:
        patterns = (
            rf'"{re.escape(key)}"\s*:\s*\[',
            rf"{re.escape(key)}\s*:\s*\[",
        )
        match = None
        for pattern in patterns:
            match = re.search(pattern, source)
            if match:
                break
        if match is None:
            return None

        start = source.find("[", match.start())
        if start < 0:
            return None

        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(source)):
            char = source[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth == 0:
                    return source[start:index + 1]
        return None

    def _extract_opgg_lp_histories(self, page: str) -> list[dict]:
        variants = [page]
        normalized_page = html.unescape(page)
        if normalized_page != page:
            variants.append(normalized_page)
        if '\\"' in normalized_page:
            variants.append(normalized_page.replace('\\"', '"'))

        for variant in variants:
            array_text = self._extract_json_array_after_key(variant, "lpHistories")
            if not array_text:
                continue
            try:
                data = json.loads(array_text)
            except json.JSONDecodeError:
                continue
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        return []

    def _load_daily_lp_snapshot_candidates(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
    ) -> list[_TodayLpBaselineCandidate]:
        store = get_store()
        if store is not None:
            snapshots = store.load_snapshots(platform, game_name, tag_line)
        else:
            cache_path = next(
                (path for path in self._daily_lp_cache_paths(platform, game_name, tag_line) if path.exists()),
                None,
            )
            if cache_path is None:
                return []
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return []
            snapshots = payload.get("snapshots")
            if not isinstance(snapshots, list):
                return []

        candidates: list[_TodayLpBaselineCandidate] = []
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            observed_at_raw = str(snapshot.get("observed_at", "") or "").strip()
            rank_text = str(snapshot.get("rank_text", "") or "").strip()
            if not observed_at_raw or not rank_text:
                continue
            try:
                observed_at = datetime.fromisoformat(observed_at_raw)
            except ValueError:
                continue
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)

            score = snapshot.get("lp_score")
            if score is None:
                continue
            try:
                candidates.append(
                    _TodayLpBaselineCandidate(
                        score=int(score),
                        rank_text=rank_text,
                        observed_at=to_app_timezone(observed_at),
                        source="Cache local",
                        wins=int(snapshot["wins"]) if snapshot.get("wins") is not None else None,
                        losses=int(snapshot["losses"]) if snapshot.get("losses") is not None else None,
                    )
                )
            except (TypeError, ValueError):
                continue
        return candidates

    def _append_daily_lp_snapshot(
        self,
        summary: PlayerSummary,
        cache_game_name: str | None = None,
        cache_tag_line: str | None = None,
    ) -> None:
        lp_score = self._lp_score_from_ranked_entry(summary.soloq)
        if lp_score is None or summary.soloq is None:
            return

        game_name = cache_game_name or summary.game_name
        tag_line = cache_tag_line or summary.tag_line
        observed_at = app_now()
        snapshot = {
            "observed_at": observed_at.isoformat(),
            "lp_score": lp_score,
            "rank_text": summary.soloq.display_rank,
            "wins": int(summary.soloq.wins or 0),
            "losses": int(summary.soloq.losses or 0),
            "total_games": int(summary.soloq.total_games or 0),
        }
        store = get_store()
        if store is not None:
            store.append_snapshot(
                summary.platform,
                game_name,
                tag_line,
                snapshot,
                TODAY_LP_SNAPSHOT_DEDUP_SECONDS,
            )
            return

        cache_path = self._daily_lp_cache_path(
            summary.platform,
            game_name,
            tag_line,
        )
        read_cache_path = next(
            (
                path
                for path in self._daily_lp_cache_paths(
                    summary.platform,
                    game_name,
                    tag_line,
                )
                if path.exists()
            ),
            cache_path,
        )
        snapshots: list[dict] = []
        if read_cache_path.exists():
            try:
                payload = json.loads(read_cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            raw_snapshots = payload.get("snapshots")
            if isinstance(raw_snapshots, list):
                snapshots = [snapshot for snapshot in raw_snapshots if isinstance(snapshot, dict)]

        if snapshots:
            last_snapshot = snapshots[-1]
            last_observed_at_raw = str(last_snapshot.get("observed_at", "") or "").strip()
            try:
                last_observed_at = datetime.fromisoformat(last_observed_at_raw)
            except ValueError:
                last_observed_at = None
            if last_observed_at is not None and last_observed_at.tzinfo is None:
                last_observed_at = last_observed_at.replace(tzinfo=timezone.utc)
            last_score = last_snapshot.get("lp_score")
            try:
                normalized_last_score = int(last_score) if last_score is not None else None
            except (TypeError, ValueError):
                normalized_last_score = None
            if (
                last_observed_at is not None
                and normalized_last_score is not None
                and lp_score == normalized_last_score
                and abs((observed_at - to_app_timezone(last_observed_at)).total_seconds()) < TODAY_LP_SNAPSHOT_DEDUP_SECONDS
            ):
                return

        snapshots.append(snapshot)
        snapshots = snapshots[-TODAY_LP_SNAPSHOT_LIMIT:]
        try:
            cache_path.write_text(json.dumps({"snapshots": snapshots}, ensure_ascii=True), encoding="utf-8")
        except OSError:
            return

    def _build_today_candidates_from_opgg_page(self, page: str) -> list[_TodayLpBaselineCandidate]:
        candidates: list[_TodayLpBaselineCandidate] = []
        for item in self._extract_opgg_lp_histories(page):
            created_at_raw = str(item.get("created_at", "") or "").strip()
            tier_info = item.get("tier_info")
            if not created_at_raw or not isinstance(tier_info, dict):
                continue
            try:
                observed_at = datetime.fromisoformat(created_at_raw)
            except ValueError:
                continue
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)
            score, rank_text = self._score_from_opgg_tier_info(tier_info)
            if score is None:
                continue
            candidates.append(
                _TodayLpBaselineCandidate(
                    score=score,
                    rank_text=rank_text,
                    observed_at=to_app_timezone(observed_at),
                    source="OP.GG",
                )
            )
        return candidates

    @staticmethod
    def _select_today_baseline_candidate(
        candidates: list[_TodayLpBaselineCandidate],
        start_of_day: datetime,
        now_local: datetime,
        first_match_at: datetime | None = None,
        current_total_games: int | None = None,
        today_match_count: int = 0,
        current_lp_score: int | None = None,
    ) -> _TodayLpBaselineCandidate | None:
        valid_candidates = [
            candidate
            for candidate in candidates
            if start_of_day - timedelta(days=2) <= candidate.observed_at <= now_local
        ]
        if not valid_candidates:
            return None

        def _source_priority(candidate: _TodayLpBaselineCandidate) -> int:
            return 0 if candidate.source == "Cache local" else 1

        def _closest_to_day_start(candidate: _TodayLpBaselineCandidate) -> tuple[float, int, int]:
            return (
                abs((candidate.observed_at - start_of_day).total_seconds()),
                0 if candidate.observed_at >= start_of_day else 1,
                _source_priority(candidate),
            )

        def _most_recent(candidate: _TodayLpBaselineCandidate) -> tuple[datetime, int]:
            return (candidate.observed_at, -_source_priority(candidate))

        search_candidates = valid_candidates
        if first_match_at is not None:
            pre_match_candidates = [candidate for candidate in valid_candidates if candidate.observed_at <= first_match_at]
            if pre_match_candidates:
                search_candidates = pre_match_candidates

        if today_match_count <= 0:
            same_state_candidates = []
            if current_total_games is not None and current_lp_score is not None:
                same_state_candidates = [
                    candidate
                    for candidate in search_candidates
                    if candidate.total_games is not None
                    and candidate.total_games == current_total_games
                    and candidate.score == current_lp_score
                ]
            if current_lp_score is not None and not same_state_candidates:
                same_state_candidates = [
                    candidate
                    for candidate in search_candidates
                    if candidate.observed_at >= start_of_day and candidate.score == current_lp_score
                ]
            if same_state_candidates:
                return max(same_state_candidates, key=_most_recent)
            return None

        expected_baseline_total = None
        if current_total_games is not None and today_match_count > 0:
            expected_baseline_total = max(0, current_total_games - today_match_count)

        if expected_baseline_total is not None:
            matching_game_count = [
                candidate
                for candidate in search_candidates
                if candidate.total_games is not None and candidate.total_games == expected_baseline_total
            ]
            if matching_game_count:
                return max(matching_game_count, key=_most_recent)

        same_day_candidates = [candidate for candidate in search_candidates if candidate.observed_at >= start_of_day]
        if same_day_candidates:
            return max(same_day_candidates, key=_most_recent)

        grace = timedelta(hours=TODAY_BASELINE_GRACE_HOURS)
        midnight_window_end = min(
            first_match_at if first_match_at is not None else now_local,
            start_of_day + grace,
        )
        near_midnight_candidates = [
            candidate
            for candidate in search_candidates
            if start_of_day - grace <= candidate.observed_at <= midnight_window_end
        ]
        if not near_midnight_candidates:
            return None

        near_midnight_candidates.sort(key=_closest_to_day_start)
        return near_midnight_candidates[0]

    @staticmethod
    def _with_cache_bust(url: str) -> str:
        parts = urlsplit(url)
        query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "_lolscout_refresh"]
        query.append(("_lolscout_refresh", str(int(time.time() * 1000))))
        return urlunsplit(parts._replace(query=urlencode(query)))

    @staticmethod
    def _is_leagueofgraphs_url(url: str) -> bool:
        return "leagueofgraphs.com" in urlsplit(url).netloc.casefold()

    @staticmethod
    def _browser_headers_for_url(url: str, force_refresh: bool = False) -> dict[str, str]:
        headers = dict(DEFAULT_BROWSER_HEADERS)
        host = urlsplit(url).netloc.casefold()
        if "leagueofgraphs.com" in host:
            headers.update(
                {
                    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Referer": "https://www.leagueofgraphs.com/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                }
            )
        elif "op.gg" in host:
            headers.update(
                {
                    "Accept-Language": "en-US,en;q=0.9,es-ES;q=0.8,es;q=0.7",
                    "Referer": "https://op.gg/",
                }
            )
        elif "u.gg" in host:
            headers.update(
                {
                    "Accept-Language": "en-US,en;q=0.9,es-ES;q=0.8,es;q=0.7",
                    "Referer": "https://u.gg/",
                }
            )
        if force_refresh:
            headers.update(
                {
                    "Cache-Control": "no-cache, no-store, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                }
            )
        return headers

    @staticmethod
    def _rate_limit_url(url: str) -> None:
        global _LEAGUEOFGRAPHS_LAST_REQUEST_AT
        if not ScrapingClient._is_leagueofgraphs_url(url):
            return

        with _LEAGUEOFGRAPHS_LOCK:
            now = time.monotonic()
            wait_seconds = _LEAGUEOFGRAPHS_LAST_REQUEST_AT + LEAGUEOFGRAPHS_MIN_INTERVAL_SECONDS - now
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            _LEAGUEOFGRAPHS_LAST_REQUEST_AT = time.monotonic()

    @staticmethod
    def _leagueofgraphs_blocked_seconds() -> float:
        if time.monotonic() >= _LEAGUEOFGRAPHS_BLOCKED_UNTIL:
            return 0.0
        return max(0.0, _LEAGUEOFGRAPHS_BLOCKED_UNTIL - time.monotonic())

    @staticmethod
    def _mark_leagueofgraphs_blocked() -> None:
        global _LEAGUEOFGRAPHS_BLOCKED_UNTIL
        with _LEAGUEOFGRAPHS_LOCK:
            _LEAGUEOFGRAPHS_BLOCKED_UNTIL = max(
                _LEAGUEOFGRAPHS_BLOCKED_UNTIL,
                time.monotonic() + LEAGUEOFGRAPHS_BLOCKED_BACKOFF_SECONDS,
            )

    @staticmethod
    def _clear_leagueofgraphs_blocked() -> None:
        global _LEAGUEOFGRAPHS_BLOCKED_UNTIL
        if _LEAGUEOFGRAPHS_BLOCKED_UNTIL <= 0:
            return
        with _LEAGUEOFGRAPHS_LOCK:
            _LEAGUEOFGRAPHS_BLOCKED_UNTIL = 0.0

    def _prime_leagueofgraphs_session(self) -> None:
        url = "https://www.leagueofgraphs.com/"
        try:
            self._rate_limit_url(url)
            self.session.get(
                url,
                headers=self._browser_headers_for_url(url),
                timeout=min(6, self.timeout),
            )
        except requests.RequestException:
            return

    def _get_text(
        self,
        url: str,
        context: str,
        headers: dict[str, str] | None = None,
        force_refresh: bool = False,
    ) -> str:
        request_headers = self._browser_headers_for_url(url, force_refresh=force_refresh)
        request_url = self._with_cache_bust(url) if force_refresh else url
        if headers:
            request_headers.update(headers)

        is_leagueofgraphs = self._is_leagueofgraphs_url(url)
        if is_leagueofgraphs and self._leagueofgraphs_blocked_seconds() > 0:
            raise ScrapingError(f"{context}: LeagueOfGraphs bloqueado temporalmente; usando fuentes alternativas.")
        max_attempts = 2 if is_leagueofgraphs else 1
        response: requests.Response | None = None
        for attempt in range(max_attempts):
            try:
                self._rate_limit_url(url)
                response = self.session.get(request_url, headers=request_headers, timeout=self.timeout)
            except requests.RequestException as exc:
                raise ScrapingError(f"{context}: no se pudo conectar: {exc}") from exc

            if is_leagueofgraphs and response.status_code in {403, 429} and attempt + 1 < max_attempts:
                self._prime_leagueofgraphs_session()
                time.sleep(0.8)
                continue
            break

        if response is None:
            raise ScrapingError(f"{context}: no se pudo conectar.")

        if response.status_code == 404:
            raise ScrapingError(f"{context}: jugador no encontrado.")
        if is_leagueofgraphs and response.status_code < 400:
            self._clear_leagueofgraphs_blocked()
        if is_leagueofgraphs and response.status_code in {403, 429}:
            self._mark_leagueofgraphs_blocked()
        if response.status_code >= 400:
            raise ScrapingError(f"{context}: error HTTP ({response.status_code}).")

        return response.text

    @staticmethod
    def _format_relative_played_at(played_at: datetime, now_local: datetime | None = None) -> str:
        current = now_local or app_now()
        delta_seconds = max(0, int((current - to_app_timezone(played_at)).total_seconds()))
        if delta_seconds < 45:
            return "Just now"
        if delta_seconds < 90:
            return "A minute ago"

        minutes = delta_seconds // 60
        if minutes < 60:
            return f"{minutes} min ago"
        if minutes < 120:
            return "An hour ago"

        hours = minutes // 60
        if hours < 24:
            return f"{hours} hrs ago"
        if hours < 48:
            return "Yesterday"

        days = hours // 24
        return f"{days} days ago"

    @staticmethod
    def _normalize_lookup_name(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip()).casefold()

    @staticmethod
    def _clean_html_text(value: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    @staticmethod
    def _normalize_champion_lookup(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", html.unescape(value))
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-z0-9]+", "", normalized.casefold())
        return normalized

    def _load_champion_id_lookup(self) -> dict[str, int]:
        global _CHAMPION_ID_LOOKUP_CACHE
        if _CHAMPION_ID_LOOKUP_CACHE is not None:
            return _CHAMPION_ID_LOOKUP_CACHE

        lookup: dict[str, int] = {}
        try:
            response = self.session.get(
                CDRAGON_CHAMPION_SUMMARY_URL,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            payload = []

        if isinstance(payload, list):
            for entry in payload:
                if not isinstance(entry, dict):
                    continue
                try:
                    champion_id = int(entry.get("id", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if champion_id <= 0:
                    continue
                for key in (entry.get("name"), entry.get("alias")):
                    normalized = self._normalize_champion_lookup(str(key or ""))
                    if normalized:
                        lookup[normalized] = champion_id

        _CHAMPION_ID_LOOKUP_CACHE = lookup
        return lookup

    def _champion_id_from_name(self, champion_name: str) -> int:
        return self._load_champion_id_lookup().get(self._normalize_champion_lookup(champion_name), 0)

    def _fill_champion_ids(self, champions: list[ChampionPlayStat]) -> list[ChampionPlayStat]:
        filled: list[ChampionPlayStat] = []
        for champion in champions:
            champion_id = champion.champion_id or self._champion_id_from_name(champion.champion)
            filled.append(
                ChampionPlayStat(
                    champion=champion.champion,
                    champion_id=champion_id,
                    games=champion.games,
                )
            )
        return filled

    @staticmethod
    def _normalize_role_text(value: str) -> str:
        cleaned = re.sub(r"[_\-/]+", " ", html.unescape(value)).strip().upper()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            return "UNKNOWN"

        direct = ROLE_ALIASES.get(cleaned)
        if direct:
            return direct

        compact = cleaned.replace(" ", "")
        direct = ROLE_ALIASES.get(compact)
        if direct:
            return direct

        token_map = (
            ("JUNGLE", "JUNGLE"),
            ("JGL", "JUNGLE"),
            ("JG", "JUNGLE"),
            ("MIDDLE", "MIDDLE"),
            ("MID", "MIDDLE"),
            ("BOTTOM", "BOTTOM"),
            ("BOT", "BOTTOM"),
            ("ADC", "BOTTOM"),
            ("SUPPORT", "UTILITY"),
            ("SUP", "UTILITY"),
            ("UTILITY", "UTILITY"),
            ("TOP", "TOP"),
        )
        tokens = set(cleaned.split())
        for token, normalized in token_map:
            if token in tokens:
                return normalized

        return "UNKNOWN"

    def _extract_live_role_from_porofessor(self, body: str) -> str:
        strong_role_patterns = (
            r'class="role-([a-z]+)-\d+',
            r'<div class="position">\s*([^<]+)\s*</div>',
            r'<div[^>]+class="[^"]*\bposition\b[^"]*"[^>]*>\s*([^<]+)\s*</div>',
            r'(?:data-role|data-position|data-lane)="([^"]+)"',
            r'icon-position-(top|jungle|middle|bottom|utility)',
        )

        for pattern in strong_role_patterns:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                for group in match.groups():
                    if not group:
                        continue
                    normalized = self._normalize_role_text(group)
                    if normalized != "UNKNOWN":
                        return normalized

        scoped_role_patterns = (
            r'\b(?:position|role|lane)\b[^>]{0,80}>\s*([^<]*(?:top|jungle|mid|middle|bottom|bot|adc|support|utility)[^<]*)<',
        )
        for pattern in scoped_role_patterns:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                for group in match.groups():
                    if not group:
                        continue
                    normalized = self._normalize_role_text(group)
                    if normalized != "UNKNOWN":
                        return normalized

        return "UNKNOWN"

    @staticmethod
    def _slug(game_name: str, tag_line: str) -> str:
        return quote_plus(f"{game_name}-{tag_line}")

    @staticmethod
    def _ugg_slug_candidates(game_name: str, tag_line: str) -> list[str]:
        compact_game_name = re.sub(r"\s+", "-", game_name.strip())
        compact_tag_line = re.sub(r"\s+", "-", tag_line.strip())
        return [
            quote_plus(f"{game_name}-{tag_line}").lower(),
            quote(f"{compact_game_name}-{compact_tag_line}", safe="-").lower(),
        ]

    @classmethod
    def build_opgg_profile_url(cls, platform: str, game_name: str, tag_line: str) -> str | None:
        opgg_region = PLATFORM_TO_OPGG_REGION.get(platform)
        if not opgg_region:
            return None
        return f"https://op.gg/lol/summoners/{opgg_region}/{cls._slug(game_name, tag_line)}"

    def _parse_opgg_rank_block(self, text: str, label: str, queue_type: str) -> dict | None:
        normalized_text = " ".join(text.split())
        primary_pattern = re.compile(
            rf"{re.escape(label)}\s+(?:(unranked)|([a-z]+)\s+([1-4]|IV|III|II|I)\s+(\d+)\s+LP)"
            rf"(?:\s+(\d+)\s*W\s+(\d+)\s*L)?",
            re.IGNORECASE,
        )
        match = primary_pattern.search(normalized_text)

        section = ""
        label_match = re.search(re.escape(label), normalized_text, re.IGNORECASE)
        if label_match:
            section = normalized_text[label_match.start():label_match.start() + 1200]

        if match and match.group(1):
            return None
        if not match and section and re.search(r"\bunranked\b", section, re.IGNORECASE):
            return None

        if match:
            tier_raw = match.group(2)
            rank_raw = match.group(3)
            lp_raw = match.group(4)
            wins_raw = match.group(5)
            losses_raw = match.group(6)
        else:
            rank_match = re.search(
                r"\b([a-z]+)\s+([1-4]|IV|III|II|I)\s+(\d+)\s+LP\b",
                section,
                re.IGNORECASE,
            )
            if not rank_match:
                return None
            tier_raw = rank_match.group(1)
            rank_raw = rank_match.group(2)
            lp_raw = rank_match.group(3)
            wins_losses_match = re.search(r"\b(\d+)\s*W\s+(\d+)\s*L\b", section, re.IGNORECASE)
            wins_raw = wins_losses_match.group(1) if wins_losses_match else None
            losses_raw = wins_losses_match.group(2) if wins_losses_match else None

        tier = TIER_ALIASES.get(tier_raw.lower())
        rank = DIVISION_ALIASES.get(rank_raw.upper(), rank_raw.upper())
        if not tier:
            return None

        winrate_source = section or normalized_text
        lp_anchor = re.search(r"\b\d+\s+LP\b", winrate_source, re.IGNORECASE)
        if lp_anchor:
            winrate_source = winrate_source[lp_anchor.end():]
        winrate_match = re.search(r"\b(\d+(?:\.\d+)?)\s*%\b", winrate_source)

        return {
            "queueType": queue_type,
            "tier": tier,
            "rank": rank,
            "leaguePoints": int(lp_raw),
            "wins": int(wins_raw or 0),
            "losses": int(losses_raw or 0),
            "winrate": float(winrate_match.group(1)) if winrate_match else None,
        }

    @staticmethod
    def _parse_opgg_action_payload(payload: str) -> dict | None:
        result: dict | None = None
        for line in payload.splitlines():
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            prefix, raw_json = stripped.split(":", 1)
            if not prefix.isdigit():
                continue
            raw_json = raw_json.strip()
            if not raw_json or raw_json.startswith("E{"):
                continue
            try:
                parsed = json.loads(raw_json)
            except ValueError:
                continue
            if isinstance(parsed, dict) and "status" in parsed:
                result = parsed
        return result

    def _post_opgg_action(
        self,
        url: str,
        action_id: str,
        params: dict[str, object],
        context: str,
    ) -> dict | None:
        request_headers = self._browser_headers_for_url(url, force_refresh=True)
        request_headers.update(
            {
                "Accept": "text/x-component",
                "Content-Type": "text/plain;charset=UTF-8",
                "next-action": action_id,
                "Origin": "https://op.gg",
                "Referer": url,
            }
        )
        try:
            response = self.session.post(
                url,
                headers=request_headers,
                data=json.dumps([params]),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ScrapingError(f"{context}: no se pudo conectar con OP.GG.") from exc

        if response.status_code >= 400:
            raise ScrapingError(f"{context}: error HTTP ({response.status_code}).")

        return self._parse_opgg_action_payload(response.text)

    @staticmethod
    def _extract_opgg_stream_value(page: str, key: str) -> str | None:
        patterns = (
            rf'"{re.escape(key)}":"([^"]+)"',
            rf'\\"{re.escape(key)}\\":\\"([^\\"]+)\\"',
        )
        for pattern in patterns:
            match = re.search(pattern, page)
            if match:
                return match.group(1)
        return None

    @classmethod
    def _extract_opgg_refresh_context(cls, page: str) -> tuple[str, str, str] | None:
        puuid = cls._extract_opgg_stream_value(page, "puuid")
        updated_at = cls._extract_opgg_stream_value(page, "initUpdatedAt") or cls._extract_opgg_stream_value(page, "updatedAt")
        renewable_at = cls._extract_opgg_stream_value(page, "initRenewableAt") or cls._extract_opgg_stream_value(page, "renewableAt")
        if not puuid or not updated_at or not renewable_at:
            return None
        return puuid, updated_at, renewable_at

    @staticmethod
    def _is_iso_datetime_due(value: str) -> bool:
        try:
            due_at = datetime.fromisoformat(value)
        except ValueError:
            return True
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        return due_at <= datetime.now(tz=due_at.tzinfo)

    @staticmethod
    def _iso_datetime_age_seconds(value: str) -> float | None:
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            return None
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return (datetime.now(tz=moment.tzinfo) - moment).total_seconds()

    def _should_refresh_opgg_profile(self, updated_at: str, renewable_at: str) -> bool:
        age_seconds = self._iso_datetime_age_seconds(updated_at)
        if age_seconds is None:
            return True
        return age_seconds >= OPGG_AUTO_RENEW_AGE_SECONDS or self._is_iso_datetime_due(renewable_at)

    def _refresh_opgg_profile(self, url: str, region: str, page: str) -> str:
        context = self._extract_opgg_refresh_context(page)
        if context is None:
            return page

        puuid, updated_at, renewable_at = context
        if not self._should_refresh_opgg_profile(updated_at, renewable_at):
            return page

        renew_data = self._post_opgg_action(
            url,
            "405a04669583947dc03eb8c7f367adf28c8f714e86",
            {"region": region, "puuid": puuid, "isPremiumPrimary": False},
            "OP.GG refresh",
        )
        if not renew_data:
            return page

        status = str(renew_data.get("status", "")).upper()
        deadline = datetime.now(timezone.utc).timestamp() + min(8, self.timeout)
        while status == "RENEWING" and datetime.now(timezone.utc).timestamp() < deadline:
            delay_ms = int(renew_data.get("delay", 1000) or 1000)
            time.sleep(max(0.25, min(delay_ms / 1000.0, 2.0)))
            renew_data = self._post_opgg_action(
                url,
                "400c02bdfd8c90756a329b312a7455e73880ad43ec",
                {"region": region, "puuid": puuid},
                "OP.GG refresh",
            )
            if not renew_data:
                break
            status = str(renew_data.get("status", "")).upper()

        if status not in {"RENEWAL_FINISH", "TOO_MANY_RENEWALS"}:
            return page
        return self._get_text(url, context="OP.GG perfil", force_refresh=True)

    def _load_opgg_profile_page(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        force_refresh: bool = False,
    ) -> str | None:
        opgg_region = PLATFORM_TO_OPGG_REGION.get(platform)
        if not opgg_region:
            return None

        url = f"https://op.gg/lol/summoners/{opgg_region}/{self._slug(game_name, tag_line)}"
        page = self._get_text(url, context="OP.GG perfil", force_refresh=force_refresh)
        if force_refresh:
            try:
                page = self._refresh_opgg_profile(url, opgg_region, page)
            except ScrapingError:
                pass
        return page

    def _parse_ranked_from_opgg_page(self, page: str) -> list[dict]:
        text = html.unescape(re.sub(r"<[^>]+>", " ", page))
        soloq = self._parse_opgg_rank_block(text, "Ranked Solo/Duo", "RANKED_SOLO_5x5")
        flex = self._parse_opgg_rank_block(text, "Ranked Flex", "RANKED_FLEX_SR")

        entries: list[dict] = []
        if soloq:
            entries.append(soloq)
        if flex:
            entries.append(flex)
        return entries

    def _load_profile_from_opgg(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        page: str | None = None,
        force_refresh: bool = False,
    ) -> ExternalProfile | None:
        opgg_page = (
            page
            if page is not None
            else self._load_opgg_profile_page(platform, game_name, tag_line, force_refresh=force_refresh)
        )
        if not opgg_page:
            return None

        text = html.unescape(re.sub(r"<[^>]+>", " ", opgg_page))
        normalized_text = " ".join(text.split())
        canonical_game_name = game_name
        canonical_tag_line = tag_line

        for pattern, source in (
            (r"<title>\s*([^#<]+)#([A-Za-z0-9]{2,6})\s+-", opgg_page),
            (r'"gameName"\s*:\s*"([^"]+)"\s*,\s*"tagline"\s*:\s*"([^"]+)"', opgg_page),
            (r'"game_name"\s*:\s*"([^"]+)"\s*,\s*"tagline"\s*:\s*"([^"]+)"', opgg_page),
            (r'"riotUserName"\s*:\s*"([^"]+)"\s*,\s*"riotTagLine"\s*:\s*"([^"]+)"', opgg_page),
            (r"\b([^#<>]{2,32})#([A-Za-z0-9]{2,6})\b", normalized_text),
        ):
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                candidate_name = self._clean_html_text(match.group(1))
                candidate_tag = self._clean_html_text(match.group(2))
                if (
                    candidate_name
                    and candidate_tag
                    and "theme-color" not in candidate_name.casefold()
                    and "=" not in candidate_name
                    and '"' not in candidate_name
                ):
                    canonical_game_name = candidate_name
                    canonical_tag_line = candidate_tag
                    break

        summoner_level = 0
        for pattern in (
            r'"summonerLevel"\s*:\s*(\d+)',
            r'"level"\s*:\s*(\d+)',
            r"\bLevel\s+(\d+)\b",
        ):
            match = re.search(pattern, opgg_page, re.IGNORECASE)
            if match:
                summoner_level = int(match.group(1))
                break

        profile_icon_id = 0
        icon_match = re.search(r"/profileicon/(\d+)\.png|profileIconId[\"']?\s*[:=]\s*(\d+)", opgg_page, re.IGNORECASE)
        if icon_match:
            profile_icon_id = int(icon_match.group(1) or icon_match.group(2) or 0)

        if summoner_level <= 0 and profile_icon_id <= 0 and not self._parse_ranked_from_opgg_page(opgg_page):
            return None

        return ExternalProfile(
            game_name=canonical_game_name,
            tag_line=canonical_tag_line,
            summoner_level=summoner_level,
            profile_icon_id=profile_icon_id,
            matches=[],
        )

    def _load_ranked_from_opgg(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        page: str | None = None,
        force_refresh: bool = False,
    ) -> list[dict]:
        opgg_page = (
            page
            if page is not None
            else self._load_opgg_profile_page(platform, game_name, tag_line, force_refresh=force_refresh)
        )
        if not opgg_page:
            return []
        return self._parse_ranked_from_opgg_page(opgg_page)

    def _load_winrate_from_ugg(self, platform: str, game_name: str, tag_line: str) -> float | None:
        ugg_region = PLATFORM_TO_UGG_REGION.get(platform)
        if not ugg_region:
            return None

        for slug in self._ugg_slug_candidates(game_name, tag_line):
            try:
                page = self._get_text(f"https://u.gg/lol/profile/{ugg_region}/{slug}/overview", context="U.GG perfil")
            except ScrapingError:
                continue

            text = html.unescape(re.sub(r"<[^>]+>", " ", page))
            normalized_text = " ".join(text.split())
            for pattern in (
                r"Ranked Solo(?:/Duo)?\s+.*?\b(\d+(?:\.\d+)?)%\s+Win Rate\b",
                r"Ranked Solo(?:/Duo)?\s+.*?\b(\d+(?:\.\d+)?)%\b",
            ):
                match = re.search(pattern, normalized_text, re.IGNORECASE)
                if match:
                    return float(match.group(1))
        return None

    @staticmethod
    def _extract_total_games(section: str) -> int | None:
        wins_losses_match = re.search(r"\b(\d+)\s*W\s+(\d+)\s*L\b", section, re.IGNORECASE)
        if wins_losses_match:
            return int(wins_losses_match.group(1)) + int(wins_losses_match.group(2))

        for pattern in (
            r"\b(\d+)\s+(?:Played|Games?|Matches)\b",
            r"\b(?:Played|Games?|Matches)\s+(\d+)\b",
        ):
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _load_games_from_opgg(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        entries: list[dict] | None = None,
    ) -> int | None:
        ranked_entries = entries if entries is not None else self._load_ranked_from_opgg(platform, game_name, tag_line)
        for entry in ranked_entries:
            queue_type = str(entry.get("queueType", "")).replace("x", "X").upper()
            if queue_type == "RANKED_SOLO_5X5" or (
                "RANKED" in queue_type and "SOLO" in queue_type and "FLEX" not in queue_type
            ):
                wins = int(entry.get("wins", 0))
                losses = int(entry.get("losses", 0))
                total_games = wins + losses
                if total_games > 0:
                    return total_games
        return None

    def _load_games_from_ugg(self, platform: str, game_name: str, tag_line: str) -> int | None:
        ugg_region = PLATFORM_TO_UGG_REGION.get(platform)
        if not ugg_region:
            return None

        for slug in self._ugg_slug_candidates(game_name, tag_line):
            try:
                page = self._get_text(f"https://u.gg/lol/profile/{ugg_region}/{slug}/overview", context="U.GG perfil")
            except ScrapingError:
                continue

            text = html.unescape(re.sub(r"<[^>]+>", " ", page))
            normalized_text = " ".join(text.split())
            patterns = (
                r"Overview Champion Stats Live Game Highlights Ranked Solo(?:/Duo)?\s+.*?(?:Ranked Flex|Your Highlights|Champion Stats|$)",
                r"Ranked Solo(?:/Duo)?\s+[A-Za-z]+\s+(?:[1-4]|IV|III|II|I)\s+\d+\s+LP.*?(?:Ranked Flex|Your Highlights|Champion Stats|$)",
            )
            for pattern in patterns:
                for match in re.finditer(pattern, normalized_text, re.IGNORECASE):
                    total_games = self._extract_total_games(match.group(0))
                    if total_games is not None:
                        return total_games

            total_games = self._extract_total_games(normalized_text)
            if total_games is not None:
                return total_games
        return None

    def _load_profile_from_ugg(self, platform: str, game_name: str, tag_line: str) -> ExternalProfile | None:
        ugg_region = PLATFORM_TO_UGG_REGION.get(platform)
        if not ugg_region:
            return None

        for slug in self._ugg_slug_candidates(game_name, tag_line):
            try:
                page = self._get_text(f"https://u.gg/lol/profile/{ugg_region}/{slug}/overview", context="U.GG perfil")
            except ScrapingError:
                continue

            canonical_game_name = game_name
            canonical_tag_line = tag_line
            summoner_level = 0
            profile_icon_id = 0

            state_match = re.search(
                r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\})\s*</script>",
                page,
                re.IGNORECASE | re.DOTALL,
            )
            if state_match:
                try:
                    state = json.loads(state_match.group(1))
                except json.JSONDecodeError:
                    state = None

                if isinstance(state, dict):
                    for key, value in state.items():
                        if not isinstance(key, str) or not key.startswith("profileInitSimple("):
                            continue
                        if not isinstance(value, dict):
                            continue
                        player_info = value.get("playerInfo")
                        if not isinstance(player_info, dict):
                            continue
                        summoner_level = int(player_info.get("summonerLevel", 0) or 0)
                        profile_icon_id = int(player_info.get("iconId", 0) or 0)
                        canonical_game_name = self._clean_html_text(
                            str(player_info.get("riotUserName") or canonical_game_name)
                        )
                        canonical_tag_line = self._clean_html_text(
                            str(player_info.get("riotTagLine") or canonical_tag_line)
                        )
                        break

            if summoner_level <= 0:
                level_match = re.search(
                    r'>\s*(\d+)\s*</div>\s*<div class="relative w-full h-full.*?Summoner profile icon',
                    page,
                    re.IGNORECASE | re.DOTALL,
                )
                if level_match:
                    summoner_level = int(level_match.group(1))

            if profile_icon_id <= 0:
                icon_match = re.search(r"/profileicon/(\d+)\.png", page, re.IGNORECASE)
                if icon_match:
                    profile_icon_id = int(icon_match.group(1))

            if summoner_level > 0 or profile_icon_id > 0:
                return ExternalProfile(
                    game_name=canonical_game_name,
                    tag_line=canonical_tag_line,
                    summoner_level=summoner_level,
                    profile_icon_id=profile_icon_id,
                    matches=[],
                )
        return None

    def _load_profile_from_leagueofgraphs(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        include_matches: bool = True,
        page: str | None = None,
        force_refresh: bool = False,
    ) -> ExternalProfile:
        region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
        if not region:
            raise ScrapingError("LeagueOfGraphs: plataforma no soportada.")

        url = f"https://www.leagueofgraphs.com/summoner/{region}/{self._slug(game_name, tag_line)}"
        source = page if page is not None else self._get_text(
            url,
            context="LeagueOfGraphs perfil",
            force_refresh=force_refresh,
        )

        title_match = re.search(r"<title>([^#<]+)#([^<(]+)\s*\(", source, re.IGNORECASE)
        canonical_game_name = self._clean_html_text(title_match.group(1)) if title_match else game_name
        canonical_tag_line = self._clean_html_text(title_match.group(2)) if title_match else tag_line

        level_match = re.search(
            r"\bbannerSubtitle\b[^>]*>\s*Level\s+(\d+)\b",
            source,
            re.IGNORECASE | re.DOTALL,
        )
        if not level_match:
            level_match = re.search(
                r">\s*Level\s+(\d+)\b",
                source,
                re.IGNORECASE,
            )
        icon_match = re.search(
            r'Summoner profile icon"\s*/?>|Summoner profile icon',
            source,
            re.IGNORECASE,
        )
        profile_icon_id = 0
        summoner_level = int(level_match.group(1)) if level_match else 0
        if icon_match:
            around_icon = source[max(0, icon_match.start() - 600):icon_match.end() + 600]
        else:
            around_icon = source
        icon_id_match = re.search(r"/profileicon/(\d+)\.png|/summonerIcons/[^/]+/\d+/(\d+)\.png", around_icon, re.IGNORECASE)
        if icon_id_match:
            profile_icon_id = int(icon_id_match.group(1) or icon_id_match.group(2) or 0)

        if summoner_level <= 0 or profile_icon_id <= 0:
            ugg_profile = self._load_profile_from_ugg(platform, canonical_game_name, canonical_tag_line)
            if ugg_profile is not None:
                if summoner_level <= 0:
                    summoner_level = ugg_profile.summoner_level
                if profile_icon_id <= 0:
                    profile_icon_id = ugg_profile.profile_icon_id
                if not title_match:
                    canonical_game_name = ugg_profile.game_name
                    canonical_tag_line = ugg_profile.tag_line

        matches = self._load_recent_matches_from_leagueofgraphs(source) if include_matches else []
        return ExternalProfile(
            game_name=canonical_game_name,
            tag_line=canonical_tag_line,
            summoner_level=summoner_level,
            profile_icon_id=profile_icon_id,
            matches=matches,
        )

    def _load_profile_with_fallbacks(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        include_matches: bool = False,
        force_refresh: bool = False,
    ) -> tuple[ExternalProfile, str | None, str | None]:
        league_page = None
        opgg_page = None
        last_error: ScrapingError | None = None
        tried_opgg = False
        tried_ugg = False

        def try_opgg_profile() -> ExternalProfile | None:
            nonlocal opgg_page, last_error, tried_opgg
            tried_opgg = True
            try:
                opgg_page = self._load_opgg_profile_page(platform, game_name, tag_line, force_refresh=force_refresh)
                return self._load_profile_from_opgg(
                    platform,
                    game_name,
                    tag_line,
                    page=opgg_page,
                    force_refresh=force_refresh,
                )
            except ScrapingError as exc:
                last_error = exc
                return None

        def try_ugg_profile() -> ExternalProfile | None:
            nonlocal tried_ugg
            tried_ugg = True
            return self._load_profile_from_ugg(platform, game_name, tag_line)

        if not include_matches:
            opgg_profile = try_opgg_profile()
            if opgg_profile is not None:
                return opgg_profile, None, opgg_page

            ugg_profile = try_ugg_profile()
            if ugg_profile is not None:
                return ugg_profile, None, opgg_page

        region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
        if region:
            try:
                league_page = self._get_text(
                    f"https://www.leagueofgraphs.com/summoner/{region}/{self._slug(game_name, tag_line)}",
                    context="LeagueOfGraphs perfil",
                    force_refresh=force_refresh,
                )
                return (
                    self._load_profile_from_leagueofgraphs(
                        platform,
                        game_name,
                        tag_line,
                        include_matches=include_matches,
                        page=league_page,
                        force_refresh=force_refresh,
                    ),
                    league_page,
                    None,
                )
            except ScrapingError as exc:
                last_error = exc

        if not tried_opgg:
            opgg_profile = try_opgg_profile()
            if opgg_profile is not None:
                return opgg_profile, None, opgg_page

        if not tried_ugg:
            ugg_profile = try_ugg_profile()
            if ugg_profile is not None:
                return ugg_profile, None, opgg_page

        if last_error is not None:
            raise last_error
        raise ScrapingError("No se pudo cargar el perfil desde las fuentes publicas.")

    @staticmethod
    def _parse_leagueofgraphs_relative_time(text: str, now_local: datetime | None = None) -> datetime | None:
        normalized = " ".join(str(text or "").casefold().split())
        if not normalized:
            return None

        current = now_local or app_now()
        if normalized in {"just now", "moments ago"}:
            return current
        if normalized in {"a minute ago", "an minute ago", "1 minute ago"}:
            return current - timedelta(minutes=1)
        if normalized in {"an hour ago", "a hour ago", "1 hour ago"}:
            return current - timedelta(hours=1)
        if normalized in {"a day ago", "1 day ago", "yesterday"}:
            return current - timedelta(days=1)

        for pattern, unit in (
            (r"(\d+)\s+seconds?\s+ago", "seconds"),
            (r"(\d+)\s+secs?\s+ago", "seconds"),
            (r"(\d+)\s+minutes?\s+ago", "minutes"),
            (r"(\d+)\s+mins?\s+ago", "minutes"),
            (r"(\d+)\s+hours?\s+ago", "hours"),
            (r"(\d+)\s+hrs?\s+ago", "hours"),
            (r"(\d+)\s+days?\s+ago", "days"),
        ):
            match = re.fullmatch(pattern, normalized)
            if not match:
                continue
            amount = int(match.group(1))
            return current - timedelta(**{unit: amount})
        return None

    def _load_recent_matches_from_leagueofgraphs(self, page: str) -> list[MatchSummary]:
        matches: list[MatchSummary] = []
        row_pattern = re.compile(r"<tr class=\"[^\"]*\">(.*?)</tr>", re.IGNORECASE | re.DOTALL)
        now_local = app_now()
        for row in row_pattern.findall(page):
            match_id_match = re.search(r"/match/[^/]+/(?P<match_id>\d+)#participant\d+", row, re.IGNORECASE)
            champion_id_match = re.search(r'class="champion-(?P<champion_id>\d+)-48\s+"', row, re.IGNORECASE)
            champion_name_match = re.search(r'alt="(?P<champion>[^"]+)"', row, re.IGNORECASE)
            result_match = re.search(r'<div class="victoryDefeatText (?P<result>victory|defeat|remade)">', row, re.IGNORECASE)
            queue_match = re.search(r'tooltip="(?P<queue>[^"]+)"', row, re.IGNORECASE)
            played_at_match = re.search(r'<div class="gameDate[^"]*"[^>]*>\s*(?P<date>[^<]+)\s*</div>', row, re.IGNORECASE)
            duration_match = re.search(r'<div class="gameDuration">\s*(?P<duration>\d+)min', row, re.IGNORECASE)
            kills_match = re.search(r'<span class="kills">(?P<kills>\d+)</span>', row, re.IGNORECASE)
            deaths_match = re.search(r'<span class="deaths">(?P<deaths>\d+)</span>', row, re.IGNORECASE)
            assists_match = re.search(r'<span class="assists">(?P<assists>\d+)</span>', row, re.IGNORECASE)
            cs_match = re.search(r'<div class="cs">\s*<span class="number">(?P<cs>\d+)</span>', row, re.IGNORECASE)

            if not (
                match_id_match
                and champion_id_match
                and champion_name_match
                and result_match
                and queue_match
                and duration_match
                and kills_match
                and deaths_match
                and assists_match
            ):
                continue

            kills = int(kills_match.group("kills"))
            deaths = int(deaths_match.group("deaths"))
            assists = int(assists_match.group("assists"))
            duration_min = max(1, int(duration_match.group("duration")))
            played_at_text = self._clean_html_text(played_at_match.group("date")) if played_at_match else ""
            played_at = self._parse_leagueofgraphs_relative_time(played_at_text, now_local=now_local)
            matches.append(
                MatchSummary(
                    match_id=match_id_match.group("match_id"),
                    champion=self._clean_html_text(champion_name_match.group("champion")),
                    champion_id=int(champion_id_match.group("champion_id")),
                    role="UNKNOWN",
                    queue_name=self._clean_html_text(queue_match.group("queue")),
                    won=result_match.group("result").lower() == "victory",
                    kills=kills,
                    deaths=deaths,
                    assists=assists,
                    cs=int(cs_match.group("cs")) if cs_match else 0,
                    duration_min=duration_min,
                    damage=0,
                    gold=0,
                    kda=round((kills + assists) / max(1, deaths), 2),
                    played_at_iso=played_at.isoformat() if played_at is not None else None,
                    played_at_text=played_at_text,
                )
            )
            if len(matches) >= MATCH_PAGE_SIZE:
                break
        return matches[:MAX_RECENT_MATCHES]

    def _load_today_matches_from_leagueofgraphs(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        force_refresh: bool = False,
    ) -> list[MatchSummary]:
        profile = self._load_profile_from_leagueofgraphs(
            platform,
            game_name,
            tag_line,
            include_matches=True,
            force_refresh=force_refresh,
        )
        now_local = app_now()
        start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        today_matches: list[MatchSummary] = []
        for match in profile.matches:
            if not match.played_at_iso:
                continue
            if not self._is_soloqueue_queue_name(match.queue_name):
                continue
            try:
                played_at = datetime.fromisoformat(match.played_at_iso)
            except ValueError:
                continue
            if played_at.tzinfo is None:
                played_at = played_at.replace(tzinfo=timezone.utc)
            if to_app_timezone(played_at) < start_of_day:
                continue
            today_matches.append(match)
        today_matches.sort(key=lambda match: match.played_at_iso or "", reverse=True)
        return today_matches

    def _load_leagueofgraphs_ranked(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        page: str | None = None,
        force_refresh: bool = False,
    ) -> list[dict]:
        region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
        if not region:
            return []

        url = f"https://www.leagueofgraphs.com/summoner/{region}/{self._slug(game_name, tag_line)}"
        source = page if page is not None else self._get_text(
            url,
            context="LeagueOfGraphs perfil",
            force_refresh=force_refresh,
        )
        entries: list[dict] = []
        patterns = (
            ("Ranked Solo/Duo", "RANKED_SOLO_5x5", r"Ranked Solo/Duo"),
            ("Ranked Flex", "RANKED_FLEX_SR", r"Ranked Flex"),
        )
        for label, queue_type, tooltip_label in patterns:
            pattern = re.compile(
                rf"<highlight>{tooltip_label}</highlight><br/>.*?player reached\s+([A-Za-z]+)\s+([IV]+)"
                rf".*?At the end of the season, this player was\s+([A-Za-z]+)\s+([IV]+)",
                re.IGNORECASE | re.DOTALL,
            )
            match = pattern.search(source)
            if match:
                tier = TIER_ALIASES.get(match.group(3).lower())
                rank = DIVISION_ALIASES.get(match.group(4).upper(), match.group(4).upper())
                if tier:
                    entries.append(
                        {
                            "queueType": queue_type,
                            "tier": tier,
                            "rank": rank,
                            "leaguePoints": 0,
                            "wins": 0,
                            "losses": 0,
                        }
                    )
                    continue

            summary_pattern = re.compile(
                rf"{tooltip_label}.*?([A-Za-z]+)\s+([IV]+).*?Wins:\s*(\d+)\s*\(([\d.]+)%\)",
                re.IGNORECASE | re.DOTALL,
            )
            summary_match = summary_pattern.search(source)
            if not summary_match:
                continue
            tier = TIER_ALIASES.get(summary_match.group(1).lower())
            rank = DIVISION_ALIASES.get(summary_match.group(2).upper(), summary_match.group(2).upper())
            wins = int(summary_match.group(3))
            winrate = float(summary_match.group(4))
            total_games = max(wins, round(wins / max(0.01, winrate / 100.0)))
            losses = max(0, total_games - wins)
            if tier:
                entries.append(
                    {
                        "queueType": queue_type,
                        "tier": tier,
                        "rank": rank,
                        "leaguePoints": 0,
                        "wins": wins,
                        "losses": losses,
                        "winrate": winrate,
                    }
                )
        return entries

    def _parse_leagueofgraphs_champion_table(self, page: str, limit: int | None = None) -> list[ChampionPlayStat]:
        table_match = re.search(
            r'<table class="data_table summoner_champions_details_table sortable_table">(.*?)</table>',
            page,
            re.IGNORECASE | re.DOTALL,
        )
        if not table_match:
            return []

        champions: list[ChampionPlayStat] = []
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
        for row in row_pattern.findall(table_match.group(1)):
            champion_id_match = re.search(r'class="champion-(?P<champion_id>\d+)-[\d-]*"', row, re.IGNORECASE)
            champion_name_match = re.search(r'alt="(?P<champion>[^"]+)"', row, re.IGNORECASE)
            played_match = re.search(r'<td[^>]+data-sort-value="(?P<played>\d+)"', row, re.IGNORECASE)
            if not champion_id_match or not champion_name_match or not played_match:
                continue
            champions.append(
                ChampionPlayStat(
                    champion=self._clean_html_text(champion_name_match.group("champion")),
                    champion_id=int(champion_id_match.group("champion_id")),
                    games=int(played_match.group("played")),
                )
            )
            if limit is not None and len(champions) >= limit:
                break
        return champions

    def _load_ranked_preferences_from_leagueofgraphs(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
    ) -> tuple[list[ChampionPlayStat], list[RolePlayStat]]:
        region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
        if not region:
            return [], []

        base_url = f"https://www.leagueofgraphs.com/summoner/champions/{region}/{self._slug(game_name, tag_line)}"
        champions_page = self._get_text(f"{base_url}/soloqueue", context="LeagueOfGraphs campeones SoloQ")
        leagueofgraphs_champions = self._parse_leagueofgraphs_champion_table(champions_page, limit=5)
        leagueofgraphs_icon_map = {
            self._normalize_champion_lookup(champion.champion): champion.champion_id
            for champion in self._parse_leagueofgraphs_champion_table(champions_page)
            if champion.champion_id > 0
        }

        opgg_champions = self._load_ranked_preferences_from_opgg(platform, game_name, tag_line)
        if opgg_champions:
            merged: list[ChampionPlayStat] = []
            for champion in opgg_champions:
                merged.append(
                    ChampionPlayStat(
                        champion=champion.champion,
                        champion_id=leagueofgraphs_icon_map.get(
                            self._normalize_champion_lookup(champion.champion),
                            champion.champion_id,
                        ),
                        games=champion.games,
                    )
                )
            return merged[:5], []

        return leagueofgraphs_champions, []

    def _load_ranking_champions_fast(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        force_refresh: bool = False,
        opgg_page: str | None = None,
    ) -> list[ChampionPlayStat]:
        try:
            opgg_champions = self._load_ranked_preferences_from_opgg(
                platform,
                game_name,
                tag_line,
                page=opgg_page,
            )[:5]
        except ScrapingError:
            opgg_champions = []
        if opgg_champions:
            return opgg_champions

        region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
        if not region:
            return []

        url = f"https://www.leagueofgraphs.com/summoner/champions/{region}/{self._slug(game_name, tag_line)}/soloqueue"
        try:
            page = self._get_text(
                url,
                context="LeagueOfGraphs campeones SoloQ",
                force_refresh=force_refresh,
            )
        except ScrapingError:
            page = ""
        champions = self._parse_leagueofgraphs_champion_table(page, limit=5) if page else []
        if champions:
            return champions
        return []

    def _parse_ranked_preferences_from_opgg_page(self, page: str) -> list[ChampionPlayStat]:
        description_match = re.search(
            r'<meta name="description" content="([^"]+)"',
            page,
            re.IGNORECASE,
        )
        if not description_match:
            return []

        description = html.unescape(description_match.group(1))
        entries = re.findall(r"([A-Za-z0-9' .:-]+?)\s*-\s*(\d+)Win\s+(\d+)Lose", description, re.IGNORECASE)
        champions: list[ChampionPlayStat] = []
        for champion_name, wins, losses in entries[:5]:
            cleaned_name = self._clean_html_text(champion_name)
            champions.append(
                ChampionPlayStat(
                    champion=cleaned_name,
                    champion_id=self._champion_id_from_name(cleaned_name),
                    games=int(wins) + int(losses),
                )
            )
        return champions

    def _load_ranked_preferences_from_opgg(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        page: str | None = None,
    ) -> list[ChampionPlayStat]:
        opgg_region = PLATFORM_TO_OPGG_REGION.get(platform)
        if not opgg_region:
            return []

        if page is not None:
            champions = self._parse_ranked_preferences_from_opgg_page(page)
            if champions:
                return champions

        url = f"https://op.gg/lol/summoners/{opgg_region}/{self._slug(game_name, tag_line)}?queue_type=SOLORANKED"
        return self._parse_ranked_preferences_from_opgg_page(
            self._get_text(url, context="OP.GG campeones SoloQ")
        )

    @staticmethod
    def _fallback_most_played_champions(matches: list[MatchSummary]) -> list[ChampionPlayStat]:
        champion_counts: dict[tuple[str, int], int] = {}
        for match in matches:
            queue_name = match.queue_name.casefold()
            if not any(label in queue_name for label in SOLOQUEUE_LABELS):
                continue
            key = (match.champion, match.champion_id)
            champion_counts[key] = champion_counts.get(key, 0) + 1
        ordered = sorted(champion_counts.items(), key=lambda item: (-item[1], item[0][0].casefold()))
        return [
            ChampionPlayStat(champion=champion, champion_id=champion_id, games=games)
            for (champion, champion_id), games in ordered[:5]
        ]

    @staticmethod
    def _fallback_most_played_roles(matches: list[MatchSummary]) -> list[RolePlayStat]:
        role_counts: dict[str, int] = {}
        for match in matches:
            role = match.role
            if role == "UNKNOWN":
                continue
            role_counts[role] = role_counts.get(role, 0) + 1
        ordered = sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))
        return [RolePlayStat(role=role, games=games) for role, games in ordered[:3]]

    @staticmethod
    def _is_soloqueue_queue_name(queue_name: str) -> bool:
        normalized = " ".join(str(queue_name or "").casefold().split())
        return any(label in normalized for label in SOLOQUEUE_LABELS)

    @staticmethod
    def _parse_porofessor_duration_minutes(source: str) -> int:
        duration_match = re.search(r'id="gameDuration"[^>]*>\((\d+):(\d+)\)', source)
        if not duration_match:
            return 0
        minutes = int(duration_match.group(1))
        seconds = int(duration_match.group(2))
        return minutes + (1 if seconds >= 30 else 0)

    @staticmethod
    def _infer_map_name_from_queue(queue_name: str) -> str:
        normalized = queue_name.lower()
        if "aram" in normalized:
            return "Howling Abyss"
        if "arena" in normalized:
            return "Arena"
        if "swarm" in normalized:
            return "Swarm"
        return "Summoner's Rift"

    def _load_live_game_from_porofessor(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
    ) -> LiveGameParticipantSummary | None:
        porofessor_region = PLATFORM_TO_POROFESSOR_REGION.get(platform)
        if not porofessor_region:
            return None

        slug = quote(f"{game_name}-{tag_line}", safe="-")
        url = f"https://porofessor.gg/partial/live-partial/{porofessor_region}/{slug}"
        headers = {"X-Requested-With": "XMLHttpRequest"}
        try:
            source = self._get_text(url, context="Porofessor partida en vivo", headers=headers)
        except ScrapingError:
            return None

        lowered = source.lower()
        canonical_game_name = game_name
        canonical_tag_line = tag_line
        if "the summoner is not in-game" in lowered:
            return LiveGameParticipantSummary(
                game_name=canonical_game_name,
                tag_line=canonical_tag_line,
                platform=platform,
                in_game=False,
                status_text="Fuera de partida",
            )
        if "summoner not found" in lowered:
            return LiveGameParticipantSummary(
                game_name=canonical_game_name,
                tag_line=canonical_tag_line,
                platform=platform,
                in_game=False,
                status_text="No se pudo consultar la fuente externa de partida en vivo",
            )

        queue_match = re.search(
            r'<h2[^>]*class="left relative"[^>]*>\s*(.*?)\s*<span[^>]*id="gameDuration"',
            source,
            re.IGNORECASE | re.DOTALL,
        )
        queue_name = self._clean_html_text(queue_match.group(1)) if queue_match else "Partida activa"
        duration_min = self._parse_porofessor_duration_minutes(source)

        target_key = self._normalize_lookup_name(f"{game_name}#{tag_line}")
        card_start_pattern = re.compile(
            r'<div class="card card-\d+" data-summonername="(?P<name>[^"]+)"[^>]*>',
            re.IGNORECASE,
        )
        card_starts = list(card_start_pattern.finditer(source))
        participants = self._parse_live_game_players_from_porofessor(source, card_starts)
        if not participants:
            return None

        selected_player = next(
            (
                participant
                for participant in participants
                if self._normalize_lookup_name(f"{participant.game_name}#{participant.tag_line}") == target_key
            ),
            None,
        )
        if selected_player is None:
            return LiveGameParticipantSummary(
                game_name=canonical_game_name,
                tag_line=canonical_tag_line,
                platform=platform,
                in_game=False,
                status_text="La fuente externa no encontro al jugador dentro de la partida",
            )

        canonical_game_name = selected_player.game_name
        canonical_tag_line = selected_player.tag_line
        team_size = sum(1 for participant in participants if participant.team_color == selected_player.team_color)
        enemy_team_size = sum(1 for participant in participants if participant.team_color != selected_player.team_color)
        queue_name = queue_name or "Partida activa"
        game = LiveGameSummary(
            queue_name=queue_name,
            game_mode=queue_name,
            map_name=self._infer_map_name_from_queue(queue_name),
            duration_min=duration_min,
            team_size=team_size,
            enemy_team_size=enemy_team_size,
        )
        status_parts = [
            game.queue_name,
            f"{game.duration_min} min" if game.duration_min > 0 else "Duracion N/D",
            game.map_name,
        ]

        return LiveGameParticipantSummary(
            game_name=canonical_game_name,
            tag_line=canonical_tag_line,
            platform=platform,
            in_game=True,
            champion=selected_player.champion or "",
            champion_id=selected_player.champion_id,
            mastery_level=selected_player.mastery_level,
            role=selected_player.role,
            game=game,
            status_text=" - ".join(status_parts),
            participants=copy.deepcopy(participants),
        )

    def _parse_live_game_players_from_porofessor(
        self,
        source: str,
        card_starts: list[re.Match[str]],
    ) -> list[LiveGamePlayerDetails]:
        participants: list[LiveGamePlayerDetails] = []
        for index, match in enumerate(card_starts):
            body_start = match.end()
            body_end = card_starts[index + 1].start() if index + 1 < len(card_starts) else len(source)
            body = source[body_start:body_end]

            raw_name = html.unescape(match.group("name")).strip()
            if "#" in raw_name:
                parsed_game_name, parsed_tag_line = [segment.strip() for segment in raw_name.split("#", 1)]
            else:
                parsed_game_name, parsed_tag_line = raw_name, ""

            team_match = re.search(r'<div class="cardHeader\s+(blue|red)"', body, re.IGNORECASE)
            team_color = team_match.group(1).lower() if team_match else "blue"
            champion_match = re.search(r'<img[^>]+class="champion[^"]*"[^>]+alt="([^"]+)"', body, re.IGNORECASE)
            champion_id_match = re.search(r'class="champion-(\d+)-', body, re.IGNORECASE)
            role = self._extract_live_role_from_porofessor(body)
            level_match = re.search(r"Summoner Level:\s*(\d+)", body, re.IGNORECASE)
            mastery_match = re.search(r"Mastery Level\s+(\d+)", body, re.IGNORECASE)

            title_match = re.search(
                r'<div class="title oneLiner">\s*(\d+(?:\.\d+)?)%\s*Win.*?<span class="subtitle">\((\d+)\s*Played\)</span>',
                body,
                re.IGNORECASE | re.DOTALL,
            )
            recent_winrate = float(title_match.group(1)) if title_match else None
            recent_games = int(title_match.group(2)) if title_match else None

            kda_match = re.search(
                r'<span class="kills">([\d.]+)</span>\s*/\s*<span class="deaths">([\d.]+)</span>\s*/\s*<span class="assists">([\d.]+)</span>',
                body,
                re.IGNORECASE | re.DOTALL,
            )
            avg_kda = ""
            if kda_match:
                avg_kda = f"{kda_match.group(1)} / {kda_match.group(2)} / {kda_match.group(3)}"

            champion_rank_match = re.search(r"Rank:\s*<a[^>]*>\s*(#[\d,]+)\s*</a>", body, re.IGNORECASE | re.DOTALL)
            spell_names = [
                self._clean_html_text(spell_name)
                for spell_name in re.findall(
                    r'<img[^>]+alt="([^"]+)"[^>]+class="[^"]*\bspell-\d+-16\b[^"]*"',
                    body,
                    re.IGNORECASE,
                )
            ]
            spell_ids = [
                int(spell_id)
                for spell_id in re.findall(
                    r'class="[^"]*\bspell-(\d+)-16\b[^"]*"',
                    body,
                    re.IGNORECASE,
                )
            ]
            tag_titles = [
                self._clean_html_text(tag_title)
                for tag_title in re.findall(
                    r"<itemname class='tagTitle [^']+'>([^<]+)</itemname>",
                    body,
                    re.IGNORECASE,
                )
            ]

            participants.append(
                LiveGamePlayerDetails(
                    game_name=parsed_game_name,
                    tag_line=parsed_tag_line,
                    team_color=team_color,
                    champion=self._clean_html_text(champion_match.group(1)) if champion_match else "",
                    champion_id=int(champion_id_match.group(1)) if champion_id_match else 0,
                    role=role,
                    summoner_level=int(level_match.group(1)) if level_match else 0,
                    recent_winrate=recent_winrate,
                    recent_games=recent_games,
                    avg_kda=avg_kda,
                    champion_rank=champion_rank_match.group(1) if champion_rank_match else None,
                    mastery_level=int(mastery_match.group(1)) if mastery_match else None,
                    spell_ids=spell_ids[:2],
                    spell_names=spell_names[:2],
                    tags=tag_titles[:5],
                )
            )
        return participants

    def _load_ranked_entries(self, platform: str, game_name: str, tag_line: str) -> tuple[list[dict], bool]:
        ranked_source_available = False
        try:
            entries = self._load_ranked_from_opgg(platform, game_name, tag_line)
            ranked_source_available = True
        except ScrapingError:
            entries = []
        if entries:
            return entries, True

        try:
            entries = self._load_leagueofgraphs_ranked(platform, game_name, tag_line)
            ranked_source_available = True
        except ScrapingError:
            entries = []
        if entries:
            return entries, True

        return [], ranked_source_available

    def _parse_ranked_entries(
        self,
        league_entries: list[dict],
    ) -> tuple[RankedEntry | None, RankedEntry | None, float | None, float | None]:
        soloq = None
        flex = None
        soloq_winrate = None
        flex_winrate = None
        for entry in league_entries:
            parsed = RankedEntry(
                queue_type=entry["queueType"],
                tier=entry.get("tier", ""),
                rank=entry.get("rank", ""),
                league_points=int(entry.get("leaguePoints", 0)),
                wins=int(entry.get("wins", 0)),
                losses=int(entry.get("losses", 0)),
            )
            normalized_queue = parsed.queue_type.replace("x", "X").upper()
            if normalized_queue == "RANKED_SOLO_5X5" or (
                "RANKED" in normalized_queue and "SOLO" in normalized_queue and "FLEX" not in normalized_queue
            ):
                soloq = parsed
                if entry.get("winrate") is not None:
                    soloq_winrate = float(entry["winrate"])
            elif normalized_queue == "RANKED_FLEX_SR":
                flex = parsed
                if entry.get("winrate") is not None:
                    flex_winrate = float(entry["winrate"])
        return soloq, flex, soloq_winrate, flex_winrate

    def _build_summary(
        self,
        profile: ExternalProfile,
        platform: str,
        league_entries: list[dict],
        ranked_available: bool,
        recent_winrate: float,
        include_matches: bool,
    ) -> PlayerSummary:
        soloq, flex, soloq_winrate, flex_winrate = self._parse_ranked_entries(league_entries)
        estimated_mmr = estimate_mmr(soloq, recent_winrate)
        global_winrate = None
        ranked_games = soloq.total_games if soloq and soloq.total_games > 0 else None

        if soloq_winrate is not None:
            global_winrate = round(soloq_winrate, 1)
        elif soloq and soloq.total_games > 0:
            global_winrate = round(soloq.winrate, 1)
        elif flex_winrate is not None:
            global_winrate = round(flex_winrate, 1)
        elif flex and flex.total_games > 0:
            global_winrate = round(flex.winrate, 1)
        else:
            try:
                ugg_winrate = self._load_winrate_from_ugg(platform, profile.game_name, profile.tag_line)
            except ScrapingError:
                ugg_winrate = None
            if ugg_winrate is not None:
                global_winrate = round(ugg_winrate, 1)

        if ranked_games is None:
            try:
                ranked_games = self._load_games_from_opgg(platform, profile.game_name, profile.tag_line)
            except ScrapingError:
                ranked_games = None
        if ranked_games is None:
            try:
                ranked_games = self._load_games_from_ugg(platform, profile.game_name, profile.tag_line)
            except ScrapingError:
                ranked_games = None

        most_played_champions: list[ChampionPlayStat] = []
        most_played_roles: list[RolePlayStat] = []
        try:
            most_played_champions, most_played_roles = self._load_ranked_preferences_from_leagueofgraphs(
                platform,
                profile.game_name,
                profile.tag_line,
            )
        except ScrapingError:
            most_played_champions, most_played_roles = [], []

        matches = profile.matches if include_matches else []
        if include_matches and not most_played_champions:
            most_played_champions = self._fallback_most_played_champions(matches)

        return PlayerSummary(
            game_name=profile.game_name,
            tag_line=profile.tag_line,
            summoner_level=profile.summoner_level,
            profile_icon_id=profile.profile_icon_id,
            platform=platform,
            opgg_url=self.build_opgg_profile_url(platform, profile.game_name, profile.tag_line),
            soloq=soloq,
            flex=flex,
            estimated_mmr=estimated_mmr,
            global_winrate=global_winrate,
            ranked_games=ranked_games,
            recent_winrate=recent_winrate,
            matches=copy.deepcopy(matches),
            most_played_champions=copy.deepcopy(most_played_champions),
            most_played_roles=copy.deepcopy(most_played_roles),
            ranked_available=ranked_available,
        )

    def fetch_player_overview(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
    ) -> PlayerSummary:
        profile, _, opgg_page = self._load_profile_with_fallbacks(
            platform,
            game_name,
            tag_line,
            include_matches=False,
        )
        league_entries, ranked_available = self._load_ranked_entries(platform, profile.game_name, profile.tag_line)
        if not league_entries and opgg_page:
            league_entries = self._parse_ranked_from_opgg_page(opgg_page)
            ranked_available = True
        return self._build_summary(
            profile=profile,
            platform=platform,
            league_entries=league_entries,
            ranked_available=ranked_available,
            recent_winrate=50.0,
            include_matches=False,
        )

    def fetch_player_ranking(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
        force_refresh: bool = False,
        store_today_snapshot: bool = True,
    ) -> PlayerSummary:
        cached = None if force_refresh else self._load_cached_ranking_summary(platform, game_name, tag_line)
        if cached is not None:
            cached.most_played_champions = self._fill_champion_ids(cached.most_played_champions)
            if cached.top_mastery_champion_id <= 0:
                cached.top_mastery_champion_id = next(
                    (champion.champion_id for champion in cached.most_played_champions if champion.champion_id > 0),
                    0,
                )
            return cached

        try:
            profile, league_page, opgg_page = self._load_profile_with_fallbacks(
                platform,
                game_name,
                tag_line,
                include_matches=False,
                force_refresh=force_refresh,
            )

            ranked_available = True
            league_entries = []
            if not league_entries:
                if opgg_page is None:
                    try:
                        opgg_page = self._load_opgg_profile_page(
                            platform,
                            profile.game_name,
                            profile.tag_line,
                            force_refresh=force_refresh,
                        )
                    except ScrapingError:
                        opgg_page = None
                league_entries = self._parse_ranked_from_opgg_page(opgg_page) if opgg_page else []
            if not league_entries:
                try:
                    league_entries = self._load_leagueofgraphs_ranked(
                        platform,
                        profile.game_name,
                        profile.tag_line,
                        page=league_page,
                        force_refresh=force_refresh,
                    )
                except ScrapingError:
                    league_entries = []

            soloq, flex, soloq_winrate, flex_winrate = self._parse_ranked_entries(league_entries)
            global_winrate = None
            if soloq_winrate is not None:
                global_winrate = round(soloq_winrate, 1)
            elif soloq and soloq.total_games > 0:
                global_winrate = round(soloq.winrate, 1)
            elif flex_winrate is not None:
                global_winrate = round(flex_winrate, 1)
            elif flex and flex.total_games > 0:
                global_winrate = round(flex.winrate, 1)

            ranked_games = soloq.total_games if soloq and soloq.total_games > 0 else None
            most_played_champions = self._load_ranking_champions_fast(
                platform,
                profile.game_name,
                profile.tag_line,
                force_refresh=force_refresh,
                opgg_page=opgg_page,
            )
            most_played_champions = self._fill_champion_ids(most_played_champions)
            if league_page is not None:
                mastery_champion_id, mastery_level, mastery_points = self._fetch_top_champion_mastery(
                    platform,
                    profile.game_name,
                    profile.tag_line,
                    page=league_page,
                )
            else:
                mastery_champion_id, mastery_level, mastery_points = 0, None, None
            if mastery_champion_id <= 0:
                mastery_champion_id = next(
                    (champion.champion_id for champion in most_played_champions if champion.champion_id > 0),
                    0,
                )
            summary = PlayerSummary(
                game_name=profile.game_name,
                tag_line=profile.tag_line,
                summoner_level=profile.summoner_level,
                profile_icon_id=profile.profile_icon_id,
                platform=platform,
                opgg_url=self.build_opgg_profile_url(platform, profile.game_name, profile.tag_line),
                soloq=soloq,
                flex=flex,
                estimated_mmr=estimate_mmr(soloq, global_winrate or 50.0),
                global_winrate=global_winrate,
                ranked_games=ranked_games,
                recent_winrate=0.0,
                matches=[],
                most_played_champions=most_played_champions,
                most_played_roles=[],
                ranked_available=ranked_available,
                top_mastery_champion_id=mastery_champion_id,
                top_mastery_level=mastery_level,
                top_mastery_points=mastery_points,
            )
            if store_today_snapshot:
                self._append_daily_lp_snapshot(summary, cache_game_name=game_name, cache_tag_line=tag_line)
            self._store_cached_ranking_summary(summary, cache_game_name=game_name, cache_tag_line=tag_line)
            return summary
        except ScrapingError:
            stale = self._load_cached_ranking_summary(platform, game_name, tag_line, max_age_seconds=None)
            if stale is not None:
                return stale
            raise

    def fetch_player_today_lp(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
        force_refresh: bool = False,
    ) -> TodayLpSummary:
        ranking_summary = self.fetch_player_ranking(
            game_name=game_name,
            tag_line=tag_line,
            platform=platform,
            force_refresh=force_refresh,
            store_today_snapshot=False,
        )
        current_rank_text = (
            ranking_summary.soloq.display_rank
            if ranking_summary.soloq is not None
            else ("Sin SoloQ" if ranking_summary.ranked_available else "Sin datos")
        )
        public_today_matches: list[MatchSummary] = []
        try:
            public_today_matches = self._load_today_matches_from_leagueofgraphs(
                platform,
                ranking_summary.game_name,
                ranking_summary.tag_line,
                force_refresh=force_refresh,
            )
        except ScrapingError:
            public_today_matches = []
        today_matches = public_today_matches
        display_today_matches = today_matches[:5]
        today_match_count = len(today_matches)
        current_lp_score = self._lp_score_from_ranked_entry(ranking_summary.soloq)
        if current_lp_score is None:
            return TodayLpSummary(
                player=ranking_summary,
                lp_change=None,
                current_lp_score=None,
                baseline_lp_score=None,
                current_rank_text=current_rank_text,
                baseline_rank_text="",
                baseline_local_time=None,
                baseline_source="",
                baseline_note="Sin datos de SoloQ para hoy.",
                today_matches=display_today_matches,
            )

        now_local = app_now()
        start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        candidates = self._load_daily_lp_snapshot_candidates(platform, game_name, tag_line)

        if (
            ranking_summary.game_name.casefold() != game_name.casefold()
            or ranking_summary.tag_line.casefold() != tag_line.casefold()
        ):
            candidates.extend(
                self._load_daily_lp_snapshot_candidates(
                    platform,
                    ranking_summary.game_name,
                    ranking_summary.tag_line,
                )
            )

        try:
            opgg_page = self._load_opgg_profile_page(
                platform,
                ranking_summary.game_name,
                ranking_summary.tag_line,
                force_refresh=force_refresh,
            )
        except ScrapingError:
            opgg_page = None
        if opgg_page:
            candidates.extend(self._build_today_candidates_from_opgg_page(opgg_page))

        first_match_at = None
        for match in today_matches:
            if not match.played_at_iso:
                continue
            try:
                played_at = datetime.fromisoformat(match.played_at_iso)
            except ValueError:
                continue
            if played_at.tzinfo is None:
                played_at = played_at.replace(tzinfo=timezone.utc)
            localized_played_at = to_app_timezone(played_at)
            if first_match_at is None or localized_played_at < first_match_at:
                first_match_at = localized_played_at

        baseline = self._select_today_baseline_candidate(
            candidates,
            start_of_day,
            now_local,
            first_match_at=first_match_at,
            current_total_games=ranking_summary.soloq.total_games if ranking_summary.soloq is not None else None,
            today_match_count=today_match_count,
            current_lp_score=current_lp_score,
        )
        self._append_daily_lp_snapshot(ranking_summary, cache_game_name=game_name, cache_tag_line=tag_line)

        if baseline is None:
            if today_match_count == 0:
                return TodayLpSummary(
                    player=ranking_summary,
                    lp_change=0,
                    current_lp_score=current_lp_score,
                    baseline_lp_score=current_lp_score,
                    current_rank_text=current_rank_text,
                    baseline_rank_text=current_rank_text,
                    baseline_local_time=now_local.strftime("%d %b %H:%M"),
                    baseline_source="Referencia actual",
                    baseline_note="Sin partidas detectadas hoy; se toma el LP actual como base.",
                    today_matches=display_today_matches,
                )
            return TodayLpSummary(
                player=ranking_summary,
                lp_change=None,
                current_lp_score=current_lp_score,
                baseline_lp_score=None,
                current_rank_text=current_rank_text,
                baseline_rank_text="",
                baseline_local_time=None,
                baseline_source="",
                baseline_note="Sin referencia historica cercana a las 00:00.",
                today_matches=display_today_matches,
            )

        baseline_local_time = baseline.observed_at.strftime("%d %b %H:%M")
        return TodayLpSummary(
            player=ranking_summary,
            lp_change=current_lp_score - baseline.score,
            current_lp_score=current_lp_score,
            baseline_lp_score=baseline.score,
            current_rank_text=current_rank_text,
            baseline_rank_text=baseline.rank_text,
            baseline_local_time=baseline_local_time,
            baseline_source=baseline.source,
            baseline_note=f"{baseline.source} {baseline_local_time}",
            today_matches=display_today_matches,
        )

    def fetch_cached_player_ranking(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
        max_age_seconds: int | None = None,
    ) -> PlayerSummary | None:
        return self._load_cached_ranking_summary(
            platform=platform,
            game_name=game_name,
            tag_line=tag_line,
            max_age_seconds=max_age_seconds,
        )

    def fetch_player_summary(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
    ) -> PlayerSummary:
        self._emit_progress("Cargando perfil externo...")
        profile, _, opgg_page = self._load_profile_with_fallbacks(
            platform,
            game_name,
            tag_line,
            include_matches=True,
        )
        self._emit_progress("Cargando ranked desde fuentes externas...")
        league_entries, ranked_available = self._load_ranked_entries(platform, profile.game_name, profile.tag_line)
        if not league_entries and opgg_page:
            league_entries = self._parse_ranked_from_opgg_page(opgg_page)
            ranked_available = True

        match_count = len(profile.matches)
        if match_count:
            self._emit_progress(f"Procesadas {match_count} partidas recientes.")
        else:
            self._emit_progress("No se encontraron partidas recientes en la fuente externa.")

        wins = sum(1 for match in profile.matches if match.won)
        recent_winrate = round((wins / max(1, len(profile.matches))) * 100, 1) if profile.matches else 0.0
        return self._build_summary(
            profile=profile,
            platform=platform,
            league_entries=league_entries,
            ranked_available=ranked_available,
            recent_winrate=recent_winrate,
            include_matches=True,
        )

    def fetch_live_game_summary(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
        fast_mode: bool = False,
    ) -> LiveGameParticipantSummary:
        del fast_mode
        direct_live = self._load_live_game_from_porofessor(
            platform=platform,
            game_name=game_name,
            tag_line=tag_line,
        )
        if direct_live is not None:
            return direct_live

        try:
            profile, _, _ = self._load_profile_with_fallbacks(
                platform,
                game_name,
                tag_line,
                include_matches=False,
            )
        except ScrapingError:
            return LiveGameParticipantSummary(
                game_name=game_name,
                tag_line=tag_line,
                platform=platform,
                in_game=False,
                mastery_level=None,
                status_text="No se pudo confirmar la partida con las fuentes publicas",
            )

        fallback = self._load_live_game_from_porofessor(
            platform=platform,
            game_name=profile.game_name,
            tag_line=profile.tag_line,
        )
        if fallback is not None:
            return fallback

        return LiveGameParticipantSummary(
            game_name=profile.game_name,
            tag_line=profile.tag_line,
            platform=platform,
            in_game=False,
            mastery_level=None,
            status_text="No se pudo confirmar la partida con las fuentes externas",
        )


def estimate_mmr(entry: RankedEntry | None, recent_winrate: float) -> int | None:
    if not entry or not entry.tier:
        return None

    base = TIER_BASE.get(entry.tier.upper(), 1000)
    division = RANK_OFFSET.get(entry.rank, 0)
    lp_factor = int(entry.league_points * 0.8)
    form_factor = int((recent_winrate - 50) * 6)
    return base + division + lp_factor + form_factor
