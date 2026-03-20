from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
import html
import json
import math
import os
from pathlib import Path
import random
import re
import tempfile
import sys
from threading import Lock, Thread
import requests

from PySide6.QtCore import QUrl
from PySide6.QtCore import QObject, QPointF, QRectF, QSize, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QRadialGradient
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig, load_config, save_config
from ..lolalytics import LolalyticsClient
from ..models import (
    LiveGameParticipantSummary,
    LiveGamePlayerDetails,
    LolalyticsAsset,
    LolalyticsBuildDetail,
    LolalyticsBuildSection,
    LolalyticsChampion,
    LolalyticsMatchup,
    LolalyticsSkillOrderRow,
    PlayerSummary,
    RankedEntry,
    SpectatorSession,
    TodayLpSummary,
)
from ..riot_api import RiotApiClient
from .theme import APP_STYLESHEET, build_palette


SETTINGS_USERNAME = "topon01"
SETTINGS_PASSWORD = "firewyvern01"


PLATFORMS = [
    "EUW1",
    "EUN1",
    "NA1",
    "KR",
    "BR1",
    "LA1",
    "LA2",
    "OC1",
    "TR1",
    "RU",
    "ME1",
]

RANKING_PLAYERS = [
    ("Dark Nøwel", "007"),
    ("guille016", "EUW"),
    ("EL TeT1T4S", "EUW"),
    ("Redsh19", "1971"),
    ("Daorru", "EUW"),
    ("BLEEEEEHH", "K1TTY"),
    ("HALLOOOOO", "K1TTY"),
    ("LUDA png", "EUW"),
    ("StephanieBullet", "EUW"),
    ("RoZaNiAs", "EUW"),
]

CHAMPION_ICON_SIZE = 56
ROLE_ICON_SIZE = 22
DETAIL_CHAMPION_ICON_SIZE = 44
DETAIL_ROLE_ICON_SIZE = 18
DETAIL_SPELL_ICON_SIZE = 18
DISCORD_AVATAR_SIZE = 52
OPGG_ICON_HEIGHT = 22
OPGG_ICON_WIDTH = 44
BUILDS_RESULT_ICON_SIZE = 46
BUILDS_MATCHUP_ICON_SIZE = 34
BUILDS_ASSET_ICON_SIZE = 34
BUILDS_RUNE_ICON_SIZE = 30
BUILDS_ITEM_ICON_SIZE = 40
BUILDS_OPTION_ICON_SIZE = 38
BUILDS_SKILL_ORDER_ICON_SIZE = 28
BUILDS_SKILL_ORDER_CELL_WIDTH = 18
BUILDS_SKILL_ORDER_CELL_HEIGHT = 28
BUILDS_INDEX_INITIAL_ICON_PREFETCH = 24
BUILDS_SEARCH_RENDER_BATCH_SIZE = 28
PLAYER_CARD_MIN_WIDTH = 228
PLAYER_CARD_ASPECT_RATIO = 1.54
TODAY_CARD_MIN_WIDTH = 288
TODAY_CARD_ASPECT_RATIO = 0.88
HOME_TAB_INDEX = 0
TODAY_TAB_INDEX = 1
RANKING_TAB_INDEX = 2
PLAYERS_TAB_INDEX = 3
LIVE_GAMES_TAB_INDEX = 4
BUILDS_TAB_INDEX = 5
SETTINGS_TAB_INDEX = 6
_CHAMPION_ICON_CACHE: dict[int, QPixmap] = {}
_CHAMPION_ICON_BYTES_CACHE: dict[int, bytes | None] = {}
_ROLE_ICON_CACHE: dict[str, QPixmap] = {}
_ROLE_ICON_BYTES_CACHE: dict[str, bytes | None] = {}
_SUMMONER_SPELL_ICON_CACHE: dict[int, QPixmap] = {}
_SUMMONER_SPELL_ICON_BYTES_CACHE: dict[int, bytes | None] = {}
_REMOTE_IMAGE_CACHE: dict[tuple[str, int], QPixmap] = {}
_REMOTE_COVER_CACHE: dict[tuple[str, int, int], QPixmap] = {}
_REMOTE_IMAGE_BYTES_CACHE: dict[str, bytes | None] = {}
_CHAMPION_DETAILS_CACHE: dict[int, dict | None] = {}
_FANDOM_LOADING_SCREEN_URL_CACHE: dict[str, str | None] = {}
_CHAMPION_NAME_CACHE: dict[int, str] = {}
_PLAYER_SHOWCASE_DATA_CACHE: dict[str, "PlayerShowcaseData"] = {}
_PLAYER_SHOWCASE_BACKGROUND_CACHE: dict[tuple[str, str, int, int, int], QPixmap] = {}
_TODAY_CARD_BACKGROUND_CACHE: dict[tuple[str, int, int], QPixmap] = {}
_TODAY_ELO_LOGO_CACHE: dict[tuple[str, int, int, str], QPixmap] = {}
_DISCORD_AVATAR_CACHE: dict[str, QPixmap] = {}
_DISCORD_AVATAR_BYTES_CACHE: dict[str, bytes | None] = {}
_OPGG_ICON_CACHE: QPixmap | None = None
_APP_LOGO_CACHE: dict[int, QPixmap] = {}
_LEADER_CROWN_CACHE: dict[tuple[int, int], QPixmap] = {}
_HOME_HERO_CACHE: dict[tuple[str, int, int], QPixmap] = {}
_HOME_ACTION_ICON_CACHE: dict[tuple[str, int], QPixmap] = {}
_DISCORD_USER_MAP: dict[str, str] | None = None
_ASSET_CACHE_LOCK = Lock()
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BUNDLED_ROOT = Path(getattr(sys, "_MEIPASS", _PROJECT_ROOT))
_UI_ROOT = Path(__file__).resolve().parent
_OPGG_ICON_PATHS = (
    _UI_ROOT / "img" / "op-gg.webp",
    _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img" / "op-gg.webp",
    _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img" / "op-gg.webp",
    _BUNDLED_ROOT / "ui" / "img" / "op-gg.webp",
)
_APP_LOGO_PATHS = (
    _UI_ROOT / "img" / "mmr-logo-app.png",
    _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img" / "mmr-logo-app.png",
    _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img" / "mmr-logo-app.png",
    _BUNDLED_ROOT / "ui" / "img" / "mmr-logo-app.png",
    _UI_ROOT / "img" / "mmr-logo.png",
    _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img" / "mmr-logo.png",
    _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img" / "mmr-logo.png",
    _BUNDLED_ROOT / "ui" / "img" / "mmr-logo.png",
)
_ELO_LOGO_DIRS = (
    _UI_ROOT / "img" / "elo",
    _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img" / "elo",
    _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img" / "elo",
    _BUNDLED_ROOT / "ui" / "img" / "elo",
)
_ELO_TIER_ASSET_ALIASES = {
    "EMERALD": ("emerald", "esmeralda", "platinum"),
}
_HOME_HERO_GLOB_PATTERNS = (
    "home-hero-*.jpg",
    "home-hero-*.jpeg",
    "home-hero-*.png",
    "home-hero-*.webp",
)
_HOME_HERO_DIRS = (
    _UI_ROOT / "img",
    _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img",
    _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img",
    _BUNDLED_ROOT / "ui" / "img",
)
_HOME_HERO_SELECTED_SOURCE: Path | None = None
_HOME_ACTION_ICON_PATHS = {
    "ranking": (
        _UI_ROOT / "img" / "home-action-ranking.png",
        _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img" / "home-action-ranking.png",
        _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img" / "home-action-ranking.png",
        _BUNDLED_ROOT / "ui" / "img" / "home-action-ranking.png",
    ),
    "builds": (
        _UI_ROOT / "img" / "home-action-builds.png",
        _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img" / "home-action-builds.png",
        _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img" / "home-action-builds.png",
        _BUNDLED_ROOT / "ui" / "img" / "home-action-builds.png",
    ),
    "live": (
        _UI_ROOT / "img" / "home-action-live.png",
        _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img" / "home-action-live.png",
        _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img" / "home-action-live.png",
        _BUNDLED_ROOT / "ui" / "img" / "home-action-live.png",
    ),
}
_DISCORD_USER_MAP_PATHS = (
    Path.cwd() / "userdc_id.json",
    _PROJECT_ROOT / "userdc_id.json",
    _BUNDLED_ROOT / "userdc_id.json",
)
_DISCORD_AVATAR_DIRS = (
    Path.cwd() / "discord_avatars",
    _PROJECT_ROOT / "discord_avatars",
    _BUNDLED_ROOT / "discord_avatars",
)
_DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
_DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "").strip()
ROLE_ICON_URLS = {
    "TOP": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-top.png",
    "JUNGLE": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-jungle.png",
    "MIDDLE": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-middle.png",
    "BOTTOM": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-bottom.png",
    "UTILITY": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-utility.png",
}
SUMMONER_SPELL_ICON_FILES = {
    1: "SummonerBoost.png",
    3: "SummonerExhaust.png",
    4: "SummonerFlash.png",
    6: "SummonerHaste.png",
    7: "SummonerHeal.png",
    11: "SummonerSmite.png",
    12: "SummonerTeleport.png",
    13: "SummonerMana.png",
    14: "SummonerDot.png",
    21: "SummonerBarrier.png",
    30: "SummonerPoroRecall.png",
    31: "SummonerPoroThrow.png",
    32: "SummonerSnowball.png",
    39: "SummonerSnowURFSnowball_Mark.png",
    54: "Summoner_UltBookPlaceholder.png",
    55: "Summoner_UltBookSmitePlaceholder.png",
    2201: "SummonerCherryHold.png",
    2202: "SummonerCherryFlash.png",
}
RANK_TIER_SCORE = {
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
RANK_DIVISION_SCORE = {"IV": 0, "III": 100, "II": 200, "I": 300}
SOLOQ_TIER_COLORS = {
    "IRON": "#7b848f",
    "BRONZE": "#b97b55",
    "SILVER": "#adb9c8",
    "GOLD": "#d8b45d",
    "PLATINUM": "#438eae",
    "EMERALD": "#5dd296",
    "DIAMOND": "#7b8cff",
    "MASTER": "#c36ee6",
    "GRANDMASTER": "#e16b7b",
    "CHALLENGER": "#58c4f6",
}
ROLE_DISPLAY_NAMES = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLA",
    "MIDDLE": "MID",
    "BOTTOM": "ADC",
    "UTILITY": "SUPPORT",
}
LIVE_ROLE_ORDER = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")
LIVE_ROLE_PRIORITY = {role: index for index, role in enumerate(LIVE_ROLE_ORDER)}
PREFERRED_LOADING_SKINS = {
    "syndra": "SKT T1 Syndra",
    "vayne": "Firecracker Vayne Prestige Edition",
}
PREFERRED_PLAYER_LOADING_SKINS = {
    "guille016#euw": "Empyrean Akali",
    "daorru#euw": "Nurse Akali",
    "bleeeeehh#k1tty": "Inkshadow Kai'Sa",
    "hallooooo#k1tty": "Chosen of the Wolf Katarina",
    "luda png#euw": "Blood Moon Aatrox",
    "ludapng#euw": "Blood Moon Aatrox",
    "rozanias#euw": "Battle Queen Katarina",
    "eltet1t4s#euw": "Dragon Master Swain",
    "redsh19#1971": "Spirit Blossom Sett",
}


def _live_role_display_name(role: str) -> str:
    if role in ROLE_DISPLAY_NAMES:
        return ROLE_DISPLAY_NAMES[role]
    return "SIN ROL" if role == "UNKNOWN" else role


def _player_lookup_key(game_name: str, tag_line: str) -> str:
    return f"{game_name}#{tag_line}".casefold()


def _live_team_slots(
    participants: list[LiveGamePlayerDetails],
) -> list[tuple[str, LiveGamePlayerDetails | None]]:
    sorted_participants = sorted(
        participants,
        key=lambda participant: (
            LIVE_ROLE_PRIORITY.get(participant.role, len(LIVE_ROLE_ORDER)),
            participant.game_name.casefold(),
            participant.tag_line.casefold(),
        ),
    )
    role_buckets: dict[str, list[LiveGamePlayerDetails]] = {role: [] for role in LIVE_ROLE_ORDER}
    extras: list[LiveGamePlayerDetails] = []

    for participant in sorted_participants:
        if participant.role in role_buckets:
            role_buckets[participant.role].append(participant)
        else:
            extras.append(participant)

    slots: list[tuple[str, LiveGamePlayerDetails | None]] = []
    for role in LIVE_ROLE_ORDER:
        if role_buckets[role]:
            slots.append((role, role_buckets[role].pop(0)))
        else:
            slots.append((role, None))

    for role in LIVE_ROLE_ORDER:
        extras.extend(role_buckets[role])

    extras.sort(
        key=lambda participant: (
            participant.role.casefold(),
            participant.game_name.casefold(),
            participant.tag_line.casefold(),
        )
    )
    slots.extend((participant.role or "UNKNOWN", participant) for participant in extras)
    return slots


@dataclass(frozen=True)
class PlayerShowcaseData:
    featured_champion_id: int
    featured_name: str
    preferred_skin: str
    art_url: str | None


def _prefetch_player_visual_assets(summaries: list[PlayerSummary]) -> None:
    tasks: list[tuple[str, object]] = []
    seen_champions: set[int] = set()
    seen_champion_loadscreens: set[int] = set()
    seen_players: set[str] = set()

    for summary in summaries:
        lookup_key = f"{summary.game_name}#{summary.tag_line}".casefold()
        if lookup_key not in seen_players:
            seen_players.add(lookup_key)
            tasks.append(("discord", summary))
        for champion in summary.most_played_champions:
            if champion.champion_id > 0 and champion.champion_id not in seen_champions:
                seen_champions.add(champion.champion_id)
                tasks.append(("champion", champion.champion_id))
        featured_champion_id = _featured_champion_id(summary)
        if featured_champion_id > 0 and featured_champion_id not in seen_champion_loadscreens:
            champion_name = _get_champion_display_name(featured_champion_id)
            if champion_name:
                seen_champion_loadscreens.add(featured_champion_id)
                preferred_skin = _get_player_loading_skin(summary, champion_name)
                tasks.append(("champion_loadscreen", (champion_name, preferred_skin, featured_champion_id)))

    if not tasks:
        return

    with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
        futures = []
        for task_type, payload in tasks:
            if task_type == "discord":
                futures.append(executor.submit(_prefetch_discord_avatar, payload))
            elif task_type == "champion":
                futures.append(executor.submit(_prefetch_champion_icon, payload))
            elif task_type == "champion_loadscreen":
                champion_name, preferred_skin, champion_id = payload
                futures.append(
                    executor.submit(_prefetch_champion_loading_screen, champion_name, preferred_skin, champion_id)
                )
        for future in as_completed(futures):
            future.result()


class RankingWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, api_key: str, platform: str, players: list[tuple[str, str]], force_refresh: bool = False) -> None:
        super().__init__()
        self.api_key = api_key
        self.platform = platform
        self.players = players
        self.force_refresh = force_refresh

    def _fetch_ranking_player(self, game_name: str, tag_line: str) -> PlayerSummary:
        client = RiotApiClient(self.api_key, timeout=12)
        try:
            return client.fetch_player_ranking(
                game_name=game_name,
                tag_line=tag_line,
                platform=self.platform,
                force_refresh=self.force_refresh,
            )
        except Exception:
            return PlayerSummary(
                game_name=game_name,
                tag_line=tag_line,
                summoner_level=0,
                profile_icon_id=0,
                platform=self.platform,
                ranked_available=False,
            )

    def run(self) -> None:
        try:
            total = len(self.players)
            if total == 0:
                self.finished.emit([])
                return

            summaries: list[PlayerSummary | None] = [None] * total
            max_workers = min(6, total)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(self._fetch_ranking_player, game_name, tag_line): (index, game_name, tag_line)
                    for index, (game_name, tag_line) in enumerate(self.players)
                }
                completed = 0
                for future in as_completed(future_map):
                    index, game_name, tag_line = future_map[future]
                    completed += 1
                    self.progress.emit(f"Cargando ranking {completed}/{total}: {game_name}#{tag_line}")
                    summaries[index] = future.result()
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Fallo inesperado: {exc}")
            return

        resolved_summaries = [summary for summary in summaries if summary is not None]
        self.progress.emit("Descargando iconos del ranking...")
        _prefetch_player_visual_assets(resolved_summaries)
        self.progress.emit("Procesando ranking...")
        self.finished.emit(resolved_summaries)


class TodayLpWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, api_key: str, platform: str, players: list[tuple[str, str]], force_refresh: bool = False) -> None:
        super().__init__()
        self.api_key = api_key
        self.platform = platform
        self.players = players
        self.force_refresh = force_refresh

    def _fetch_today_player(self, game_name: str, tag_line: str) -> TodayLpSummary:
        client = RiotApiClient(self.api_key, timeout=12)
        try:
            return client.fetch_player_today_lp(
                game_name=game_name,
                tag_line=tag_line,
                platform=self.platform,
                force_refresh=self.force_refresh,
            )
        except Exception as exc:
            return TodayLpSummary(
                player=PlayerSummary(
                    game_name=game_name,
                    tag_line=tag_line,
                    summoner_level=0,
                    profile_icon_id=0,
                    platform=self.platform,
                    ranked_available=False,
                ),
                current_rank_text="No disponible",
                baseline_note=f"No se pudo calcular hoy: {exc}",
            )

    def run(self) -> None:
        try:
            total = len(self.players)
            if total == 0:
                self.finished.emit([])
                return

            summaries: list[TodayLpSummary | None] = [None] * total
            with ThreadPoolExecutor(max_workers=min(4, total)) as executor:
                future_map = {
                    executor.submit(self._fetch_today_player, game_name, tag_line): (index, game_name, tag_line)
                    for index, (game_name, tag_line) in enumerate(self.players)
                }
                completed = 0
                for future in as_completed(future_map):
                    index, game_name, tag_line = future_map[future]
                    completed += 1
                    self.progress.emit(f"Calculando hoy {completed}/{total}: {game_name}#{tag_line}")
                    summaries[index] = future.result()
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Fallo inesperado: {exc}")
            return

        resolved_summaries = [summary for summary in summaries if summary is not None]
        players = [summary.player for summary in resolved_summaries]
        self.progress.emit("Preparando tarjetas de hoy...")
        _prefetch_player_visual_assets(players)
        self.finished.emit(resolved_summaries)


class LiveGameWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, api_key: str, platform: str, players: list[tuple[str, str]]) -> None:
        super().__init__()
        self.api_key = api_key
        self.platform = platform
        self.players = players

    def _fetch_live_player(self, game_name: str, tag_line: str) -> LiveGameParticipantSummary:
        client = RiotApiClient(self.api_key, timeout=12)
        try:
            return client.fetch_live_game_summary(
                game_name=game_name,
                tag_line=tag_line,
                platform=self.platform,
            )
        except Exception as exc:
            return LiveGameParticipantSummary(
                game_name=game_name,
                tag_line=tag_line,
                platform=self.platform,
                in_game=False,
                status_text=f"Error: {exc}",
            )

    def _prefetch_assets(self, summaries: list[LiveGameParticipantSummary]) -> None:
        tasks: list[tuple[str, object]] = []
        seen_champions: set[int] = set()
        seen_roles: set[str] = set()
        seen_spells: set[int] = set()

        for summary in summaries:
            if summary.champion_id > 0 and summary.champion_id not in seen_champions:
                seen_champions.add(summary.champion_id)
                tasks.append(("champion", summary.champion_id))
            if summary.role and summary.role not in seen_roles:
                seen_roles.add(summary.role)
                tasks.append(("role", summary.role))
            for participant in summary.participants:
                if participant.champion_id > 0 and participant.champion_id not in seen_champions:
                    seen_champions.add(participant.champion_id)
                    tasks.append(("champion", participant.champion_id))
                if participant.role and participant.role not in seen_roles:
                    seen_roles.add(participant.role)
                    tasks.append(("role", participant.role))
                for spell_id in participant.spell_ids:
                    if spell_id > 0 and spell_id not in seen_spells:
                        seen_spells.add(spell_id)
                        tasks.append(("spell", spell_id))

        if not tasks:
            return

        with ThreadPoolExecutor(max_workers=min(10, len(tasks))) as executor:
            futures = []
            for task_type, payload in tasks:
                if task_type == "champion":
                    futures.append(executor.submit(_prefetch_champion_icon, payload))
                elif task_type == "role":
                    futures.append(executor.submit(_prefetch_role_icon, payload))
                elif task_type == "spell":
                    futures.append(executor.submit(_prefetch_summoner_spell_icon, payload))
            for future in as_completed(futures):
                future.result()

    def run(self) -> None:
        try:
            total = len(self.players)
            if total == 0:
                self.finished.emit([])
                return

            summaries: list[LiveGameParticipantSummary | None] = [None] * total
            max_workers = min(2, total)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(self._fetch_live_player, game_name, tag_line): (index, game_name, tag_line)
                    for index, (game_name, tag_line) in enumerate(self.players)
                }
                completed = 0
                for future in as_completed(future_map):
                    index, game_name, tag_line = future_map[future]
                    completed += 1
                    self.progress.emit(f"Consultando partida {completed}/{total}: {game_name}#{tag_line}")
                    summaries[index] = future.result()
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Fallo inesperado: {exc}")
            return

        resolved_summaries = [summary for summary in summaries if summary is not None]
        self.progress.emit("Descargando iconos de partidas...")
        self._prefetch_assets(resolved_summaries)
        self.progress.emit("Procesando partidas activas...")
        self.finished.emit(resolved_summaries)


class BuildsIndexWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, force_refresh: bool = False) -> None:
        super().__init__()
        self.force_refresh = force_refresh

    @staticmethod
    def _prefetch_assets(champions: list[LolalyticsChampion]) -> None:
        icon_urls = []
        seen_urls: set[str] = set()
        for champion in champions:
            if champion.icon_url and champion.icon_url not in seen_urls:
                seen_urls.add(champion.icon_url)
                icon_urls.append(champion.icon_url)

        if not icon_urls:
            return

        with ThreadPoolExecutor(max_workers=min(4, len(icon_urls))) as executor:
            futures = [executor.submit(_prefetch_remote_image, url) for url in icon_urls]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    continue

    def run(self) -> None:
        self.progress.emit("Cargando catálogo de campeones...")
        try:
            champions = LolalyticsClient(timeout=16).fetch_champion_index(force_refresh=self.force_refresh)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"No se pudo cargar el catálogo de Builds: {exc}")
            return
        if champions:
            self.progress.emit("Preparando primeros campeones...")
            self._prefetch_assets(champions[:BUILDS_INDEX_INITIAL_ICON_PREFETCH])
        self.finished.emit(champions)


class BuildDetailWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, champion: LolalyticsChampion, force_refresh: bool = False) -> None:
        super().__init__()
        self.champion = champion
        self.force_refresh = force_refresh

    @staticmethod
    def _prefetch_assets(detail: LolalyticsBuildDetail) -> None:
        urls = []
        seen_urls: set[str] = set()

        def add_url(url: str | None) -> None:
            if url and url not in seen_urls:
                seen_urls.add(url)
                urls.append(url)

        def add_assets(assets: list[LolalyticsAsset]) -> None:
            for asset in assets:
                add_url(asset.icon_url)

        add_url(detail.icon_url)
        add_assets(detail.skill_priority)
        for row in detail.skill_order:
            add_url(row.skill.icon_url)
        add_assets(detail.summoner_spells)
        add_assets(detail.primary_runes)
        add_assets(detail.secondary_runes)
        for section in [detail.starting_items, detail.core_build]:
            if section is not None:
                add_assets(section.items)
        for sections in [detail.item_four, detail.item_five, detail.item_six]:
            for section in sections:
                add_assets(section.items)
        for url in [detail.icon_url] + [
            _lolalytics_champion_icon_url(matchup.slug)
            for matchup in [*detail.best_matchups, *detail.worst_matchups]
        ]:
            add_url(url)

        if not urls:
            return

        with ThreadPoolExecutor(max_workers=min(4, len(urls))) as executor:
            futures = [executor.submit(_prefetch_remote_image, url) for url in urls]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    continue

    def run(self) -> None:
        self.progress.emit(f"Cargando build de {self.champion.name}...")
        try:
            detail = LolalyticsClient(timeout=18).fetch_build_detail(
                self.champion.slug,
                force_refresh=self.force_refresh,
            )
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"No se pudo cargar la build de {self.champion.name}: {exc}")
            return

        self.progress.emit(f"Descargando assets de {self.champion.name}...")
        self._prefetch_assets(detail)
        self.finished.emit(detail)


class StatCard(QFrame):
    def __init__(
        self,
        label: str,
        value: str,
        accent: str = "#54d2a0",
        style_variant: str = "default",
    ) -> None:
        super().__init__()

        if style_variant == "ranking":
            self.setObjectName("RankingStatCard")
            value_object_name = "RankingStatValue"
            label_object_name = "RankingStatLabel"
            margins = (14, 12, 14, 12)
            spacing = 4
            self.setMinimumWidth(132)
        else:
            self.setObjectName("Card")
            value_object_name = "StatValue"
            label_object_name = "StatLabel"
            margins = (18, 16, 18, 16)
            spacing = 6

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*margins)
        layout.setSpacing(spacing)

        value_label = QLabel(value)
        value_label.setObjectName(value_object_name)
        value_label.setStyleSheet(f"color: {accent};")
        value_label.setWordWrap(True)
        text_label = QLabel(label)
        text_label.setObjectName(label_object_name)
        text_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(text_label)


class LoaderSpinner(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rotation_degrees = 0.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

        self.setFixedSize(112, 112)

    def _advance(self) -> None:
        self._rotation_degrees = (self._rotation_degrees + 4.5) % 360.0
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(112, 112)

    @staticmethod
    def _angular_distance(angle_a: float, angle_b: float) -> float:
        return abs(((angle_a - angle_b + 180.0) % 360.0) - 180.0)

    @staticmethod
    def _blend_color(start: QColor, end: QColor, factor: float) -> QColor:
        clamped_factor = max(0.0, min(1.0, factor))
        return QColor(
            round(start.red() + (end.red() - start.red()) * clamped_factor),
            round(start.green() + (end.green() - start.green()) * clamped_factor),
            round(start.blue() + (end.blue() - start.blue()) * clamped_factor),
        )

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            center_x = self.width() / 2
            center_y = self.height() / 2
            spinner_size = min(self.width(), self.height())
            orbit_radius = spinner_size * 0.36
            dot_radius = max(4.0, spinner_size * 0.047)

            painter.setPen(QPen(QColor(84, 98, 120, 42), 1.4))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(center_x, center_y), orbit_radius, orbit_radius)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(63, 75, 92, 36))
            painter.drawEllipse(QPointF(center_x, center_y), spinner_size * 0.19, spinner_size * 0.19)
            painter.setBrush(QColor(201, 164, 107, 24))
            painter.drawEllipse(QPointF(center_x, center_y), spinner_size * 0.145, spinner_size * 0.145)

            rune_radius = spinner_size * 0.115
            painter.save()
            painter.translate(center_x, center_y)
            painter.rotate(self._rotation_degrees)

            outer_pen = QPen(QColor(201, 164, 107, 168), max(1.4, spinner_size * 0.017))
            outer_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(outer_pen)
            painter.setBrush(Qt.NoBrush)
            outer_rect = QRectF(-rune_radius, -rune_radius, rune_radius * 2, rune_radius * 2)
            painter.drawArc(outer_rect, 22 * 16, 54 * 16)
            painter.drawArc(outer_rect, 146 * 16, 40 * 16)
            painter.drawArc(outer_rect, 266 * 16, 54 * 16)
            painter.restore()

            painter.save()
            painter.translate(center_x, center_y)
            painter.rotate(-(self._rotation_degrees * 0.72))

            inner_radius = spinner_size * 0.074
            inner_pen = QPen(QColor(245, 232, 203, 118), max(1.0, spinner_size * 0.012))
            inner_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(inner_pen)
            inner_rect = QRectF(-inner_radius, -inner_radius, inner_radius * 2, inner_radius * 2)
            painter.drawArc(inner_rect, 304 * 16, 76 * 16)
            painter.drawArc(inner_rect, 116 * 16, 56 * 16)
            painter.restore()

            sparkle = QPainterPath()
            sparkle.moveTo(center_x, center_y - spinner_size * 0.062)
            sparkle.lineTo(center_x + spinner_size * 0.028, center_y)
            sparkle.lineTo(center_x, center_y + spinner_size * 0.062)
            sparkle.lineTo(center_x - spinner_size * 0.028, center_y)
            sparkle.closeSubpath()

            painter.setPen(QPen(QColor(255, 244, 220, 210), max(1.0, spinner_size * 0.012)))
            painter.setBrush(QColor(223, 188, 126, 172))
            painter.drawPath(sparkle)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(247, 238, 223, 218))
            painter.drawEllipse(QPointF(center_x, center_y), spinner_size * 0.014, spinner_size * 0.014)

            lead_angle = self._rotation_degrees % 360.0
            base_dot_color = QColor("#566070")
            trail_dot_color = QColor("#c9a46b")
            head_dot_color = QColor("#f2ddbb")
            for index in range(12):
                dot_angle = index * 30.0
                trail_distance = ((lead_angle - dot_angle) % 360.0) / 30.0
                head_distance = self._angular_distance(dot_angle, lead_angle)
                trail_emphasis = max(0.0, 1.0 - (trail_distance / 8.0))
                head_emphasis = max(0.0, 1.0 - (head_distance / 24.0))
                emphasis = max(trail_emphasis, head_emphasis)
                radius = dot_radius * (0.72 + emphasis * 0.46)
                angle = math.radians(dot_angle - 90.0)
                x = center_x + math.cos(angle) * orbit_radius
                y = center_y + math.sin(angle) * orbit_radius

                color = self._blend_color(base_dot_color, trail_dot_color, trail_emphasis)
                color = self._blend_color(color, head_dot_color, head_emphasis)
                alpha = 58 + int(emphasis * 175)
                color.setAlpha(alpha)
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(x, y), radius, radius)
        finally:
            painter.end()


class InlineLoaderCard(QFrame):
    def __init__(self, title: str, message: str | None = None) -> None:
        super().__init__()
        self.setObjectName("BuildPanelCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        spinner = LoaderSpinner(self)
        spinner.setFixedSize(88, 88)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 15pt; font-weight: 800; padding-top: 4px;")

        layout.addWidget(spinner, 0, Qt.AlignCenter)
        layout.addWidget(title_label)
        if message:
            message_label = QLabel(message)
            message_label.setAlignment(Qt.AlignCenter)
            message_label.setWordWrap(True)
            message_label.setObjectName("Muted")
            message_label.setStyleSheet("font-size: 10.5pt; color: #b6bfce;")
            layout.addWidget(message_label)


class PlayerConfigRow(QFrame):
    def __init__(self, game_name: str, tag_line: str, remove_callback=None) -> None:
        super().__init__()
        self.setObjectName("Card")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        self.game_name_input = QLineEdit()
        self.game_name_input.setPlaceholderText("Nombre")
        self.game_name_input.setText(game_name)

        self.tag_line_input = QLineEdit()
        self.tag_line_input.setPlaceholderText("Tag")
        self.tag_line_input.setText(tag_line)

        self.remove_button = QPushButton("Eliminar")
        if remove_callback is not None:
            self.remove_button.clicked.connect(remove_callback)

        layout.addWidget(self.game_name_input, 3)
        layout.addWidget(self.tag_line_input, 2)
        layout.addWidget(self.remove_button)

    def values(self) -> tuple[str, str]:
        return self.game_name_input.text().strip(), self.tag_line_input.text().strip()


class RankingRow(QFrame):
    def __init__(self, position: int, summary: PlayerSummary) -> None:
        super().__init__()
        self.summary = summary
        if position == 1:
            self.setObjectName("RankingLeaderRow")
        elif position <= 3:
            self.setObjectName("RankingTopRow")
        else:
            self.setObjectName("RankingRowCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(14)

        position_badge = self._build_position_badge(position)

        avatar_stack = QWidget()
        avatar_stack.setAttribute(Qt.WA_TranslucentBackground, True)
        avatar_stack.setAutoFillBackground(False)
        avatar_stack.setStyleSheet("background: transparent;")
        avatar_stack_height = DISCORD_AVATAR_SIZE + (16 if position == 1 else 0)
        avatar_stack.setFixedSize(DISCORD_AVATAR_SIZE, avatar_stack_height)

        avatar_label = QLabel(avatar_stack)
        avatar_label.setGeometry(0, avatar_stack_height - DISCORD_AVATAR_SIZE, DISCORD_AVATAR_SIZE, DISCORD_AVATAR_SIZE)
        avatar_label.setPixmap(_load_discord_avatar(summary))
        avatar_label.setScaledContents(True)
        avatar_border = "rgba(201, 164, 107, 150)" if position == 1 else "#2f3750"
        avatar_label.setAttribute(Qt.WA_TranslucentBackground, True)
        avatar_label.setStyleSheet(
            f"border-radius: {DISCORD_AVATAR_SIZE // 2}px; background: transparent; border: 1px solid {avatar_border};"
        )
        if position == 1:
            crown_label = QLabel(avatar_stack)
            crown_label.setFixedSize(34, 20)
            crown_label.setPixmap(_get_leader_crown_pixmap(34, 20))
            crown_label.setScaledContents(True)
            crown_label.setAttribute(Qt.WA_TranslucentBackground, True)
            crown_label.setAutoFillBackground(False)
            crown_label.setStyleSheet("background: transparent;")
            crown_label.move((DISCORD_AVATAR_SIZE - crown_label.width()) // 2, 2)
            crown_label.raise_()

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(6)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        riot_id = f"{summary.game_name}#{summary.tag_line}" if summary.tag_line else summary.game_name
        escaped_name = html.escape(riot_id)
        name_label = QLabel()
        if summary.opgg_url:
            name_label.setText(
                f'<a href="{html.escape(summary.opgg_url, quote=True)}" '
                f'style="text-decoration:none; color:#f4eee2;">{escaped_name}</a>'
            )
            name_label.setTextFormat(Qt.RichText)
            name_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            name_label.setOpenExternalLinks(True)
        else:
            name_label.setText(escaped_name)
        name_label.setObjectName("RankingName")
        name_label.setStyleSheet("font-size: 13.6pt; font-weight: 700; color: #f4eee2;")

        title_row.addWidget(name_label, 0, Qt.AlignVCenter)
        if summary.opgg_url:
            opgg_button = QPushButton()
            opgg_button.setCursor(Qt.PointingHandCursor)
            opgg_button.setFixedSize(OPGG_ICON_WIDTH + 6, OPGG_ICON_HEIGHT + 4)
            opgg_button.setIcon(QIcon(_get_opgg_icon()))
            opgg_button.setIconSize(QSize(OPGG_ICON_WIDTH, OPGG_ICON_HEIGHT))
            opgg_button.setToolTip("Abrir perfil en OP.GG")
            opgg_button.setStyleSheet(
                "QPushButton { border: none; background: transparent; padding: 0; }"
                "QPushButton:hover { background: rgba(232, 64, 87, 0.12); border-radius: 6px; }"
            )
            opgg_button.clicked.connect(lambda _checked=False, url=summary.opgg_url: QDesktopServices.openUrl(QUrl(url)))
            title_row.addWidget(opgg_button, 0, Qt.AlignVCenter)
        title_row.addStretch(1)

        meta_parts = [summary.platform]
        if summary.summoner_level > 0:
            meta_parts.append(f"Nivel {summary.summoner_level}")
        else:
            meta_parts.append("Sin perfil completo")
        meta_label = QLabel(" / ".join(meta_parts))
        meta_label.setObjectName("RankingMetaPill")
        name_col.addLayout(title_row)
        name_col.addWidget(meta_label)

        soloq_text = summary.soloq.display_rank if summary.soloq else ("No disponible" if not summary.ranked_available else "Sin rango")
        mmr_text = str(summary.estimated_mmr) if summary.estimated_mmr is not None else "N/D"
        winrate_text = f"{summary.global_winrate:.1f}%" if summary.global_winrate is not None else "N/D"
        games_total = summary.ranked_games
        if games_total is None and summary.soloq and summary.soloq.total_games > 0:
            games_total = summary.soloq.total_games
        games_text = str(games_total) if games_total is not None else "N/D"
        soloq_accent = self._soloq_accent(summary)

        info_col = QHBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(10)
        info_col.addWidget(StatCard("SoloQ", soloq_text, accent=soloq_accent, style_variant="ranking"))
        info_col.addWidget(StatCard("Partidas", games_text, accent="#9db7d6", style_variant="ranking"))
        info_col.addWidget(StatCard("MMR", mmr_text, accent="#c9a46b", style_variant="ranking"))
        info_col.addWidget(StatCard("Winrate", winrate_text, accent="#8fb9a6", style_variant="ranking"))

        top_row.addWidget(position_badge, 0, Qt.AlignTop)
        top_row.addWidget(avatar_stack, 0, Qt.AlignTop)
        top_row.addLayout(name_col, 1)
        top_row.addLayout(info_col, 0)
        layout.addLayout(top_row)

        insights_row = self._build_insights_row(summary)
        if insights_row is not None:
            layout.addWidget(insights_row)

    @staticmethod
    def _soloq_accent(summary: PlayerSummary) -> str:
        return _soloq_accent(summary)

    def _build_insights_row(self, summary: PlayerSummary) -> QWidget | None:
        if not summary.most_played_champions:
            return None

        wrapper = QFrame()
        wrapper.setObjectName("RankingInsightsPanel")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        layout.addLayout(self._build_champion_insights(summary))
        return wrapper

    def _build_champion_insights(self, summary: PlayerSummary) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)

        title = QLabel("Campeones más jugados")
        title.setObjectName("RankingInsightsTitle")
        column.addWidget(title)

        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(10)
        chips.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        if summary.most_played_champions:
            for stat in summary.most_played_champions:
                chips.addWidget(
                    self._build_champion_item(stat.champion, stat.champion_id, stat.games),
                    0,
                    Qt.AlignTop,
                )
            chips.addStretch(1)
        else:
            empty = QLabel("Sin datos de campeones")
            empty.setObjectName("Muted")
            chips.addWidget(empty, 0, Qt.AlignTop)
            chips.addStretch(1)
        column.addLayout(chips)
        return column

    @staticmethod
    def _build_champion_item(champion_name: str, champion_id: int, games: int) -> QWidget:
        item = QFrame()
        item.setObjectName("RankingChampionChip")
        item.setFixedWidth(148)
        item.setFixedHeight(44)
        item.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout = QHBoxLayout(item)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(8)

        icon = QLabel()
        icon.setFixedSize(28, 28)
        icon.setPixmap(
            _load_champion_icon(champion_id).scaled(28, 28, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        )
        icon.setScaledContents(True)
        icon.setStyleSheet("border-radius: 7px; background: transparent;")

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        name = QLabel(champion_name)
        name.setObjectName("RankingChampionName")
        name.setFixedWidth(96)
        games_label = QLabel(f"{games} partidas")
        games_label.setObjectName("RankingChampionGames")

        text_col.addWidget(name)
        text_col.addWidget(games_label)
        text_col.addStretch(1)

        layout.addWidget(icon, 0, Qt.AlignTop)
        layout.addLayout(text_col, 1)
        return item

    @staticmethod
    def _build_position_badge(position: int) -> QFrame:
        badge = QFrame()
        badge.setObjectName("RankingPositionBadge")
        badge.setFixedSize(64, 58)

        layout = QVBoxLayout(badge)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(1)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel("Puesto")
        label.setObjectName("RankingPositionLabel")
        label.setAlignment(Qt.AlignCenter)

        value = QLabel(f"#{position}")
        value.setAlignment(Qt.AlignCenter)
        value.setObjectName("RankingPositionValueLeader" if position == 1 else "RankingPositionValue")

        layout.addWidget(label)
        layout.addWidget(value)
        return badge


class RankingConnector(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(34)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            center_x = self.width() / 2
            top_y = 4.0
            line_bottom_y = self.height() - 13.0

            gradient = QLinearGradient(center_x, top_y, center_x, line_bottom_y)
            gradient.setColorAt(0.0, QColor(201, 164, 107, 0))
            gradient.setColorAt(0.22, QColor(201, 164, 107, 66))
            gradient.setColorAt(0.70, QColor(201, 164, 107, 164))
            gradient.setColorAt(1.0, QColor(201, 164, 107, 24))

            pen = QPen(gradient, 1.8)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(center_x, top_y), QPointF(center_x, line_bottom_y))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(243, 223, 184, 82))
            painter.drawEllipse(QPointF(center_x, top_y + 2), 2.2, 2.2)

            rune_center_y = self.height() - 7.5
            rune = QPolygonF(
                [
                    QPointF(center_x, rune_center_y - 5.2),
                    QPointF(center_x + 4.8, rune_center_y),
                    QPointF(center_x, rune_center_y + 5.2),
                    QPointF(center_x - 4.8, rune_center_y),
                ]
            )
            rune_fill = QLinearGradient(center_x, rune_center_y - 5, center_x, rune_center_y + 5)
            rune_fill.setColorAt(0.0, QColor("#f3e0b6"))
            rune_fill.setColorAt(0.55, QColor("#d8b06d"))
            rune_fill.setColorAt(1.0, QColor("#8f6532"))
            painter.setBrush(rune_fill)
            painter.setPen(QPen(QColor("#f6e2b4"), 1.0))
            painter.drawPolygon(rune)

            inner = QPolygonF(
                [
                    QPointF(center_x, rune_center_y - 2.5),
                    QPointF(center_x + 2.2, rune_center_y),
                    QPointF(center_x, rune_center_y + 2.5),
                    QPointF(center_x - 2.2, rune_center_y),
                ]
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(18, 22, 30, 210))
            painter.drawPolygon(inner)
        finally:
            painter.end()


def _get_opgg_icon() -> QPixmap:
    global _OPGG_ICON_CACHE
    if _OPGG_ICON_CACHE is not None:
        return _OPGG_ICON_CACHE

    for icon_path in _OPGG_ICON_PATHS:
        if not icon_path.exists():
            continue
        pixmap = QPixmap(str(icon_path))
        if not pixmap.isNull():
            cropped = _crop_transparent_margins(pixmap)
            _OPGG_ICON_CACHE = cropped.scaled(
                OPGG_ICON_WIDTH,
                OPGG_ICON_HEIGHT,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            return _OPGG_ICON_CACHE

    pixmap = QPixmap(OPGG_ICON_WIDTH, OPGG_ICON_HEIGHT)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#e84057"))
    painter.drawRoundedRect(0, 0, OPGG_ICON_WIDTH, OPGG_ICON_HEIGHT, 6, 6)
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setPointSize(8)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "OP")
    painter.end()

    _OPGG_ICON_CACHE = pixmap
    return _OPGG_ICON_CACHE


def _get_app_logo(size: int = 96) -> QPixmap:
    cached = _APP_LOGO_CACHE.get(size)
    if cached is not None:
        return cached

    for logo_path in _APP_LOGO_PATHS:
        if not logo_path.exists():
            continue
        pixmap = QPixmap(str(logo_path))
        if not pixmap.isNull():
            scaled = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            canvas = QPixmap(size, size)
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
            painter.end()
            _APP_LOGO_CACHE[size] = canvas
            return _APP_LOGO_CACHE[size]

    fallback = QPixmap(size, size)
    fallback.fill(QColor("#11151b"))
    painter = QPainter(fallback)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#c8a66a"))
    painter.drawRoundedRect(0, 0, size, size, 22, 22)
    painter.setPen(QColor("#151515"))
    font = painter.font()
    font.setPointSize(max(16, size // 4))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(fallback.rect(), Qt.AlignCenter, "MMR")
    painter.end()
    _APP_LOGO_CACHE[size] = fallback
    return fallback


def _resolve_elo_logo_path(asset_name: str) -> Path | None:
    normalized_name = str(asset_name or "").strip().lower()
    if not normalized_name:
        return None

    for directory in _ELO_LOGO_DIRS:
        for extension in ("webp", "png"):
            candidate = directory / f"{normalized_name}.{extension}"
            if candidate.exists():
                return candidate
    return None


def _resolve_tier_logo_source(tier: str) -> tuple[Path | None, str]:
    normalized_tier = str(tier or "").strip().upper()
    if not normalized_tier:
        return None, ""

    candidates = _ELO_TIER_ASSET_ALIASES.get(normalized_tier, (normalized_tier.lower(),))
    for candidate_name in candidates:
        source = _resolve_elo_logo_path(candidate_name)
        if source is not None:
            return source, candidate_name
    return None, ""


def _clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _enhance_logo_detail(pixmap: QPixmap, contrast: float = 1.08, sharpness: float = 0.34) -> QPixmap:
    if pixmap.isNull():
        return pixmap

    working = pixmap
    max_dimension = max(working.width(), working.height())
    if max_dimension < 220:
        upscale_target = 260 if max_dimension < 180 else 220
        working = working.scaled(upscale_target, upscale_target, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    source = working.toImage().convertToFormat(QImage.Format_ARGB32)
    result = source.copy()

    for y in range(1, source.height() - 1):
        for x in range(1, source.width() - 1):
            center = source.pixelColor(x, y)
            if center.alpha() == 0:
                continue

            neighbors = (
                source.pixelColor(x - 1, y),
                source.pixelColor(x + 1, y),
                source.pixelColor(x, y - 1),
                source.pixelColor(x, y + 1),
            )
            avg_red = sum(color.red() for color in neighbors) / 4.0
            avg_green = sum(color.green() for color in neighbors) / 4.0
            avg_blue = sum(color.blue() for color in neighbors) / 4.0

            sharpened_red = center.red() + (center.red() - avg_red) * sharpness
            sharpened_green = center.green() + (center.green() - avg_green) * sharpness
            sharpened_blue = center.blue() + (center.blue() - avg_blue) * sharpness

            adjusted_red = 128.0 + (sharpened_red - 128.0) * contrast
            adjusted_green = 128.0 + (sharpened_green - 128.0) * contrast
            adjusted_blue = 128.0 + (sharpened_blue - 128.0) * contrast

            result.setPixelColor(
                x,
                y,
                QColor(
                    _clamp_channel(adjusted_red),
                    _clamp_channel(adjusted_green),
                    _clamp_channel(adjusted_blue),
                    center.alpha(),
                ),
            )

    return QPixmap.fromImage(result)


def _tint_pixmap(pixmap: QPixmap, color: QColor, alpha: int) -> QPixmap:
    tinted = QPixmap(pixmap.size())
    tinted.fill(Qt.transparent)

    painter = QPainter(tinted)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    overlay = QColor(color)
    overlay.setAlpha(max(0, min(255, alpha)))
    painter.fillRect(tinted.rect(), overlay)
    painter.end()
    return tinted


def _set_pixmap_opacity(pixmap: QPixmap, opacity: float) -> QPixmap:
    if pixmap.isNull():
        return pixmap

    canvas = QPixmap(pixmap.size())
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setOpacity(max(0.0, min(1.0, opacity)))
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return canvas


def _soft_blur_pixmap(pixmap: QPixmap, scale_factor: float = 0.28) -> QPixmap:
    if pixmap.isNull():
        return pixmap

    width = max(1, pixmap.width())
    height = max(1, pixmap.height())
    reduced_width = max(1, int(width * max(0.08, min(scale_factor, 1.0))))
    reduced_height = max(1, int(height * max(0.08, min(scale_factor, 1.0))))
    reduced = pixmap.scaled(reduced_width, reduced_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return reduced.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _build_today_elo_logo(tier: str | None, width: int, height: int) -> QPixmap | None:
    normalized_tier = str(tier or "").strip().upper()
    if not normalized_tier or width <= 0 or height <= 0:
        return None

    tier_color = SOLOQ_TIER_COLORS.get(normalized_tier, "#d8c29b")
    cache_key = (normalized_tier, width, height, tier_color)
    cached = _TODAY_ELO_LOGO_CACHE.get(cache_key)
    if cached is not None:
        return cached

    source, source_key = _resolve_tier_logo_source(normalized_tier)
    if source is None:
        return None

    pixmap = QPixmap(str(source))
    if pixmap.isNull():
        return None

    pixmap = _crop_transparent_margins(pixmap)
    accent = QColor(tier_color)
    if normalized_tier == "EMERALD" and source_key == "platinum":
        pixmap = _tint_pixmap(pixmap, accent, 118)
    if source_key in {"emerald", "esmeralda"} or max(pixmap.width(), pixmap.height()) < 190:
        pixmap = _enhance_logo_detail(pixmap, contrast=1.12, sharpness=0.42)

    max_logo_width = max(72, int(width * 0.92))
    max_logo_height = max(52, int(height * 0.88))
    scaled = pixmap.scaled(max_logo_width, max_logo_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    canvas = QPixmap(width, height)
    canvas.fill(Qt.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    try:
        glow = QRadialGradient(width * 0.50, height * 0.54, max(width, height) * 0.42)
        glow.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 72))
        glow.setColorAt(0.42, QColor(92, 198, 255, 26))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(width * 0.16, height * 0.14, width * 0.68, height * 0.72))

        shadow = _tint_pixmap(scaled, accent, 255)
        center_x = (width - scaled.width()) // 2
        center_y = (height - scaled.height()) // 2 + int(height * 0.02)

        painter.setOpacity(0.18)
        for offset_x, offset_y in ((0, 7), (-4, 4), (4, 4)):
            painter.drawPixmap(center_x + offset_x, center_y + offset_y, shadow)

        painter.setOpacity(1.0)
        painter.drawPixmap(center_x, center_y, scaled)
    finally:
        painter.end()

    _TODAY_ELO_LOGO_CACHE[cache_key] = canvas
    return canvas


def _resolve_home_hero_source() -> Path | None:
    global _HOME_HERO_SELECTED_SOURCE
    if _HOME_HERO_SELECTED_SOURCE is not None:
        return _HOME_HERO_SELECTED_SOURCE

    available: list[Path] = []
    seen: set[str] = set()
    for directory in _HOME_HERO_DIRS:
        for pattern in _HOME_HERO_GLOB_PATTERNS:
            for candidate in sorted(directory.glob(pattern)):
                key = str(candidate.resolve()).casefold()
                if key in seen:
                    continue
                seen.add(key)
                available.append(candidate)

    if not available:
        return None

    _HOME_HERO_SELECTED_SOURCE = random.choice(available)
    return _HOME_HERO_SELECTED_SOURCE


def _get_home_hero_background(width: int, height: int) -> QPixmap:
    source = _resolve_home_hero_source()
    cache_key = (str(source) if source is not None else "__fallback__", width, height)
    cached = _HOME_HERO_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if source is not None:
        pixmap = QPixmap(str(source))
        if not pixmap.isNull():
            scaled = pixmap.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            canvas = QPixmap(width, height)
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            painter.drawPixmap((width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled)
            painter.end()
            _HOME_HERO_CACHE[cache_key] = canvas
            return canvas

    fallback = QPixmap(width, height)
    fallback.fill(QColor("#0d0f14"))
    painter = QPainter(fallback)
    painter.setRenderHint(QPainter.Antialiasing, True)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor("#2a1c18"))
    gradient.setColorAt(0.55, QColor("#151118"))
    gradient.setColorAt(1.0, QColor("#090b10"))
    painter.fillRect(fallback.rect(), gradient)
    painter.end()
    _HOME_HERO_CACHE[cache_key] = fallback
    return fallback


def _get_home_action_icon(icon_key: str, size: int = 34) -> QPixmap:
    cache_key = (icon_key, size)
    cached = _HOME_ACTION_ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    try:
        gold = QColor("#d7b06d")
        gold_light = QColor("#f3dfb8")
        gold_dark = QColor("#8b6531")

        def _pen(width: float = 2.0) -> QPen:
            pen = QPen(gold_light, width)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            return pen

        glow = QRadialGradient(size * 0.52, size * 0.44, size * 0.44)
        glow.setColorAt(0.0, QColor(215, 176, 109, 58))
        glow.setColorAt(1.0, QColor(215, 176, 109, 0))
        painter.setBrush(glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(size * 0.08, size * 0.04, size * 0.84, size * 0.84))

        if icon_key == "ranking":
            shield = QPainterPath()
            shield.moveTo(size * 0.50, size * 0.12)
            shield.lineTo(size * 0.76, size * 0.24)
            shield.lineTo(size * 0.72, size * 0.58)
            shield.quadTo(size * 0.68, size * 0.82, size * 0.50, size * 0.92)
            shield.quadTo(size * 0.32, size * 0.82, size * 0.28, size * 0.58)
            shield.lineTo(size * 0.24, size * 0.24)
            shield.closeSubpath()

            fill = QLinearGradient(0, size * 0.12, 0, size * 0.92)
            fill.setColorAt(0.0, QColor(243, 223, 184, 90))
            fill.setColorAt(1.0, QColor(140, 101, 49, 46))
            painter.setBrush(fill)
            painter.setPen(_pen(1.8))
            painter.drawPath(shield)

            painter.setPen(_pen(1.6))
            painter.drawLine(QPointF(size * 0.50, size * 0.26), QPointF(size * 0.50, size * 0.70))
            painter.drawLine(QPointF(size * 0.36, size * 0.42), QPointF(size * 0.50, size * 0.26))
            painter.drawLine(QPointF(size * 0.64, size * 0.42), QPointF(size * 0.50, size * 0.26))
            painter.drawLine(QPointF(size * 0.40, size * 0.58), QPointF(size * 0.60, size * 0.58))

        elif icon_key == "builds":
            gem = QPainterPath()
            gem.moveTo(size * 0.50, size * 0.10)
            gem.lineTo(size * 0.80, size * 0.34)
            gem.lineTo(size * 0.66, size * 0.82)
            gem.lineTo(size * 0.34, size * 0.82)
            gem.lineTo(size * 0.20, size * 0.34)
            gem.closeSubpath()

            fill = QLinearGradient(0, size * 0.1, size * 0.8, size * 0.82)
            fill.setColorAt(0.0, QColor(243, 223, 184, 86))
            fill.setColorAt(0.55, QColor(215, 176, 109, 42))
            fill.setColorAt(1.0, QColor(139, 101, 49, 26))
            painter.setBrush(fill)
            painter.setPen(_pen(1.8))
            painter.drawPath(gem)

            painter.setPen(_pen(1.4))
            painter.drawLine(QPointF(size * 0.50, size * 0.10), QPointF(size * 0.50, size * 0.82))
            painter.drawLine(QPointF(size * 0.20, size * 0.34), QPointF(size * 0.80, size * 0.34))
            painter.drawLine(QPointF(size * 0.20, size * 0.34), QPointF(size * 0.50, size * 0.56))
            painter.drawLine(QPointF(size * 0.80, size * 0.34), QPointF(size * 0.50, size * 0.56))

        elif icon_key == "live":
            eye = QPainterPath()
            eye.moveTo(size * 0.16, size * 0.50)
            eye.quadTo(size * 0.50, size * 0.16, size * 0.84, size * 0.50)
            eye.quadTo(size * 0.50, size * 0.84, size * 0.16, size * 0.50)

            painter.setBrush(QColor(215, 176, 109, 26))
            painter.setPen(_pen(2.0))
            painter.drawPath(eye)

            iris = QRadialGradient(size * 0.50, size * 0.50, size * 0.18)
            iris.setColorAt(0.0, gold_light)
            iris.setColorAt(0.65, gold)
            iris.setColorAt(1.0, gold_dark)
            painter.setBrush(iris)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(size * 0.38, size * 0.38, size * 0.24, size * 0.24))

            painter.setBrush(QColor("#0d1016"))
            painter.drawEllipse(QRectF(size * 0.46, size * 0.46, size * 0.08, size * 0.08))

        elif icon_key == "today":
            dial = QRectF(size * 0.18, size * 0.18, size * 0.64, size * 0.64)
            painter.setBrush(QColor(215, 176, 109, 22))
            painter.setPen(_pen(1.8))
            painter.drawEllipse(dial)

            painter.setPen(_pen(1.5))
            painter.drawLine(QPointF(size * 0.50, size * 0.50), QPointF(size * 0.50, size * 0.30))
            painter.drawLine(QPointF(size * 0.50, size * 0.50), QPointF(size * 0.65, size * 0.57))

            arrow = QPainterPath()
            arrow.moveTo(size * 0.28, size * 0.82)
            arrow.lineTo(size * 0.42, size * 0.66)
            arrow.lineTo(size * 0.46, size * 0.72)
            arrow.lineTo(size * 0.70, size * 0.48)
            arrow.lineTo(size * 0.76, size * 0.54)
            arrow.lineTo(size * 0.52, size * 0.78)
            arrow.lineTo(size * 0.58, size * 0.82)
            arrow.closeSubpath()
            painter.setBrush(QColor(243, 223, 184, 168))
            painter.setPen(QPen(gold_dark, 1.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(arrow)

        else:
            painter.setBrush(QColor(215, 176, 109, 50))
            painter.setPen(_pen(1.8))
            painter.drawEllipse(QRectF(size * 0.18, size * 0.18, size * 0.64, size * 0.64))
    finally:
        painter.end()

    _HOME_ACTION_ICON_CACHE[cache_key] = pixmap
    return pixmap


def _get_leader_crown_pixmap(width: int = 38, height: int = 24) -> QPixmap:
    cache_key = (width, height)
    cached = _LEADER_CROWN_CACHE.get(cache_key)
    if cached is not None:
        return cached

    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    try:
        glow = QRadialGradient(width * 0.50, height * 0.48, width * 0.42)
        glow.setColorAt(0.0, QColor(201, 164, 107, 30))
        glow.setColorAt(0.68, QColor(201, 164, 107, 8))
        glow.setColorAt(1.0, QColor(201, 164, 107, 0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(width * 0.12, height * 0.08, width * 0.76, height * 0.74))

        crown = QPainterPath()
        crown.moveTo(width * 0.16, height * 0.74)
        crown.lineTo(width * 0.22, height * 0.28)
        crown.lineTo(width * 0.36, height * 0.47)
        crown.lineTo(width * 0.50, height * 0.11)
        crown.lineTo(width * 0.64, height * 0.47)
        crown.lineTo(width * 0.78, height * 0.28)
        crown.lineTo(width * 0.84, height * 0.74)
        crown.lineTo(width * 0.16, height * 0.74)
        crown.closeSubpath()

        fill = QLinearGradient(width * 0.50, height * 0.11, width * 0.50, height * 0.74)
        fill.setColorAt(0.0, QColor("#fff0be"))
        fill.setColorAt(0.52, QColor("#ddb15d"))
        fill.setColorAt(1.0, QColor("#9d6d31"))
        painter.setBrush(fill)
        painter.setPen(QPen(QColor("#f7e3ae"), 0.95, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(crown)

        band = QRectF(width * 0.22, height * 0.59, width * 0.56, height * 0.12)
        band_fill = QLinearGradient(0, band.top(), 0, band.bottom())
        band_fill.setColorAt(0.0, QColor("#f5d388"))
        band_fill.setColorAt(1.0, QColor("#b47d33"))
        painter.setBrush(band_fill)
        painter.setPen(QPen(QColor("#f5dfab"), 0.85))
        painter.drawRoundedRect(band, height * 0.05, height * 0.05)

        painter.setPen(QPen(QColor(104, 71, 34, 165), 0.85, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(QPointF(width * 0.50, height * 0.16), QPointF(width * 0.50, height * 0.58))
        painter.drawLine(QPointF(width * 0.22, height * 0.28), QPointF(width * 0.36, height * 0.47))
        painter.drawLine(QPointF(width * 0.78, height * 0.28), QPointF(width * 0.64, height * 0.47))

        jewel = QPolygonF(
            [
                QPointF(width * 0.50, height * 0.57),
                QPointF(width * 0.55, height * 0.62),
                QPointF(width * 0.50, height * 0.69),
                QPointF(width * 0.45, height * 0.62),
            ]
        )
        jewel_fill = QLinearGradient(width * 0.50, height * 0.57, width * 0.50, height * 0.69)
        jewel_fill.setColorAt(0.0, QColor("#fbefbf"))
        jewel_fill.setColorAt(1.0, QColor("#d19a46"))
        painter.setBrush(jewel_fill)
        painter.setPen(QPen(QColor("#f7e7c2"), 0.7))
        painter.drawPolygon(jewel)

        painter.setPen(QPen(QColor(255, 246, 221, 145), 0.75, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(QPointF(width * 0.28, height * 0.61), QPointF(width * 0.41, height * 0.61))
        painter.drawLine(QPointF(width * 0.59, height * 0.61), QPointF(width * 0.72, height * 0.61))
    finally:
        painter.end()

    _LEADER_CROWN_CACHE[cache_key] = pixmap
    return pixmap


def _crop_transparent_margins(pixmap: QPixmap) -> QPixmap:
    image = pixmap.toImage()
    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0 or not image.hasAlphaChannel():
        return pixmap

    left = width
    top = height
    right = -1
    bottom = -1

    for y in range(height):
        for x in range(width):
            if image.pixelColor(x, y).alpha() <= 0:
                continue
            if x < left:
                left = x
            if y < top:
                top = y
            if x > right:
                right = x
            if y > bottom:
                bottom = y

    if right < left or bottom < top:
        return pixmap

    return pixmap.copy(left, top, (right - left) + 1, (bottom - top) + 1)

def _load_discord_user_map() -> dict[str, str]:
        global _DISCORD_USER_MAP
        if _DISCORD_USER_MAP is not None:
            return _DISCORD_USER_MAP

        raw_data = None
        for path in _DISCORD_USER_MAP_PATHS:
            if not path.exists():
                continue
            try:
                raw_data = json.loads(path.read_text(encoding="utf-8"))
                break
            except (OSError, json.JSONDecodeError):
                continue

        if raw_data is None:
            _DISCORD_USER_MAP = {}
            return _DISCORD_USER_MAP

        mapping: dict[str, str] = {}
        if isinstance(raw_data, dict):
            for key, value in raw_data.items():
                lookup_key = str(key).strip()
                user_id = str(value).strip()
                if lookup_key and user_id:
                    mapping[lookup_key.casefold()] = user_id

        _DISCORD_USER_MAP = mapping
        return _DISCORD_USER_MAP

def _load_bundled_discord_avatar(user_id: str) -> QPixmap | None:
        for directory in _DISCORD_AVATAR_DIRS:
            avatar_path = directory / f"{user_id}.png"
            if not avatar_path.exists():
                continue

            pixmap = QPixmap()
            if pixmap.load(str(avatar_path)):
                return pixmap.scaled(
                    DISCORD_AVATAR_SIZE,
                    DISCORD_AVATAR_SIZE,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation,
                )
        return None


def _has_bundled_discord_avatar(user_id: str) -> bool:
        for directory in _DISCORD_AVATAR_DIRS:
            if (directory / f"{user_id}.png").exists():
                return True
        return False

def _build_discord_avatar_url(user_id: str) -> str | None:
        if not _DISCORD_BOT_TOKEN or not _DISCORD_GUILD_ID:
            return None

        try:
            response = requests.get(
                f"https://discord.com/api/v10/guilds/{_DISCORD_GUILD_ID}/members/{user_id}",
                headers={"Authorization": f"Bot {_DISCORD_BOT_TOKEN}"},
                timeout=6,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None

        member_avatar = payload.get("avatar")
        user = payload.get("user", {})
        user_avatar = user.get("avatar") if isinstance(user, dict) else None

        if member_avatar:
            return (
                f"https://cdn.discordapp.com/guilds/{_DISCORD_GUILD_ID}/users/{user_id}"
                f"/avatars/{member_avatar}.png?size=128"
            )
        if user_avatar:
            return f"https://cdn.discordapp.com/avatars/{user_id}/{user_avatar}.png?size=128"
        return None


def _download_image_bytes(url: str, timeout: int = 5, headers: dict[str, str] | None = None) -> bytes | None:
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException:
            return None
        return response.content


def _lolalytics_champion_icon_url(slug: str | None) -> str | None:
        if not slug:
            return None
        return f"https://cdn5.lolalytics.com/champx46/{slug}.webp"


def _prefetch_remote_image(url: str) -> None:
        if not url:
            return
        with _ASSET_CACHE_LOCK:
            if url in _REMOTE_IMAGE_BYTES_CACHE:
                return
        image_bytes = _download_image_bytes(url, timeout=6)
        with _ASSET_CACHE_LOCK:
            _REMOTE_IMAGE_BYTES_CACHE[url] = image_bytes


def _prefetch_discord_avatar(summary: PlayerSummary) -> None:
        lookup_key = f"{summary.game_name}#{summary.tag_line}".casefold()
        with _ASSET_CACHE_LOCK:
            if lookup_key in _DISCORD_AVATAR_BYTES_CACHE or lookup_key in _DISCORD_AVATAR_CACHE:
                return

        user_id = _load_discord_user_map().get(lookup_key)
        if not user_id:
            with _ASSET_CACHE_LOCK:
                _DISCORD_AVATAR_BYTES_CACHE[lookup_key] = None
            return

        if _has_bundled_discord_avatar(user_id):
            with _ASSET_CACHE_LOCK:
                _DISCORD_AVATAR_BYTES_CACHE[lookup_key] = None
            return

        avatar_url = _build_discord_avatar_url(user_id)
        avatar_bytes = _download_image_bytes(avatar_url, timeout=6) if avatar_url else None
        with _ASSET_CACHE_LOCK:
            _DISCORD_AVATAR_BYTES_CACHE[lookup_key] = avatar_bytes


def _prefetch_champion_icon(champion_id: int) -> None:
        if champion_id <= 0:
            return
        with _ASSET_CACHE_LOCK:
            if champion_id in _CHAMPION_ICON_BYTES_CACHE or champion_id in _CHAMPION_ICON_CACHE:
                return
        icon_bytes = _download_image_bytes(
            f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/{champion_id}.png",
            timeout=5,
        )
        with _ASSET_CACHE_LOCK:
            _CHAMPION_ICON_BYTES_CACHE[champion_id] = icon_bytes


def _prefetch_role_icon(role: str) -> None:
        if not role:
            return
        with _ASSET_CACHE_LOCK:
            if role in _ROLE_ICON_BYTES_CACHE or role in _ROLE_ICON_CACHE:
                return
        url = ROLE_ICON_URLS.get(role)
        icon_bytes = _download_image_bytes(url, timeout=5) if url else None
        with _ASSET_CACHE_LOCK:
            _ROLE_ICON_BYTES_CACHE[role] = icon_bytes


def _prefetch_summoner_spell_icon(spell_id: int) -> None:
        if spell_id <= 0:
            return
        with _ASSET_CACHE_LOCK:
            if spell_id in _SUMMONER_SPELL_ICON_BYTES_CACHE or spell_id in _SUMMONER_SPELL_ICON_CACHE:
                return
        icon_file = SUMMONER_SPELL_ICON_FILES.get(spell_id)
        icon_bytes = None
        if icon_file:
            version = "15.6.1"
            icon_bytes = _download_image_bytes(
                f"https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{icon_file}",
                timeout=5,
            )
        with _ASSET_CACHE_LOCK:
            _SUMMONER_SPELL_ICON_BYTES_CACHE[spell_id] = icon_bytes

def _load_discord_avatar(summary: PlayerSummary) -> QPixmap:
        lookup_key = f"{summary.game_name}#{summary.tag_line}".casefold()
        cached = _DISCORD_AVATAR_CACHE.get(lookup_key)
        if cached is not None:
            return cached

        pixmap = QPixmap(DISCORD_AVATAR_SIZE, DISCORD_AVATAR_SIZE)
        pixmap.fill(Qt.transparent)

        user_id = _load_discord_user_map().get(lookup_key)
        if user_id:
            bundled_avatar = _load_bundled_discord_avatar(user_id)
            if bundled_avatar is not None:
                pixmap = bundled_avatar
            else:
                avatar_bytes = _DISCORD_AVATAR_BYTES_CACHE.get(lookup_key)
                if avatar_bytes:
                    downloaded = QPixmap()
                    if downloaded.loadFromData(avatar_bytes):
                        pixmap = downloaded.scaled(
                            DISCORD_AVATAR_SIZE,
                            DISCORD_AVATAR_SIZE,
                            Qt.KeepAspectRatioByExpanding,
                            Qt.SmoothTransformation,
                        )

        rounded = QPixmap(DISCORD_AVATAR_SIZE, DISCORD_AVATAR_SIZE)
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addEllipse(0, 0, DISCORD_AVATAR_SIZE, DISCORD_AVATAR_SIZE)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pixmap)
        finally:
            painter.end()

        _DISCORD_AVATAR_CACHE[lookup_key] = rounded
        return rounded

def _load_champion_icon(champion_id: int) -> QPixmap:
        cached = _CHAMPION_ICON_CACHE.get(champion_id)
        if cached is not None:
            return cached

        pixmap = QPixmap(CHAMPION_ICON_SIZE, CHAMPION_ICON_SIZE)
        pixmap.fill(Qt.transparent)

        icon_bytes = _CHAMPION_ICON_BYTES_CACHE.get(champion_id)
        if icon_bytes:
            downloaded = QPixmap()
            if downloaded.loadFromData(icon_bytes):
                pixmap = downloaded.scaled(
                    CHAMPION_ICON_SIZE,
                    CHAMPION_ICON_SIZE,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )

        _CHAMPION_ICON_CACHE[champion_id] = pixmap
        return pixmap

def _load_role_icon(role: str) -> QPixmap:
        cached = _ROLE_ICON_CACHE.get(role)
        if cached is not None:
            return cached

        pixmap = QPixmap(ROLE_ICON_SIZE, ROLE_ICON_SIZE)
        pixmap.fill(Qt.transparent)

        icon_bytes = _ROLE_ICON_BYTES_CACHE.get(role)
        if icon_bytes:
            downloaded = QPixmap()
            if downloaded.loadFromData(icon_bytes):
                pixmap = downloaded.scaled(
                    ROLE_ICON_SIZE,
                    ROLE_ICON_SIZE,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )

        _ROLE_ICON_CACHE[role] = pixmap
        return pixmap


def _load_summoner_spell_icon(spell_id: int) -> QPixmap:
        cached = _SUMMONER_SPELL_ICON_CACHE.get(spell_id)
        if cached is not None:
            return cached

        size = DETAIL_SPELL_ICON_SIZE
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        icon_bytes = _SUMMONER_SPELL_ICON_BYTES_CACHE.get(spell_id)
        if icon_bytes:
            downloaded = QPixmap()
            if downloaded.loadFromData(icon_bytes):
                pixmap = downloaded.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        _SUMMONER_SPELL_ICON_CACHE[spell_id] = pixmap
        return pixmap


def _load_remote_image(url: str | None, size: int) -> QPixmap:
        if not url:
            fallback = QPixmap(size, size)
            fallback.fill(Qt.transparent)
            return fallback

        cache_key = (url, size)
        cached = _REMOTE_IMAGE_CACHE.get(cache_key)
        if cached is not None:
            return cached

        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        image_bytes = _REMOTE_IMAGE_BYTES_CACHE.get(url)
        if image_bytes:
            downloaded = QPixmap()
            if downloaded.loadFromData(image_bytes):
                scaled = downloaded.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                canvas = QPixmap(size, size)
                canvas.fill(Qt.transparent)
                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                painter.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
                painter.end()
                pixmap = canvas
                _REMOTE_IMAGE_CACHE[cache_key] = pixmap
        return pixmap


def _download_json(url: str, timeout: int = 6) -> dict | list | None:
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException:
            return None
        try:
            return response.json()
        except ValueError:
            return None


def _communitydragon_asset_url(path: str | None) -> str | None:
        if not path:
            return None
        normalized = path.replace("/lol-game-data/assets/", "/").lower()
        return f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default{normalized}"


def _load_champion_details(champion_id: int, allow_network: bool = True) -> dict | None:
        if champion_id <= 0:
            return None
        with _ASSET_CACHE_LOCK:
            if champion_id in _CHAMPION_DETAILS_CACHE:
                return _CHAMPION_DETAILS_CACHE[champion_id]
        if not allow_network:
            return None

        details = _download_json(
            f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champions/{champion_id}.json",
            timeout=6,
        )
        parsed = details if isinstance(details, dict) else None
        with _ASSET_CACHE_LOCK:
            _CHAMPION_DETAILS_CACHE[champion_id] = parsed
        return parsed


def _fandom_api_json(params: dict[str, str], timeout: int = 8) -> dict | None:
        try:
            response = requests.get(
                "https://lol.fandom.com/api.php",
                params=params,
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
        except requests.RequestException:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        return payload if isinstance(payload, dict) else None


def _get_fandom_loading_screen_url(
    champion_name: str,
    preferred_skin: str = "",
    allow_network: bool = True,
) -> str | None:
        normalized_name = champion_name.strip()
        if not normalized_name:
            return None
        preferred_skin = preferred_skin.strip()
        cache_key = f"{normalized_name.casefold()}::{preferred_skin.casefold()}" if preferred_skin else normalized_name.casefold()
        with _ASSET_CACHE_LOCK:
            cache_hit = cache_key in _FANDOM_LOADING_SCREEN_URL_CACHE
            cached = _FANDOM_LOADING_SCREEN_URL_CACHE.get(cache_key)
        if cache_hit:
            if cached and "format=original" not in cached:
                separator = "&" if "?" in cached else "?"
                cached = f"{cached}{separator}format=original"
                with _ASSET_CACHE_LOCK:
                    _FANDOM_LOADING_SCREEN_URL_CACHE[cache_key] = cached
            return cached
        if not allow_network:
            return None

        parse_payload = _fandom_api_json(
            {
                "action": "parse",
                "page": f"{normalized_name}/Gallery/Loading_Screens",
                "prop": "wikitext",
                "format": "json",
            }
        )
        wikitext = ""
        if isinstance(parse_payload, dict):
            parse_data = parse_payload.get("parse")
            if isinstance(parse_data, dict):
                wikitext_data = parse_data.get("wikitext")
                if isinstance(wikitext_data, dict):
                    wikitext = str(wikitext_data.get("*", ""))

        selected_file_title = None
        if preferred_skin:
            for line in wikitext.splitlines():
                if preferred_skin.casefold() in line.casefold():
                    preferred_match = re.search(r"\[\[(?:Image|File):([^\]|]+)", line, re.IGNORECASE)
                    if preferred_match is not None:
                        selected_file_title = preferred_match.group(1).strip()
                        break

        file_match = None
        if selected_file_title is None and not preferred_skin:
            file_match = re.search(r"\[\[(?:Image|File):([^\]|]+_0\.[^\]|]+)", wikitext, re.IGNORECASE)
            if file_match is None:
                file_match = re.search(r"\[\[(?:Image|File):([^\]|]+)", wikitext, re.IGNORECASE)
            selected_file_title = file_match.group(1).strip() if file_match is not None else None

        loading_screen_url = None
        if selected_file_title is not None:
            query_payload = _fandom_api_json(
                {
                    "action": "query",
                    "titles": f"File:{selected_file_title}",
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "format": "json",
                }
            )
            if isinstance(query_payload, dict):
                query_data = query_payload.get("query")
                if isinstance(query_data, dict):
                    pages = query_data.get("pages")
                    if isinstance(pages, dict):
                        for page_data in pages.values():
                            if not isinstance(page_data, dict):
                                continue
                            imageinfo = page_data.get("imageinfo")
                            if isinstance(imageinfo, list) and imageinfo:
                                first_image = imageinfo[0]
                                if isinstance(first_image, dict) and first_image.get("url"):
                                    loading_screen_url = str(first_image["url"]).strip() or None
                                    if loading_screen_url and "format=original" not in loading_screen_url:
                                        separator = "&" if "?" in loading_screen_url else "?"
                                        loading_screen_url = f"{loading_screen_url}{separator}format=original"
                                    break

        with _ASSET_CACHE_LOCK:
            _FANDOM_LOADING_SCREEN_URL_CACHE[cache_key] = loading_screen_url
        return loading_screen_url


def _get_champion_display_name(champion_id: int, fallback: str = "", allow_network: bool = True) -> str:
        if champion_id <= 0:
            return fallback
        with _ASSET_CACHE_LOCK:
            cached = _CHAMPION_NAME_CACHE.get(champion_id)
        if cached:
            return cached

        details = _load_champion_details(champion_id, allow_network=allow_network)
        if isinstance(details, dict):
            name = str(details.get("name", "")).strip()
            if name:
                with _ASSET_CACHE_LOCK:
                    _CHAMPION_NAME_CACHE[champion_id] = name
                return name
        return fallback


def _get_player_loading_skin(summary: PlayerSummary, champion_name: str) -> str:
        lookup_key = f"{summary.game_name}#{summary.tag_line}".casefold()
        player_override = PREFERRED_PLAYER_LOADING_SKINS.get(lookup_key, "").strip()
        if not player_override:
            compact_lookup_key = re.sub(r"\s+", "", lookup_key)
            player_override = PREFERRED_PLAYER_LOADING_SKINS.get(compact_lookup_key, "").strip()
        if player_override:
            return player_override
        return PREFERRED_LOADING_SKINS.get(champion_name.casefold(), "").strip()


def _get_communitydragon_skin_loading_url(
    champion_id: int,
    skin_name: str,
    allow_network: bool = True,
) -> str | None:
        if champion_id <= 0 or not skin_name.strip():
            return None
        details = _load_champion_details(champion_id, allow_network=allow_network)
        if not isinstance(details, dict):
            return None
        skins = details.get("skins")
        if not isinstance(skins, list):
            return None
        target_name = skin_name.casefold()
        for skin in skins:
            if not isinstance(skin, dict):
                continue
            current_name = str(skin.get("name", "")).strip()
            if current_name.casefold() != target_name:
                continue
            loadscreen_path = str(skin.get("loadScreenPath", "")).strip() or str(skin.get("tilePath", "")).strip()
            return _communitydragon_asset_url(loadscreen_path)
        return None


def _prefetch_champion_loading_screen(champion_name: str, preferred_skin: str = "", champion_id: int = 0) -> None:
        if not champion_name:
            return
        loadscreen_url = _get_fandom_loading_screen_url(champion_name, preferred_skin=preferred_skin)
        if not loadscreen_url and preferred_skin:
            loadscreen_url = _get_communitydragon_skin_loading_url(champion_id, preferred_skin)
        if loadscreen_url:
            _prefetch_remote_image(loadscreen_url)


def _player_lookup_key(summary_or_game_name: PlayerSummary | str, tag_line: str | None = None) -> str:
        if isinstance(summary_or_game_name, PlayerSummary):
            return f"{summary_or_game_name.game_name}#{summary_or_game_name.tag_line}".casefold()
        return f"{summary_or_game_name}#{tag_line or ''}".casefold()


def _featured_name_from_summary(summary: PlayerSummary, featured_champion_id: int) -> str:
        if featured_champion_id <= 0:
            return ""
        for champion in summary.most_played_champions:
            if champion.champion_id == featured_champion_id:
                return champion.champion
        return ""


def _get_player_showcase_data(summary: PlayerSummary, allow_network: bool = True) -> PlayerShowcaseData:
        lookup_key = _player_lookup_key(summary)
        with _ASSET_CACHE_LOCK:
            cached = _PLAYER_SHOWCASE_DATA_CACHE.get(lookup_key)
        if cached is not None:
            return cached

        featured_champion_id = _featured_champion_id(summary)
        featured_name = _get_champion_display_name(
            featured_champion_id,
            _featured_name_from_summary(summary, featured_champion_id),
            allow_network=allow_network,
        )
        preferred_skin = _get_player_loading_skin(summary, featured_name)
        art_url = _get_fandom_loading_screen_url(
            featured_name,
            preferred_skin=preferred_skin,
            allow_network=allow_network,
        )
        if not art_url and preferred_skin:
            art_url = _get_communitydragon_skin_loading_url(
                featured_champion_id,
                preferred_skin,
                allow_network=allow_network,
            )

        showcase_data = PlayerShowcaseData(
            featured_champion_id=featured_champion_id,
            featured_name=featured_name,
            preferred_skin=preferred_skin,
            art_url=art_url,
        )
        with _ASSET_CACHE_LOCK:
            _PLAYER_SHOWCASE_DATA_CACHE[lookup_key] = showcase_data
        return showcase_data


def _load_remote_cover_image(url: str | None, width: int, height: int) -> QPixmap:
        if not url:
            fallback = QPixmap(width, height)
            fallback.fill(Qt.transparent)
            return fallback

        cache_key = (url, width, height)
        cached = _REMOTE_COVER_CACHE.get(cache_key)
        if cached is not None:
            return cached

        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)

        image_bytes = _REMOTE_IMAGE_BYTES_CACHE.get(url)
        if image_bytes:
            downloaded = QPixmap()
            if downloaded.loadFromData(image_bytes):
                scaled = downloaded.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                canvas = QPixmap(width, height)
                canvas.fill(Qt.transparent)
                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                painter.drawPixmap((width - scaled.width()) // 2, (height - scaled.height()) // 2, scaled)
                painter.end()
                pixmap = canvas

        _REMOTE_COVER_CACHE[cache_key] = pixmap
        return pixmap


def _build_player_showcase_background(url: str | None, accent_hex: str, champion_id: int, width: int, height: int) -> QPixmap:
        cache_key = (url or "", accent_hex, champion_id, width, height)
        cached = _PLAYER_SHOWCASE_BACKGROUND_CACHE.get(cache_key)
        if cached is not None:
            return cached

        canvas = QPixmap(width, height)
        canvas.fill(Qt.transparent)

        painter = QPainter(canvas)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            rect = QRectF(1, 1, width - 2, height - 2)
            path = QPainterPath()
            path.addRoundedRect(rect, 24, 24)
            painter.setClipPath(path)

            image_bytes = _REMOTE_IMAGE_BYTES_CACHE.get(url) if url else None
            if image_bytes:
                painter.drawPixmap(0, 0, _load_remote_cover_image(url, width, height))
            else:
                fallback = QLinearGradient(0, 0, 0, height)
                accent = QColor(accent_hex)
                accent.setAlpha(110)
                fallback.setColorAt(0.0, QColor("#1a2230"))
                fallback.setColorAt(0.42, accent)
                fallback.setColorAt(1.0, QColor("#080b11"))
                painter.fillPath(path, fallback)
                if champion_id > 0:
                    icon = _load_champion_icon(champion_id).scaled(
                        130,
                        130,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation,
                    )
                    painter.setOpacity(0.18)
                    painter.drawPixmap((width - icon.width()) // 2, 78, icon)
                    painter.setOpacity(1.0)

            overlay = QLinearGradient(0, 0, 0, height)
            overlay.setColorAt(0.0, QColor(8, 10, 15, 55))
            overlay.setColorAt(0.46, QColor(8, 10, 15, 20))
            overlay.setColorAt(0.72, QColor(8, 10, 15, 185))
            overlay.setColorAt(1.0, QColor(8, 10, 15, 245))
            painter.fillPath(path, overlay)

            accent_bar = QRectF((width / 2) - 30, 0, 60, 8)
            painter.setClipping(False)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(accent_hex))
            painter.drawRoundedRect(accent_bar, 4, 4)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(accent_hex), 2.0))
            painter.drawRoundedRect(rect, 24, 24)
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
            painter.drawRoundedRect(QRectF(6, 6, width - 12, height - 12), 19, 19)
        finally:
            painter.end()

        _PLAYER_SHOWCASE_BACKGROUND_CACHE[cache_key] = canvas
        return canvas


def _draw_today_energy_streak(painter: QPainter, points: list[QPointF], tint: QColor) -> None:
    if len(points) < 2:
        return

    path = QPainterPath(points[0])
    for point in points[1:]:
        path.lineTo(point)

    glow_pen = QPen(QColor(tint.red(), tint.green(), tint.blue(), 78), 5.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    core_pen = QPen(QColor("#eefcff"), 1.25, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(glow_pen)
    painter.drawPath(path)
    painter.setPen(core_pen)
    painter.drawPath(path)


def _draw_today_crest_motif(painter: QPainter, width: int, height: int, accent: QColor) -> None:
    def _polygon_path(points: list[QPointF]) -> QPainterPath:
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        return path

    gold = QColor("#cfa86a")
    gold_soft = QColor("#f3dfb8")
    blue = QColor("#59d2ff")
    blue_soft = QColor("#baf7ff")
    frame_blue = QColor(97, 151, 196, 26)

    center_x = width * 0.50
    center_y = height * 0.25
    motif_w = width * 0.42
    motif_h = height * 0.22

    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(frame_blue, 1.0))
    for x_factor, bend_factor, end_factor in (
        (0.18, 0.13, 0.37),
        (0.31, 0.11, 0.31),
        (0.50, 0.09, 0.27),
        (0.69, 0.11, 0.31),
        (0.82, 0.13, 0.37),
    ):
        guide = QPainterPath()
        guide.moveTo(width * x_factor, height * 0.02)
        guide.lineTo(width * x_factor, height * bend_factor)
        guide.lineTo(width * 0.50, height * end_factor)
        painter.drawPath(guide)

    frame_pen = QPen(QColor(gold.red(), gold.green(), gold.blue(), 62), 1.25, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(frame_pen)
    painter.drawLine(QPointF(width * 0.08, height * 0.16), QPointF(width * 0.08, height * 0.43))
    painter.drawLine(QPointF(width * 0.92, height * 0.16), QPointF(width * 0.92, height * 0.43))
    painter.drawLine(QPointF(width * 0.08, height * 0.16), QPointF(width * 0.13, height * 0.08))
    painter.drawLine(QPointF(width * 0.92, height * 0.16), QPointF(width * 0.87, height * 0.08))

    glow = QRadialGradient(center_x, center_y + motif_h * 0.04, motif_w * 0.48)
    glow.setColorAt(0.0, QColor(78, 203, 255, 52))
    glow.setColorAt(0.52, QColor(accent.red(), accent.green(), accent.blue(), 18))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.setPen(Qt.NoPen)
    painter.setBrush(glow)
    painter.drawEllipse(
        QRectF(
            center_x - motif_w * 0.48,
            center_y - motif_h * 0.43,
            motif_w * 0.96,
            motif_h * 1.05,
        )
    )

    left_wing_points = [
        QPointF(center_x - motif_w * 0.03, center_y - motif_h * 0.16),
        QPointF(center_x - motif_w * 0.14, center_y - motif_h * 0.32),
        QPointF(center_x - motif_w * 0.29, center_y - motif_h * 0.12),
        QPointF(center_x - motif_w * 0.44, center_y - motif_h * 0.03),
        QPointF(center_x - motif_w * 0.35, center_y + motif_h * 0.18),
        QPointF(center_x - motif_w * 0.18, center_y + motif_h * 0.10),
        QPointF(center_x - motif_w * 0.08, center_y + motif_h * 0.26),
        QPointF(center_x - motif_w * 0.01, center_y + motif_h * 0.14),
    ]
    right_wing_points = [QPointF((center_x * 2.0) - point.x(), point.y()) for point in left_wing_points]
    left_wing = _polygon_path(left_wing_points)
    right_wing = _polygon_path(right_wing_points)

    shield_points = [
        QPointF(center_x, center_y - motif_h * 0.39),
        QPointF(center_x + motif_w * 0.10, center_y - motif_h * 0.23),
        QPointF(center_x + motif_w * 0.08, center_y + motif_h * 0.04),
        QPointF(center_x, center_y + motif_h * 0.37),
        QPointF(center_x - motif_w * 0.08, center_y + motif_h * 0.04),
        QPointF(center_x - motif_w * 0.10, center_y - motif_h * 0.23),
    ]
    shield_path = _polygon_path(shield_points)

    inner_shield_points = [
        QPointF(center_x, center_y - motif_h * 0.26),
        QPointF(center_x + motif_w * 0.054, center_y - motif_h * 0.15),
        QPointF(center_x + motif_w * 0.044, center_y + motif_h * 0.02),
        QPointF(center_x, center_y + motif_h * 0.24),
        QPointF(center_x - motif_w * 0.044, center_y + motif_h * 0.02),
        QPointF(center_x - motif_w * 0.054, center_y - motif_h * 0.15),
    ]
    inner_shield = _polygon_path(inner_shield_points)

    halo_pen = QPen(QColor(89, 210, 255, 22), max(4.5, motif_w * 0.028), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setBrush(Qt.NoBrush)
    painter.setPen(halo_pen)
    for crest_path in (left_wing, right_wing, shield_path):
        painter.drawPath(crest_path)

    wing_fill = QLinearGradient(center_x, center_y - motif_h * 0.28, center_x, center_y + motif_h * 0.28)
    wing_fill.setColorAt(0.0, QColor(7, 18, 31, 152))
    wing_fill.setColorAt(1.0, QColor(4, 10, 18, 214))
    shield_fill = QLinearGradient(center_x, center_y - motif_h * 0.39, center_x, center_y + motif_h * 0.37)
    shield_fill.setColorAt(0.0, QColor(10, 24, 41, 210))
    shield_fill.setColorAt(0.55, QColor(7, 18, 31, 235))
    shield_fill.setColorAt(1.0, QColor(4, 11, 20, 248))

    outline_pen = QPen(QColor(gold.red(), gold.green(), gold.blue(), 182), 2.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(outline_pen)
    painter.setBrush(wing_fill)
    painter.drawPath(left_wing)
    painter.drawPath(right_wing)
    painter.setBrush(shield_fill)
    painter.drawPath(shield_path)

    painter.setPen(QPen(QColor(gold_soft.red(), gold_soft.green(), gold_soft.blue(), 158), 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(QColor(6, 13, 22, 78))
    painter.drawPath(inner_shield)

    sigil = QPainterPath()
    sigil.moveTo(center_x, center_y - motif_h * 0.08)
    sigil.cubicTo(
        center_x + motif_w * 0.028,
        center_y - motif_h * 0.02,
        center_x + motif_w * 0.036,
        center_y + motif_h * 0.05,
        center_x,
        center_y + motif_h * 0.16,
    )
    sigil.cubicTo(
        center_x - motif_w * 0.036,
        center_y + motif_h * 0.05,
        center_x - motif_w * 0.028,
        center_y - motif_h * 0.02,
        center_x,
        center_y - motif_h * 0.08,
    )
    sigil.closeSubpath()
    sigil_fill = QLinearGradient(center_x, center_y - motif_h * 0.08, center_x, center_y + motif_h * 0.16)
    sigil_fill.setColorAt(0.0, QColor(192, 248, 255, 224))
    sigil_fill.setColorAt(0.4, QColor(114, 220, 255, 182))
    sigil_fill.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 92))
    painter.setPen(QPen(QColor(186, 247, 255, 126), 1.0))
    painter.setBrush(sigil_fill)
    painter.drawPath(sigil)

    painter.setPen(QPen(QColor(gold_soft.red(), gold_soft.green(), gold_soft.blue(), 118), 1.05, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    painter.drawLine(
        QPointF(center_x - motif_w * 0.08, center_y - motif_h * 0.38),
        QPointF(center_x - motif_w * 0.18, center_y - motif_h * 0.50),
    )
    painter.drawLine(
        QPointF(center_x + motif_w * 0.08, center_y - motif_h * 0.38),
        QPointF(center_x + motif_w * 0.18, center_y - motif_h * 0.50),
    )
    painter.drawLine(
        QPointF(center_x - motif_w * 0.22, center_y - motif_h * 0.20),
        QPointF(center_x + motif_w * 0.22, center_y - motif_h * 0.20),
    )

    _draw_today_energy_streak(
        painter,
        [
            QPointF(center_x - motif_w * 0.49, center_y - motif_h * 0.06),
            QPointF(center_x - motif_w * 0.44, center_y - motif_h * 0.12),
            QPointF(center_x - motif_w * 0.40, center_y - motif_h * 0.02),
            QPointF(center_x - motif_w * 0.35, center_y - motif_h * 0.08),
        ],
        blue,
    )
    _draw_today_energy_streak(
        painter,
        [
            QPointF(center_x + motif_w * 0.31, center_y + motif_h * 0.02),
            QPointF(center_x + motif_w * 0.36, center_y - motif_h * 0.08),
            QPointF(center_x + motif_w * 0.42, center_y + motif_h * 0.00),
            QPointF(center_x + motif_w * 0.46, center_y - motif_h * 0.10),
        ],
        blue_soft,
    )


def _build_today_card_background(accent_hex: str, width: int, height: int) -> QPixmap:
    cache_key = (accent_hex, width, height)
    cached = _TODAY_CARD_BACKGROUND_CACHE.get(cache_key)
    if cached is not None:
        return cached

    canvas = QPixmap(width, height)
    canvas.fill(Qt.transparent)

    painter = QPainter(canvas)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(1, 1, width - 2, height - 2)
        path = QPainterPath()
        path.addRoundedRect(rect, 24, 24)
        painter.setClipPath(path)

        accent = QColor(accent_hex)
        base = QLinearGradient(0, 0, 0, height)
        base.setColorAt(0.0, QColor("#181d27"))
        base.setColorAt(0.46, QColor("#131821"))
        base.setColorAt(1.0, QColor("#0c1016"))
        painter.fillPath(path, base)

        haze = QLinearGradient(0, 0, 0, height * 0.78)
        haze.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 26))
        haze.setColorAt(0.18, QColor(84, 190, 255, 22))
        haze.setColorAt(0.50, QColor(0, 0, 0, 0))
        painter.fillPath(path, haze)

        upper_focus = QRadialGradient(width * 0.50, height * 0.26, width * 0.42)
        upper_focus.setColorAt(0.0, QColor(103, 194, 255, 30))
        upper_focus.setColorAt(0.42, QColor(accent.red(), accent.green(), accent.blue(), 20))
        upper_focus.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillPath(path, upper_focus)

        painter.setClipping(False)

        guide_pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 42), 1.0)
        guide_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(guide_pen)
        guide_top = 24.0
        guide_bottom = height * 0.42
        painter.drawLine(QPointF(30.0, guide_top), QPointF(30.0, guide_bottom))
        painter.drawLine(QPointF(width - 30.0, guide_top), QPointF(width - 30.0, guide_bottom))

        lower_shadow = QLinearGradient(0, height * 0.54, 0, height)
        lower_shadow.setColorAt(0.0, QColor(7, 10, 16, 0))
        lower_shadow.setColorAt(0.34, QColor(7, 10, 16, 76))
        lower_shadow.setColorAt(1.0, QColor(7, 10, 16, 228))
        painter.fillPath(path, lower_shadow)

        accent_bar = QRectF((width / 2) - 30, 0, 60, 8)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(accent_hex))
        painter.drawRoundedRect(accent_bar, 4, 4)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(accent_hex), 1.8))
        painter.drawRoundedRect(rect, 24, 24)
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
        painter.drawRoundedRect(QRectF(6, 6, width - 12, height - 12), 19, 19)
    finally:
        painter.end()

    _TODAY_CARD_BACKGROUND_CACHE[cache_key] = canvas
    return canvas


def _soloq_accent(summary: PlayerSummary) -> str:
        if summary.soloq is None or not summary.soloq.tier:
            return "#d8c29b" if summary.ranked_available else "#8f99ab"
        return SOLOQ_TIER_COLORS.get(summary.soloq.tier.upper(), "#d8c29b")


def _featured_champion_id(summary: PlayerSummary) -> int:
        return summary.top_mastery_champion_id if summary.top_mastery_champion_id > 0 else 0


class PlayerShowcaseCard(QFrame):
    def __init__(self, summary: PlayerSummary, card_width: int = PLAYER_CARD_MIN_WIDTH) -> None:
        super().__init__()
        self.setObjectName("PlayerShowcaseCard")
        self.summary = summary
        self._accent = _soloq_accent(summary)
        showcase_data = _get_player_showcase_data(summary, allow_network=False)
        self._featured_champion_id = showcase_data.featured_champion_id
        self._featured_name = showcase_data.featured_name
        self._preferred_skin = showcase_data.preferred_skin
        self._art_url = showcase_data.art_url
        if self._art_url and self._art_url not in _REMOTE_IMAGE_BYTES_CACHE:
            _prefetch_remote_image(self._art_url)
        self._card_width = max(PLAYER_CARD_MIN_WIDTH, card_width)
        self._card_height = self._height_for_width(self._card_width)

        self.setFixedSize(self._card_width, self._card_height)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor if summary.opgg_url else Qt.ArrowCursor)
        if summary.opgg_url:
            self.setToolTip("Abrir perfil en OP.GG")

        self._background_label = QLabel(self)
        self._background_label.setGeometry(0, 0, self._card_width, self._card_height)
        self._background_label.setPixmap(
            _build_player_showcase_background(
                self._art_url,
                self._accent,
                self._featured_champion_id,
                self._card_width,
                self._card_height,
            )
        )
        self._background_label.setScaledContents(False)
        self._background_label.setStyleSheet("background: transparent;")
        self._background_label.lower()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(0)
        header.addStretch(1)
        header.addWidget(self._build_badge(self._rank_badge_text(), self._accent))
        header.addStretch(1)
        root.addLayout(header)
        root.addStretch(1)

        footer = QFrame(self)
        footer.setObjectName("PlayerShowcaseInfoPanel")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(14, 12, 14, 12)
        footer_layout.setSpacing(6)

        champion_label = QLabel(self._featured_name or "Maestria no disponible")
        champion_label.setObjectName("PlayerShowcaseChampion")
        champion_label.setAlignment(Qt.AlignCenter)
        champion_label.setWordWrap(True)

        if self._preferred_skin:
            skin_label = QLabel(self._preferred_skin)
            skin_label.setObjectName("PlayerShowcaseSkin")
            skin_label.setAlignment(Qt.AlignCenter)
            skin_label.setWordWrap(True)
        else:
            skin_label = None

        badges = QHBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(6)
        badges.setAlignment(Qt.AlignCenter)
        for text, accent in self._badge_specs():
            badges.addWidget(self._build_badge(text, accent))

        summoner_label = QLabel(f"{summary.game_name}#{summary.tag_line}")
        summoner_label.setObjectName("PlayerShowcaseSummoner")
        summoner_label.setAlignment(Qt.AlignCenter)
        summoner_label.setWordWrap(True)

        footer_layout.addWidget(champion_label)
        if skin_label is not None:
            footer_layout.addWidget(skin_label)
        footer_layout.addLayout(badges)
        footer_layout.addWidget(summoner_label)
        root.addWidget(footer)

    def set_card_width(self, width: int) -> None:
        next_width = max(PLAYER_CARD_MIN_WIDTH, width)
        if next_width == self._card_width:
            return
        self._card_width = next_width
        self._card_height = self._height_for_width(self._card_width)
        self.setFixedSize(self._card_width, self._card_height)
        self._background_label.setGeometry(0, 0, self._card_width, self._card_height)
        self._background_label.setPixmap(
            _build_player_showcase_background(
                self._art_url,
                self._accent,
                self._featured_champion_id,
                self._card_width,
                self._card_height,
            )
        )

    @staticmethod
    def _height_for_width(width: int) -> int:
        return max(352, int(width * PLAYER_CARD_ASPECT_RATIO))

    def _featured_games(self) -> int | None:
        if self._featured_champion_id <= 0:
            return None
        for champion in self.summary.most_played_champions:
            if champion.champion_id == self._featured_champion_id:
                return champion.games
        return None

    def _rank_badge_text(self) -> str:
        if self.summary.soloq and self.summary.soloq.tier:
            rank = f" {self.summary.soloq.rank}" if self.summary.soloq.rank else ""
            return f"{self.summary.soloq.tier.title()}{rank}"
        return "Sin SoloQ"

    def _badge_specs(self) -> list[tuple[str, str]]:
        badges: list[tuple[str, str]] = []
        if self.summary.top_mastery_level is not None:
            badges.append((f"M{self.summary.top_mastery_level}", "#7cc7ff"))
        if self.summary.top_mastery_points is not None:
            badges.append((self._format_points(self.summary.top_mastery_points), "#9ed07b"))
        else:
            games = self._featured_games()
            if self.summary.top_mastery_champion_id > 0 and games is not None and games > 0:
                badges.append((f"{games} partidas", "#9ed07b"))
        return badges[:2]

    @staticmethod
    def _format_points(points: int) -> str:
        if points >= 1_000_000:
            return f"{points / 1_000_000:.1f}M pts"
        if points >= 1_000:
            return f"{points / 1_000:.0f}k pts"
        return f"{points} pts"

    @staticmethod
    def _build_badge(text: str, accent: str) -> QLabel:
        color = QColor(accent)
        badge = QLabel(text)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 30);"
            f"border: 1px solid rgba({color.red()}, {color.green()}, {color.blue()}, 140);"
            "border-radius: 10px;"
            "padding: 4px 9px;"
            "font-family: 'Bahnschrift';"
            "font-size: 8.4pt;"
            "font-weight: 700;"
            "letter-spacing: 0.6px;"
            "color: #f4ecde;"
        )
        return badge

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.summary.opgg_url:
            QDesktopServices.openUrl(QUrl(self.summary.opgg_url))
            event.accept()
            return
        super().mouseReleaseEvent(event)


class TodayLpCard(QFrame):
    def __init__(self, summary: TodayLpSummary, card_width: int = TODAY_CARD_MIN_WIDTH) -> None:
        super().__init__()
        self.summary = summary
        self.player = summary.player
        self._accent = self._change_accent(summary)

        self._card_width = max(TODAY_CARD_MIN_WIDTH, card_width)
        self._card_height = self._height_for_width(self._card_width)
        self.setObjectName("TodayPlayerCard")
        self.setFixedSize(self._card_width, self._card_height)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor if self.player.opgg_url else Qt.ArrowCursor)
        if self.player.opgg_url:
            self.setToolTip("Abrir perfil en OP.GG")

        self._background_label = QLabel(self)
        self._background_label.setGeometry(0, 0, self._card_width, self._card_height)
        self._background_label.setPixmap(_build_today_card_background(self._accent, self._card_width, self._card_height))
        self._background_label.setStyleSheet("background: transparent;")
        self._background_label.lower()

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(10)

        delta_label = QLabel(self._delta_text())
        delta_label.setObjectName("TodayDeltaPill")
        delta_label.setStyleSheet(self._delta_stylesheet())

        avatar = QLabel()
        avatar.setFixedSize(42, 42)
        avatar.setPixmap(_load_discord_avatar(self.player))
        avatar.setScaledContents(True)
        avatar.setStyleSheet(f"background: transparent; border-radius: 21px; border: 1px solid {self._accent};")

        top_row.addWidget(delta_label, 0, Qt.AlignLeft | Qt.AlignTop)
        top_row.addStretch(1)
        top_row.addWidget(avatar, 0, Qt.AlignRight | Qt.AlignTop)
        root.addLayout(top_row)
        root.addSpacing(8)

        self._hero_panel = QFrame()
        self._hero_panel.setObjectName("TodayCardHeroPanel")
        self._hero_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hero_layout = QVBoxLayout(self._hero_panel)
        hero_layout.setContentsMargins(16, 10, 16, 10)
        hero_layout.setSpacing(6)
        hero_layout.setAlignment(Qt.AlignCenter)

        self._elo_logo_label = QLabel()
        self._elo_logo_label.setAlignment(Qt.AlignCenter)
        self._elo_logo_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self._elo_logo_label.setStyleSheet("background: transparent;")
        self._elo_logo_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._rank_chip_label = QLabel()
        self._rank_chip_label.setAlignment(Qt.AlignCenter)
        self._rank_chip_label.setAttribute(Qt.WA_TranslucentBackground, True)

        hero_layout.addStretch(1)
        hero_layout.addWidget(self._elo_logo_label, 0, Qt.AlignHCenter)
        hero_layout.addWidget(self._rank_chip_label, 0, Qt.AlignHCenter)
        hero_layout.addStretch(1)
        root.addWidget(self._hero_panel)
        root.addSpacing(8)
        self._refresh_rank_logo()
        root.addStretch(1)

        footer = QFrame(self)
        footer.setObjectName("TodayCardInfoPanel")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(14, 12, 14, 12)
        footer_layout.setSpacing(4)

        name_label = QLabel(summary.riot_id)
        name_label.setObjectName("TodayCardName")
        name_label.setWordWrap(True)

        current_label = QLabel(self._current_status_text())
        current_label.setObjectName("TodayCardCurrent")
        current_label.setWordWrap(True)

        matches_title = QLabel("ÚLTIMAS DE HOY")
        matches_title.setObjectName("TodayMatchesTitle")
        matches_title.setWordWrap(True)

        footer_layout.addWidget(name_label)
        footer_layout.addWidget(current_label)
        footer_layout.addSpacing(2)
        footer_layout.addWidget(matches_title)
        if summary.today_matches:
            for match in summary.today_matches[:2]:
                footer_layout.addWidget(self._build_match_row(match))
        else:
            empty_label = QLabel("No ha jugado hoy")
            empty_label.setObjectName("TodayCardMeta")
            empty_label.setWordWrap(True)
            footer_layout.addWidget(empty_label)
        root.addWidget(footer)

    def set_card_width(self, width: int) -> None:
        next_width = max(TODAY_CARD_MIN_WIDTH, width)
        if next_width == self._card_width:
            return
        self._card_width = next_width
        self._card_height = self._height_for_width(self._card_width)
        self.setFixedSize(self._card_width, self._card_height)
        self._background_label.setGeometry(0, 0, self._card_width, self._card_height)
        self._background_label.setPixmap(_build_today_card_background(self._accent, self._card_width, self._card_height))
        self._refresh_rank_logo()

    @staticmethod
    def _height_for_width(width: int) -> int:
        return max(336, int(width * TODAY_CARD_ASPECT_RATIO))

    @staticmethod
    def _change_accent(summary: TodayLpSummary) -> str:
        if summary.lp_change is None:
            return "#8f99ab"
        if summary.lp_change > 0:
            return "#5dd296"
        if summary.lp_change < 0:
            return "#e16b7b"
        return "#d8b379"

    def _delta_text(self) -> str:
        if self.summary.lp_change is None:
            return "Sin base"
        return self.summary.change_text

    def _delta_stylesheet(self) -> str:
        color = QColor(self._accent)
        return (
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 34);"
            f"border: 1px solid rgba({color.red()}, {color.green()}, {color.blue()}, 160);"
            "border-radius: 14px;"
            "padding: 8px 12px;"
            "font-family: 'Bahnschrift';"
            "font-size: 11.4pt;"
            "font-weight: 700;"
            "letter-spacing: 0.3px;"
            "color: #f5efe4;"
        )

    def _rank_tier(self) -> str:
        if self.player.soloq and self.player.soloq.tier:
            return self.player.soloq.tier
        return ""

    def _rank_badge_text(self) -> str:
        if self.player.soloq and self.player.soloq.tier:
            rank = f" {self.player.soloq.rank}" if self.player.soloq.rank else ""
            return f"{self.player.soloq.tier.title()}{rank}"
        return "Sin SoloQ"

    def _current_status_text(self) -> str:
        if self.player.soloq and self.player.soloq.tier:
            return f"{int(self.player.soloq.league_points or 0)} LP actuales"
        return self.summary.current_rank_text or "Sin SoloQ"

    def _rank_chip_stylesheet(self) -> str:
        tier_color = QColor(SOLOQ_TIER_COLORS.get(self._rank_tier().upper(), "#8f99ab"))
        return (
            f"background: rgba({tier_color.red()}, {tier_color.green()}, {tier_color.blue()}, 28);"
            f"border: 1px solid rgba({tier_color.red()}, {tier_color.green()}, {tier_color.blue()}, 142);"
            "border-radius: 11px;"
            "padding: 5px 12px;"
            "font-family: 'Bahnschrift';"
            "font-size: 8.6pt;"
            "font-weight: 700;"
            "letter-spacing: 0.7px;"
            "color: #f2efe7;"
        )

    def _refresh_rank_logo(self) -> None:
        hero_height = max(108, int(self._card_height * 0.30))
        self._hero_panel.setFixedHeight(hero_height)

        width = max(168, self._card_width - 84)
        height = max(82, int(hero_height * 0.60))
        self._elo_logo_label.setFixedSize(width, height)
        self._rank_chip_label.setText(self._rank_badge_text())
        self._rank_chip_label.setStyleSheet(self._rank_chip_stylesheet())

        logo = _build_today_elo_logo(self._rank_tier(), width, height)
        if logo is not None and not logo.isNull():
            self._elo_logo_label.setPixmap(logo)
            self._elo_logo_label.setText("")
            self._elo_logo_label.setStyleSheet("background: transparent;")
            return

        self._elo_logo_label.setPixmap(QPixmap())
        self._elo_logo_label.setText("Sin SoloQ")
        self._elo_logo_label.setStyleSheet(
            "background: transparent;"
            "color: #d9c7a4;"
            "font-family: 'Bahnschrift';"
            "font-size: 12pt;"
            "font-weight: 700;"
            "letter-spacing: 0.4px;"
        )

    def _build_match_row(self, match) -> QFrame:
        row = QFrame()
        row.setObjectName("TodayMatchRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        result = QLabel("W" if match.won else "L")
        result.setAlignment(Qt.AlignCenter)
        badge_color = "#5dd296" if match.won else "#e16b7b"
        color = QColor(badge_color)
        result.setStyleSheet(
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 34);"
            f"border: 1px solid rgba({color.red()}, {color.green()}, {color.blue()}, 160);"
            "border-radius: 10px;"
            "padding: 4px 8px;"
            "font-family: 'Bahnschrift';"
            "font-size: 8.8pt;"
            "font-weight: 700;"
            "color: #f5efe4;"
        )
        result.setFixedWidth(28)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        champion_name = match.champion or "Partida"
        champion_label = QLabel(champion_name)
        champion_label.setObjectName("TodayMatchChampion")
        champion_label.setWordWrap(True)

        meta_parts = [f"{match.kills}/{match.deaths}/{match.assists}"]
        if match.played_at_text:
            meta_parts.append(match.played_at_text)
        meta_label = QLabel(" · ".join(meta_parts))
        meta_label.setObjectName("TodayMatchMeta")
        meta_label.setWordWrap(True)

        text_col.addWidget(champion_label)
        text_col.addWidget(meta_label)

        layout.addWidget(result, 0, Qt.AlignTop)
        layout.addLayout(text_col, 1)
        return row

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.player.opgg_url:
            QDesktopServices.openUrl(QUrl(self.player.opgg_url))
            event.accept()
            return
        super().mouseReleaseEvent(event)


class TodayLpOverlayCard(QFrame):
    def __init__(self, summary: TodayLpSummary, card_width: int = TODAY_CARD_MIN_WIDTH) -> None:
        super().__init__()
        self.summary = summary
        self.player = summary.player
        self._accent = self._change_accent(summary)

        self._card_width = max(TODAY_CARD_MIN_WIDTH, card_width)
        self._card_height = self._height_for_width(self._card_width)
        self.setObjectName("TodayPlayerCard")
        self.setFixedSize(self._card_width, self._card_height)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor if self.player.opgg_url else Qt.ArrowCursor)
        if self.player.opgg_url:
            self.setToolTip("Abrir perfil en OP.GG")

        self._background_label = QLabel(self)
        self._background_label.setGeometry(0, 0, self._card_width, self._card_height)
        self._background_label.setPixmap(_build_today_card_background(self._accent, self._card_width, self._card_height))
        self._background_label.setStyleSheet("background: transparent;")
        self._background_label.lower()

        self._delta_label = QLabel(self._delta_text(), self)
        self._delta_label.setObjectName("TodayDeltaPill")
        self._delta_label.setStyleSheet(self._delta_stylesheet())

        self._avatar_label = QLabel(self)
        self._avatar_label.setFixedSize(42, 42)
        self._avatar_label.setPixmap(_load_discord_avatar(self.player))
        self._avatar_label.setScaledContents(True)
        self._avatar_label.setStyleSheet(
            f"background: transparent; border-radius: 21px; border: 1px solid {self._accent};"
        )

        self._hero_panel = QFrame(self)
        self._hero_panel.setObjectName("TodayCardHeroPanel")

        self._hero_back_logo_label = QLabel(self._hero_panel)
        self._hero_back_logo_label.setAlignment(Qt.AlignCenter)
        self._hero_back_logo_label.setStyleSheet("background: transparent;")
        self._hero_back_logo_label.setScaledContents(True)

        self._hero_logo_label = QLabel(self._hero_panel)
        self._hero_logo_label.setAlignment(Qt.AlignCenter)
        self._hero_logo_label.setStyleSheet("background: transparent;")
        self._hero_logo_label.setScaledContents(True)

        self._rank_hint_label = QLabel(self._hero_panel)
        self._rank_hint_label.setObjectName("TodayHeroRankHint")
        self._rank_hint_label.setAlignment(Qt.AlignCenter)

        self._footer = QFrame(self)
        self._footer.setObjectName("TodayCardInfoPanel")
        footer_layout = QVBoxLayout(self._footer)
        footer_layout.setContentsMargins(14, 12, 14, 12)
        footer_layout.setSpacing(4)

        name_label = QLabel(summary.riot_id)
        name_label.setObjectName("TodayCardName")
        name_label.setWordWrap(True)

        current_label = QLabel(self._current_status_text())
        current_label.setObjectName("TodayCardCurrent")
        current_label.setWordWrap(True)

        matches_title = QLabel("ULTIMAS DE HOY")
        matches_title.setObjectName("TodayMatchesTitle")
        matches_title.setWordWrap(True)

        footer_layout.addWidget(name_label)
        footer_layout.addWidget(current_label)
        footer_layout.addSpacing(2)
        footer_layout.addWidget(matches_title)
        if summary.today_matches:
            for match in summary.today_matches[:2]:
                footer_layout.addWidget(self._build_match_row(match))
        else:
            empty_label = QLabel("No ha jugado hoy")
            empty_label.setObjectName("TodayCardMeta")
            empty_label.setWordWrap(True)
            footer_layout.addWidget(empty_label)

        self._refresh_rank_logo()
        self._layout_card_sections()

    def set_card_width(self, width: int) -> None:
        next_width = max(TODAY_CARD_MIN_WIDTH, width)
        if next_width == self._card_width:
            return
        self._card_width = next_width
        self._card_height = self._height_for_width(self._card_width)
        self.setFixedSize(self._card_width, self._card_height)
        self._background_label.setGeometry(0, 0, self._card_width, self._card_height)
        self._background_label.setPixmap(_build_today_card_background(self._accent, self._card_width, self._card_height))
        self._refresh_rank_logo()
        self._layout_card_sections()

    @staticmethod
    def _height_for_width(width: int) -> int:
        return max(352, int(width * 0.92))

    @staticmethod
    def _change_accent(summary: TodayLpSummary) -> str:
        if summary.lp_change is None:
            return "#8f99ab"
        if summary.lp_change > 0:
            return "#5dd296"
        if summary.lp_change < 0:
            return "#e16b7b"
        return "#d8b379"

    def _delta_text(self) -> str:
        if self.summary.lp_change is None:
            return "Sin base"
        return self.summary.change_text

    def _delta_stylesheet(self) -> str:
        color = QColor(self._accent)
        return (
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 34);"
            f"border: 1px solid rgba({color.red()}, {color.green()}, {color.blue()}, 160);"
            "border-radius: 14px;"
            "padding: 8px 12px;"
            "font-family: 'Bahnschrift';"
            "font-size: 11.4pt;"
            "font-weight: 700;"
            "letter-spacing: 0.3px;"
            "color: #f5efe4;"
        )

    def _rank_tier(self) -> str:
        if self.player.soloq and self.player.soloq.tier:
            return self.player.soloq.tier
        return ""

    def _rank_badge_text(self) -> str:
        if self.player.soloq and self.player.soloq.tier:
            rank = f" {self.player.soloq.rank}" if self.player.soloq.rank else ""
            return f"{self.player.soloq.tier.title()}{rank}"
        return "Sin SoloQ"

    def _current_status_text(self) -> str:
        if self.player.soloq and self.player.soloq.tier:
            return f"{int(self.player.soloq.league_points or 0)} LP actuales"
        return self.summary.current_rank_text or "Sin SoloQ"

    def _rank_hint_stylesheet(self) -> str:
        tier_color = QColor(SOLOQ_TIER_COLORS.get(self._rank_tier().upper(), "#8f99ab"))
        return (
            "background: transparent;"
            "border: none;"
            "padding: 0;"
            "font-family: 'Bahnschrift';"
            "font-size: 8.8pt;"
            "font-weight: 700;"
            "letter-spacing: 0.8px;"
            f"color: rgba({tier_color.red()}, {tier_color.green()}, {tier_color.blue()}, 185);"
        )

    def _refresh_rank_logo(self) -> None:
        self._rank_hint_label.setText(self._rank_badge_text())
        self._rank_hint_label.setStyleSheet(self._rank_hint_stylesheet())

        logo = _build_today_elo_logo(
            self._rank_tier(),
            max(196, self._card_width - 44),
            max(118, int(self._card_height * 0.30)),
        )
        if logo is not None and not logo.isNull():
            self._hero_back_logo_label.setPixmap(_set_pixmap_opacity(_soft_blur_pixmap(logo, scale_factor=0.18), 0.26))
            self._hero_logo_label.setPixmap(_set_pixmap_opacity(logo, 0.54))
            self._hero_logo_label.setText("")
            self._hero_logo_label.setStyleSheet("background: transparent;")
            return

        self._hero_back_logo_label.setPixmap(QPixmap())
        self._hero_logo_label.setPixmap(QPixmap())
        self._hero_logo_label.setText("Sin SoloQ")
        self._hero_logo_label.setStyleSheet(
            "background: transparent;"
            "color: rgba(217, 199, 164, 170);"
            "font-family: 'Bahnschrift';"
            "font-size: 12pt;"
            "font-weight: 700;"
            "letter-spacing: 0.4px;"
        )

    def _layout_card_sections(self) -> None:
        outer_margin = 16
        top_y = outer_margin

        self._delta_label.adjustSize()
        delta_size = self._delta_label.sizeHint()
        self._delta_label.setGeometry(outer_margin, top_y, max(80, delta_size.width()), max(30, delta_size.height()))
        self._avatar_label.setGeometry(self._card_width - outer_margin - 42, top_y, 42, 42)

        body_top = top_y + 42 + 10
        footer_width = self._card_width - (outer_margin * 2) + 6
        self._footer.resize(footer_width, 10)
        self._footer.layout().activate()
        footer_height = min(
            self._card_height - body_top - outer_margin,
            max(116, self._footer.sizeHint().height()),
        )
        footer_y = self._card_height - outer_margin - footer_height
        self._footer.setGeometry(outer_margin - 3, footer_y, footer_width, footer_height)

        overlap = 36 if self.summary.today_matches else 10
        hero_x = 8
        hero_y = body_top
        hero_width = self._card_width - (hero_x * 2)
        hero_height = max(170, footer_y - hero_y + overlap)
        self._hero_panel.setGeometry(hero_x, hero_y, hero_width, hero_height)

        back_width = int(hero_width * 0.96)
        back_height = int(hero_height * 0.94)
        self._hero_back_logo_label.setGeometry(
            (hero_width - back_width) // 2,
            max(4, int(hero_height * 0.01)),
            back_width,
            back_height,
        )

        logo_width = int(hero_width * 0.82)
        logo_height = int(hero_height * 0.62)
        self._hero_logo_label.setGeometry(
            (hero_width - logo_width) // 2,
            max(18, int(hero_height * 0.16)),
            logo_width,
            logo_height,
        )

        self._rank_hint_label.adjustSize()
        rank_size = self._rank_hint_label.sizeHint()
        self._rank_hint_label.setGeometry(
            (hero_width - rank_size.width()) // 2,
            hero_height - rank_size.height() - 18,
            rank_size.width(),
            rank_size.height(),
        )

        self._hero_panel.raise_()
        self._footer.raise_()
        self._delta_label.raise_()
        self._avatar_label.raise_()

    def _build_match_row(self, match) -> QFrame:
        row = QFrame()
        row.setObjectName("TodayMatchRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        result = QLabel("W" if match.won else "L")
        result.setAlignment(Qt.AlignCenter)
        badge_color = "#5dd296" if match.won else "#e16b7b"
        color = QColor(badge_color)
        result.setStyleSheet(
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 34);"
            f"border: 1px solid rgba({color.red()}, {color.green()}, {color.blue()}, 160);"
            "border-radius: 10px;"
            "padding: 4px 8px;"
            "font-family: 'Bahnschrift';"
            "font-size: 8.8pt;"
            "font-weight: 700;"
            "color: #f5efe4;"
        )
        result.setFixedWidth(28)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        champion_name = match.champion or "Partida"
        champion_label = QLabel(champion_name)
        champion_label.setObjectName("TodayMatchChampion")
        champion_label.setWordWrap(True)

        meta_parts = [f"{match.kills}/{match.deaths}/{match.assists}"]
        if match.played_at_text:
            meta_parts.append(match.played_at_text)
        meta_label = QLabel(" · ".join(meta_parts))
        meta_label.setObjectName("TodayMatchMeta")
        meta_label.setWordWrap(True)

        text_col.addWidget(champion_label)
        text_col.addWidget(meta_label)

        layout.addWidget(result, 0, Qt.AlignTop)
        layout.addLayout(text_col, 1)
        return row

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.player.opgg_url:
            QDesktopServices.openUrl(QUrl(self.player.opgg_url))
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _LegacyLiveGameRow(QFrame):
    def __init__(self, summary: LiveGameParticipantSummary) -> None:
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(16)

        icon_stack = QWidget()
        icon_stack.setFixedSize(CHAMPION_ICON_SIZE, CHAMPION_ICON_SIZE)

        icon_label = QLabel(icon_stack)
        icon_label.setGeometry(0, 0, CHAMPION_ICON_SIZE, CHAMPION_ICON_SIZE)
        icon_label.setPixmap(_load_champion_icon(summary.champion_id))
        icon_label.setScaledContents(True)
        icon_label.setStyleSheet("background: transparent;")

        if summary.role != "UNKNOWN":
            role_container = QLabel(icon_stack)
            role_container.setGeometry(
                CHAMPION_ICON_SIZE - ROLE_ICON_SIZE,
                CHAMPION_ICON_SIZE - ROLE_ICON_SIZE,
                ROLE_ICON_SIZE,
                ROLE_ICON_SIZE,
            )
            role_container.setStyleSheet(
                "background: #0b1528; border: 1px solid #22304d; border-radius: 11px; padding: 1px;"
            )
            role_label = QLabel(role_container)
            role_label.setGeometry(1, 1, ROLE_ICON_SIZE - 2, ROLE_ICON_SIZE - 2)
            role_label.setPixmap(_load_role_icon(summary.role))
            role_label.setScaledContents(True)
            role_label.setStyleSheet("background: transparent;")
            role_container.setToolTip(summary.role)

        left = QVBoxLayout()
        name_label = QLabel(f"{summary.game_name}#{summary.tag_line}")
        name_label.setStyleSheet("font-size: 13pt; font-weight: 700;")
        if summary.in_game:
            status_text = "En partida"
        elif summary.status_text == "Fuera de partida":
            status_text = "Fuera de partida"
        else:
            status_text = "No verificable"
        status_label = QLabel(status_text)
        status_label.setStyleSheet(
            "font-weight: 700; color: #54d2a0;" if summary.in_game else "font-weight: 700; color: #ff7d9b;"
        )
        detail_label = QLabel(summary.status_text or "Sin datos")
        detail_label.setObjectName("Muted")
        detail_label.setWordWrap(True)
        left.addWidget(name_label)
        left.addWidget(status_label)
        left.addWidget(detail_label)

        right = QHBoxLayout()
        right.setSpacing(12)
        mastery_text = f"M{summary.mastery_level}" if summary.mastery_level is not None else "Sin Maestria"
        right.addWidget(
            StatCard(
                "Maestria",
                mastery_text,
                accent="#7cc7ff" if summary.in_game else "#7e8aa3",
            )
        )
        right.addWidget(
            StatCard(
                "Rol",
                ROLE_DISPLAY_NAMES.get(summary.role, summary.role) if summary.role != "UNKNOWN" else "N/D",
                accent="#ffbf69" if summary.in_game else "#7e8aa3",
            )
        )
        right.addWidget(
            StatCard(
                "Modo",
                summary.game.game_mode if summary.game else "N/D",
                accent="#f58ab3" if summary.in_game else "#7e8aa3",
            )
        )

        top_row.addWidget(icon_stack, 0, Qt.AlignTop)
        top_row.addLayout(left, 2)
        top_row.addLayout(right, 3)
        layout.addLayout(top_row)

        if summary.in_game and summary.participants:
            toggle_button = QPushButton(f"Ver partida completa ({len(summary.participants)} jugadores)")
            toggle_button.setCheckable(True)
            toggle_button.setCursor(Qt.PointingHandCursor)
            toggle_button.setStyleSheet(
                "QPushButton { text-align: left; padding: 10px 14px; font-weight: 700; }"
            )
            details_widget = self._build_match_details(summary.participants)
            details_widget.setVisible(False)

            def _toggle_details(checked: bool) -> None:
                toggle_button.setText(
                    "Ocultar partida completa"
                    if checked
                    else f"Ver partida completa ({len(summary.participants)} jugadores)"
                )
                details_widget.setVisible(checked)

            toggle_button.toggled.connect(_toggle_details)
            layout.addWidget(toggle_button)
            layout.addWidget(details_widget)

    def _build_match_details(self, participants: list[LiveGamePlayerDetails]) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        blue_team = self._sort_live_team([participant for participant in participants if participant.team_color == "blue"])
        red_team = self._sort_live_team([participant for participant in participants if participant.team_color == "red"])

        layout.addWidget(self._build_team_column("Equipo Azul", blue_team, "#7cc7ff"))
        layout.addWidget(self._build_team_column("Equipo Rojo", red_team, "#ff7d9b"))
        return wrapper

    @staticmethod
    def _sort_live_team(participants: list[LiveGamePlayerDetails]) -> list[LiveGamePlayerDetails]:
        role_order = {
            "TOP": 0,
            "JUNGLE": 1,
            "MIDDLE": 2,
            "BOTTOM": 3,
            "UTILITY": 4,
            "UNKNOWN": 5,
        }
        return sorted(
            participants,
            key=lambda participant: (
                role_order.get(participant.role, 5),
                participant.game_name.casefold(),
                participant.tag_line.casefold(),
            ),
        )

    def _build_team_column(self, title: str, participants: list[LiveGamePlayerDetails], accent: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 12pt; font-weight: 700; color: {accent};")
        layout.addWidget(title_label)

        for participant in participants:
            layout.addWidget(LiveGamePlayerDetailRow(participant))
        layout.addStretch(1)
        return frame


class _LegacyLiveGamePlayerDetailRow(QFrame):
    def __init__(self, participant: LiveGamePlayerDetails) -> None:
        super().__init__()
        self.setObjectName("Card")
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        icon_stack = QWidget()
        icon_stack.setFixedSize(DETAIL_CHAMPION_ICON_SIZE, DETAIL_CHAMPION_ICON_SIZE)

        champion_icon = QLabel(icon_stack)
        champion_icon.setGeometry(0, 0, DETAIL_CHAMPION_ICON_SIZE, DETAIL_CHAMPION_ICON_SIZE)
        champion_icon.setPixmap(_load_champion_icon(participant.champion_id))
        champion_icon.setScaledContents(True)
        champion_icon.setStyleSheet("background: transparent; border-radius: 8px;")

        if participant.role != "UNKNOWN":
            role_container = QLabel(icon_stack)
            role_container.setGeometry(
                DETAIL_CHAMPION_ICON_SIZE - DETAIL_ROLE_ICON_SIZE,
                DETAIL_CHAMPION_ICON_SIZE - DETAIL_ROLE_ICON_SIZE,
                DETAIL_ROLE_ICON_SIZE,
                DETAIL_ROLE_ICON_SIZE,
            )
            role_container.setStyleSheet(
                "background: #0b1528; border: 1px solid #22304d; border-radius: 9px; padding: 1px;"
            )
            role_icon = QLabel(role_container)
            role_icon.setGeometry(1, 1, DETAIL_ROLE_ICON_SIZE - 2, DETAIL_ROLE_ICON_SIZE - 2)
            role_icon.setPixmap(_load_role_icon(participant.role))
            role_icon.setScaledContents(True)
            role_icon.setStyleSheet("background: transparent;")
            role_container.setToolTip(participant.role)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(4)

        header = QLabel(
            f"{participant.game_name}#{participant.tag_line}"
            if participant.tag_line
            else participant.game_name
        )
        header.setStyleSheet("font-size: 11pt; font-weight: 700;")

        subheader_parts = [participant.champion or "Sin Maestria"]
        if participant.role != "UNKNOWN":
            subheader_parts.append(ROLE_DISPLAY_NAMES.get(participant.role, participant.role))
        subheader = QLabel(" · ".join(subheader_parts))
        subheader.setObjectName("Muted")
        subheader.setWordWrap(True)

        spell_row = QHBoxLayout()
        spell_row.setContentsMargins(0, 0, 0, 0)
        spell_row.setSpacing(6)

        for index, spell_id in enumerate(participant.spell_ids[:2]):
            spell_icon = QLabel()
            spell_icon.setFixedSize(DETAIL_SPELL_ICON_SIZE, DETAIL_SPELL_ICON_SIZE)
            spell_icon.setPixmap(_load_summoner_spell_icon(spell_id))
            spell_icon.setScaledContents(True)
            if index < len(participant.spell_names):
                spell_icon.setToolTip(participant.spell_names[index])
            spell_row.addWidget(spell_icon, 0, Qt.AlignVCenter)
        spell_row.addStretch(1)

        info_col.addWidget(header)
        info_col.addWidget(subheader)
        info_col.addLayout(spell_row)

        stats_col = QVBoxLayout()
        stats_col.setContentsMargins(0, 0, 0, 0)
        stats_col.setSpacing(4)

        primary_stats = []
        if participant.recent_winrate is not None and participant.recent_games is not None:
            primary_stats.append(f"{participant.recent_winrate:.0f}% WR · {participant.recent_games}p")
        if participant.avg_kda:
            primary_stats.append(f"KDA {participant.avg_kda}")

        secondary_stats = []
        if participant.summoner_level > 0:
            secondary_stats.append(f"Nivel {participant.summoner_level}")
        if participant.mastery_level is not None:
            secondary_stats.append(f"M{participant.mastery_level}")
        if participant.champion_rank:
            secondary_stats.append(participant.champion_rank)

        primary_label = QLabel(" · ".join(primary_stats) if primary_stats else "Sin estadisticas recientes")
        primary_label.setStyleSheet("font-weight: 700; color: #e5edf7;")
        primary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        primary_label.setWordWrap(True)

        secondary_label = QLabel(" · ".join(secondary_stats) if secondary_stats else "Sin datos extra")
        secondary_label.setObjectName("Muted")
        secondary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        secondary_label.setWordWrap(True)

        stats_col.addWidget(primary_label)
        stats_col.addWidget(secondary_label)
        stats_col.addStretch(1)

        top_row.addWidget(icon_stack, 0, Qt.AlignTop)
        top_row.addLayout(info_col, 1)
        top_row.addLayout(stats_col, 0)
        root.addLayout(top_row)

        if participant.tags:
            tags = QLabel(" · ".join(participant.tags))
            tags.setObjectName("Muted")
            tags.setWordWrap(True)
            tags.setStyleSheet(
                "color: #93a8c6; background: rgba(11, 21, 40, 0.75); border: 1px solid #22304d; "
                "border-radius: 10px; padding: 6px 8px;"
            )
            root.addWidget(tags)


class LiveMetaChip(QFrame):
    def __init__(self, label: str, value: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("LiveMetaChip")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        value_label = QLabel(value)
        value_label.setObjectName("LiveMetaValue")
        value_label.setStyleSheet(f"color: {accent};")
        value_label.setWordWrap(True)

        label_widget = QLabel(label)
        label_widget.setObjectName("LiveMetaLabel")
        label_widget.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(label_widget)


class LiveGameRow(QFrame):
    def __init__(self, summary: LiveGameParticipantSummary) -> None:
        super().__init__()
        self.summary = summary
        self.setObjectName("LiveMatchCard")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(16)

        icon_shell = QFrame()
        icon_shell.setObjectName("LiveMatchIconShell")
        icon_shell.setFixedSize(72, 72)

        icon_label = QLabel(icon_shell)
        icon_label.setGeometry(8, 8, CHAMPION_ICON_SIZE, CHAMPION_ICON_SIZE)
        icon_label.setStyleSheet("background: transparent;")
        if summary.champion_id > 0:
            icon_label.setPixmap(_load_champion_icon(summary.champion_id))
            icon_label.setScaledContents(True)
        else:
            icon_label.setObjectName("LivePlaceholderGlyph")
            icon_label.setAlignment(Qt.AlignCenter)
            icon_label.setText("LIVE")

        if summary.role in LIVE_ROLE_PRIORITY:
            role_container = QLabel(icon_shell)
            role_container.setGeometry(48, 48, 24, 24)
            role_container.setStyleSheet(
                "background: #0b1528; border: 1px solid #22304d; border-radius: 12px; padding: 1px;"
            )
            role_label = QLabel(role_container)
            role_label.setGeometry(1, 1, 22, 22)
            role_label.setPixmap(_load_role_icon(summary.role))
            role_label.setScaledContents(True)
            role_label.setStyleSheet("background: transparent;")
            role_container.setToolTip(summary.role)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)

        eyebrow = QLabel("LIVE TRACKING")
        eyebrow.setObjectName("LiveMatchEyebrow")

        riot_id = f"{summary.game_name}#{summary.tag_line}" if summary.tag_line else summary.game_name
        title_label = QLabel(riot_id)
        title_label.setObjectName("LiveMatchTitle")
        title_label.setWordWrap(True)

        detail_label = QLabel(summary.status_text or "Partida activa")
        detail_label.setObjectName("LiveMatchDetail")
        detail_label.setWordWrap(True)

        support_parts: list[str] = []
        if summary.mastery_level is not None:
            support_parts.append(f"Maestria M{summary.mastery_level}")
        support_label = QLabel(" · ".join(support_parts))
        support_label.setObjectName("Muted")
        support_label.setWordWrap(True)

        text_col.addWidget(eyebrow)
        text_col.addWidget(title_label)
        text_col.addWidget(detail_label)
        if support_parts:
            text_col.addWidget(support_label)

        header.addWidget(icon_shell, 0, Qt.AlignTop)
        header.addLayout(text_col, 1)
        root.addLayout(header)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(10)
        meta_row.addWidget(LiveMetaChip("Campeon", summary.champion or "Oculto", "#f0d7a2"), 1)
        meta_row.addWidget(LiveMetaChip("Rol", _live_role_display_name(summary.role), "#7cc7ff"), 1)
        meta_row.addWidget(
            LiveMetaChip(
                "Duracion",
                f"{summary.game.duration_min} min" if summary.game and summary.game.duration_min > 0 else "N/D",
                "#9ed07b",
            ),
            1,
        )
        meta_row.addWidget(
            LiveMetaChip(
                "Mapa",
                summary.game.map_name if summary.game and summary.game.map_name else "N/D",
                "#f58ab3",
            ),
            1,
        )
        root.addLayout(meta_row)

        if summary.in_game and summary.participants:
            toggle_button = QPushButton("Ver alineacion completa")
            toggle_button.setObjectName("LiveDetailsButton")
            toggle_button.setCheckable(True)
            toggle_button.setCursor(Qt.PointingHandCursor)

            details_widget = self._build_match_details(summary.participants)
            details_widget.setVisible(False)

            def _toggle_details(checked: bool) -> None:
                toggle_button.setText("Ocultar alineacion" if checked else "Ver alineacion completa")
                details_widget.setVisible(checked)

            toggle_button.toggled.connect(_toggle_details)
            root.addWidget(toggle_button, 0, Qt.AlignLeft)
            root.addWidget(details_widget)

    def _build_match_details(self, participants: list[LiveGamePlayerDetails]) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        blue_team = [participant for participant in participants if participant.team_color == "blue"]
        red_team = [participant for participant in participants if participant.team_color == "red"]

        layout.addWidget(self._build_team_column("Equipo Azul", blue_team, "#7cc7ff"), 1)
        layout.addWidget(self._build_team_column("Equipo Rojo", red_team, "#ff8ea4"), 1)
        return wrapper

    def _build_team_column(self, title: str, participants: list[LiveGamePlayerDetails], accent: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("LiveTeamCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        slots = _live_team_slots(participants)
        title_label = QLabel(title)
        title_label.setObjectName("LiveTeamTitle")
        title_label.setStyleSheet(f"color: {accent};")
        layout.addWidget(title_label)
        meta_parts: list[str] = []

        meta_label = QLabel(" · ".join(meta_parts))
        meta_label.setObjectName("LiveTeamMeta")
        meta_label.setWordWrap(True)

        meta_label.hide()

        for role, participant in slots:
            layout.addWidget(LiveGamePlayerDetailRow(participant, role, accent))
        return frame


class LiveGamePlayerDetailRow(QFrame):
    def __init__(self, participant: LiveGamePlayerDetails | None, role_hint: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("LivePlayerCard" if participant is not None else "LivePlayerPlaceholderCard")
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        icon_shell = QFrame()
        icon_shell.setObjectName("LivePlayerIconShell")
        icon_shell.setFixedSize(58, 58)

        display_role = participant.role if participant is not None and participant.role != "UNKNOWN" else role_hint
        if participant is not None:
            champion_icon = QLabel(icon_shell)
            champion_icon.setGeometry(7, 7, DETAIL_CHAMPION_ICON_SIZE, DETAIL_CHAMPION_ICON_SIZE)
            champion_icon.setPixmap(_load_champion_icon(participant.champion_id))
            champion_icon.setScaledContents(True)
            champion_icon.setStyleSheet("background: transparent; border-radius: 10px;")

            if display_role in LIVE_ROLE_PRIORITY:
                role_container = QLabel(icon_shell)
                role_container.setGeometry(38, 38, 20, 20)
                role_container.setStyleSheet(
                    "background: #0b1528; border: 1px solid #22304d; border-radius: 10px; padding: 1px;"
                )
                role_icon = QLabel(role_container)
                role_icon.setGeometry(1, 1, 18, 18)
                role_icon.setPixmap(_load_role_icon(display_role))
                role_icon.setScaledContents(True)
                role_icon.setStyleSheet("background: transparent;")
                role_container.setToolTip(display_role)
        else:
            placeholder_icon = QLabel(icon_shell)
            placeholder_icon.setGeometry(13, 13, 32, 32)
            placeholder_icon.setAlignment(Qt.AlignCenter)
            if display_role in LIVE_ROLE_PRIORITY:
                placeholder_icon.setPixmap(
                    _load_role_icon(display_role).scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                placeholder_icon.setScaledContents(True)
            else:
                placeholder_icon.setObjectName("LivePlaceholderGlyph")
                placeholder_icon.setText("--")

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(5)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        role_pill = QLabel(_live_role_display_name(display_role))
        role_pill.setObjectName("LiveRolePill")
        accent_color = QColor(accent)
        role_pill.setStyleSheet(
            f"background: rgba({accent_color.red()}, {accent_color.green()}, {accent_color.blue()}, 26);"
            f"border: 1px solid rgba({accent_color.red()}, {accent_color.green()}, {accent_color.blue()}, 120);"
            f"border-radius: 10px; padding: 4px 8px; color: {accent};"
            "font-family: 'Bahnschrift';"
            "font-size: 8.2pt;"
            "font-weight: 700;"
            "letter-spacing: 0.6px;"
        )

        if participant is not None:
            header = QLabel(
                f"{participant.game_name}#{participant.tag_line}"
                if participant.tag_line
                else participant.game_name
            )
            header.setObjectName("LivePlayerName")

            subheader_parts = [participant.champion or "Campeon no detectado"]
            if participant.champion_rank:
                subheader_parts.append(participant.champion_rank)
            subheader = QLabel(" · ".join(subheader_parts))
            subheader.setObjectName("LivePlayerMeta")
            subheader.setWordWrap(True)

            spell_row = QHBoxLayout()
            spell_row.setContentsMargins(0, 0, 0, 0)
            spell_row.setSpacing(6)

            for index, spell_id in enumerate(participant.spell_ids[:2]):
                spell_icon = QLabel()
                spell_icon.setFixedSize(DETAIL_SPELL_ICON_SIZE, DETAIL_SPELL_ICON_SIZE)
                spell_icon.setPixmap(_load_summoner_spell_icon(spell_id))
                spell_icon.setScaledContents(True)
                if index < len(participant.spell_names):
                    spell_icon.setToolTip(participant.spell_names[index])
                spell_row.addWidget(spell_icon, 0, Qt.AlignVCenter)
            spell_row.addStretch(1)

            title_row.addWidget(header, 1)
            title_row.addWidget(role_pill, 0, Qt.AlignTop)

            info_col.addLayout(title_row)
            info_col.addWidget(subheader)
            info_col.addLayout(spell_row)

            stats_col = QVBoxLayout()
            stats_col.setContentsMargins(0, 0, 0, 0)
            stats_col.setSpacing(4)

            primary_stats = []
            if participant.recent_winrate is not None and participant.recent_games is not None:
                primary_stats.append(f"{participant.recent_winrate:.0f}% WR · {participant.recent_games}p")
            if participant.avg_kda:
                primary_stats.append(f"KDA {participant.avg_kda}")

            secondary_stats = []
            if participant.summoner_level > 0:
                secondary_stats.append(f"Nivel {participant.summoner_level}")
            if participant.mastery_level is not None:
                secondary_stats.append(f"M{participant.mastery_level}")
            if participant.champion_rank:
                secondary_stats.append(participant.champion_rank)

            primary_label = QLabel(" · ".join(primary_stats) if primary_stats else "Sin estadisticas recientes")
            primary_label.setObjectName("LivePlayerPrimary")
            primary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            primary_label.setWordWrap(True)

            secondary_label = QLabel(" · ".join(secondary_stats) if secondary_stats else "Sin datos extra")
            secondary_label.setObjectName("LivePlayerMeta")
            secondary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            secondary_label.setWordWrap(True)

            stats_col.addWidget(primary_label)
            stats_col.addWidget(secondary_label)
            stats_col.addStretch(1)

            top_row.addWidget(icon_shell, 0, Qt.AlignTop)
            top_row.addLayout(info_col, 1)
            top_row.addLayout(stats_col, 0)
            root.addLayout(top_row)

            if participant.tags:
                tags = QLabel(" · ".join(participant.tags))
                tags.setObjectName("LivePlayerTag")
                tags.setWordWrap(True)
                root.addWidget(tags)
            return

        header = QLabel("Invocador oculto")
        header.setObjectName("LivePlayerName")

        subheader = QLabel("Modo streamer o fuente incompleta")
        subheader.setObjectName("LivePlayerMeta")
        subheader.setWordWrap(True)

        note = QLabel("Hueco reservado para mantener la composicion del equipo.")
        note.setObjectName("Muted")
        note.setWordWrap(True)

        title_row.addWidget(header, 1)
        title_row.addWidget(role_pill, 0, Qt.AlignTop)

        info_col.addLayout(title_row)
        info_col.addWidget(subheader)
        info_col.addWidget(note)

        top_row.addWidget(icon_shell, 0, Qt.AlignTop)
        top_row.addLayout(info_col, 1)
        root.addLayout(top_row)


class BuildSearchResultRow(QFrame):
    def __init__(self, champion: LolalyticsChampion, open_callback) -> None:
        super().__init__()
        self._icon_url = champion.icon_url
        self._icon_size = BUILDS_RESULT_ICON_SIZE
        self.setObjectName("BuildSearchResultCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        self._icon_refresh_attempts = 0
        self._icon_refresh_timer = QTimer(self)
        self._icon_refresh_timer.setInterval(180)
        self._icon_refresh_timer.timeout.connect(self._refresh_icon)

        icon_shell = QFrame()
        icon_shell.setObjectName("BuildResultIconShell")
        icon_shell.setFixedSize(self._icon_size + 14, self._icon_size + 14)
        icon_shell_layout = QVBoxLayout(icon_shell)
        icon_shell_layout.setContentsMargins(7, 7, 7, 7)
        icon_shell_layout.setSpacing(0)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(self._icon_size, self._icon_size)
        self._icon_label.setStyleSheet("background: transparent;")
        self._refresh_icon()
        if self._icon_url and self._icon_url not in _REMOTE_IMAGE_BYTES_CACHE:
            self._icon_refresh_timer.start()
        icon_shell_layout.addWidget(self._icon_label, 0, Qt.AlignCenter)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)

        name = QLabel(champion.name)
        name.setObjectName("BuildSearchResultName")
        meta = QLabel(f"{champion.slug} · Lolalytics")
        meta.setObjectName("BuildSearchResultMeta")
        meta.setText(f"{champion.slug} / Lolalytics")

        text_col.addWidget(name)
        text_col.addWidget(meta)

        button = QPushButton("Ver build")
        button.setObjectName("BuildInlineButton")
        button.clicked.connect(lambda checked=False: open_callback(champion))

        layout.addWidget(icon_shell, 0, Qt.AlignVCenter)
        layout.addLayout(text_col, 1)
        layout.addWidget(button)

    def _refresh_icon(self) -> None:
        self._icon_label.setPixmap(_load_remote_image(self._icon_url, self._icon_size))
        if not self._icon_url:
            self._icon_refresh_timer.stop()
            return
        if self._icon_url in _REMOTE_IMAGE_BYTES_CACHE and _REMOTE_IMAGE_BYTES_CACHE[self._icon_url]:
            self._icon_refresh_timer.stop()
            return

        self._icon_refresh_attempts += 1
        if self._icon_refresh_attempts >= 50:
            self._icon_refresh_timer.stop()


class BuildAssetIcon(QWidget):
    def __init__(self, asset: LolalyticsAsset, size: int) -> None:
        super().__init__()
        self.asset = asset
        self.setFixedSize(size, size)

        tooltip = asset.name.strip()
        if tooltip:
            self.setToolTip(tooltip)

        icon = QLabel(self)
        icon.setGeometry(0, 0, size, size)
        icon.setPixmap(_load_remote_image(asset.icon_url, size))
        icon.setToolTip(tooltip)
        icon.setStyleSheet(
            f"background: transparent; border: 1px solid #42536d; border-radius: {max(6, size // 5)}px;"
        )

        if asset.label:
            badge_size = max(16, size // 3)
            badge = QLabel(asset.label, self)
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(badge_size, badge_size)
            badge.move(size - badge_size, size - badge_size)
            badge.setStyleSheet(
                "background: rgba(6, 10, 19, 0.95); border: 1px solid #5d7491; "
                "border-radius: 8px; color: #eef4fb; font-size: 8pt; font-weight: 700;"
            )
            badge.setToolTip(tooltip)


class BuildAssetCard(QFrame):
    def __init__(
        self,
        title: str,
        assets: list[LolalyticsAsset],
        accent: str = "#7cc7ff",
        footer: str = "",
        icon_size: int = BUILDS_ASSET_ICON_SIZE,
        show_sequence: bool = False,
        empty_text: str = "Sin datos",
    ) -> None:
        super().__init__()
        self.setObjectName("BuildPanelCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("BuildPanelTitle")
        title_label.setStyleSheet(f"color: {accent};")
        layout.addWidget(title_label)

        if not assets:
            body = QLabel(empty_text)
            body.setObjectName("Muted")
            body.setWordWrap(True)
            layout.addWidget(body)
        else:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            for index, asset in enumerate(assets):
                row.addWidget(BuildAssetIcon(asset, icon_size), 0, Qt.AlignVCenter)
                if show_sequence and index < len(assets) - 1:
                    arrow = QLabel("›")
                    arrow.setStyleSheet("font-size: 16pt; font-weight: 700; color: #96a7c2;")
                    row.addWidget(arrow, 0, Qt.AlignVCenter)
            row.addStretch(1)
            layout.addLayout(row)

        if footer:
            footer_label = QLabel(footer)
            footer_label.setObjectName("Muted")
            footer_label.setWordWrap(True)
            layout.addWidget(footer_label)


class BuildSectionCard(QFrame):
    def __init__(
        self,
        title: str,
        lines: list[str],
        footer: str = "",
        accent: str = "#7cc7ff",
    ) -> None:
        super().__init__()
        self.setObjectName("BuildPanelCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("BuildPanelTitle")
        title_label.setStyleSheet(f"color: {accent};")
        body = QLabel("\n".join(lines) if lines else "Sin datos")
        body.setWordWrap(True)
        body.setStyleSheet("color: #e7edf6;")

        layout.addWidget(title_label)
        layout.addWidget(body)
        if footer:
            footer_label = QLabel(footer)
            footer_label.setObjectName("Muted")
            footer_label.setWordWrap(True)
            layout.addWidget(footer_label)


class BuildItemOptionWidget(QFrame):
    def __init__(self, option: LolalyticsBuildSection, accent: str) -> None:
        super().__init__()
        self.setObjectName("BuildOptionCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        asset = option.items[0] if option.items else None
        if asset is None:
            empty = QLabel("Sin datos")
            empty.setObjectName("Muted")
            empty.setAlignment(Qt.AlignCenter)
            layout.addWidget(empty)
            return

        self.setToolTip(asset.name)
        layout.addWidget(BuildAssetIcon(asset, BUILDS_OPTION_ICON_SIZE), 0, Qt.AlignHCenter)

        win_rate = QLabel(self._format_percent(option.win_rate))
        win_rate.setAlignment(Qt.AlignCenter)
        win_rate.setObjectName("BuildOptionStat")
        win_rate.setStyleSheet(f"font-weight: 700; color: {accent};")

        games = QLabel(self._format_count(option.games))
        games.setAlignment(Qt.AlignCenter)
        games.setObjectName("BuildOptionMeta")

        layout.addWidget(win_rate)
        layout.addWidget(games)

    @staticmethod
    def _format_percent(value: float | None) -> str:
        return f"{value:.2f}%" if value is not None else "N/D"

    @staticmethod
    def _format_count(value: int | None) -> str:
        return f"{value:,}" if value is not None else "N/D"


class BuildItemOptionsCard(QFrame):
    def __init__(self, title: str, options: list[LolalyticsBuildSection], accent: str) -> None:
        super().__init__()
        self.setObjectName("BuildPanelCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("BuildPanelTitle")
        title_label.setStyleSheet(f"color: {accent};")
        layout.addWidget(title_label)

        if not options:
            empty = QLabel("Sin datos")
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            return

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        for index, option in enumerate(options):
            row.addWidget(BuildItemOptionWidget(option, accent))
            if index < len(options) - 1:
                or_label = QLabel("OR")
                or_label.setObjectName("BuildSearchResultMeta")
                row.addWidget(or_label, 0, Qt.AlignVCenter)
        row.addStretch(1)
        layout.addLayout(row)


class BuildSkillOrderCard(QFrame):
    def __init__(
        self,
        rows: list[LolalyticsSkillOrderRow],
        win_rate: float | None,
        games: int | None,
        accent: str = "#7cc7ff",
    ) -> None:
        super().__init__()
        self.setObjectName("BuildPanelCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_label = QLabel("Skill Order")
        title_label.setObjectName("BuildPanelTitle")
        title_label.setStyleSheet(f"color: {accent};")
        layout.addWidget(title_label)

        if not rows:
            empty = QLabel("Sin datos del orden de habilidades.")
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            return

        for row in rows:
            row_layout = QHBoxLayout()
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(1)
            row_layout.addWidget(BuildAssetIcon(row.skill, BUILDS_SKILL_ORDER_ICON_SIZE), 0, Qt.AlignVCenter)

            levels = set(row.levels)
            for level in range(1, 16):
                cell = QLabel(str(level) if level in levels else "")
                cell.setAlignment(Qt.AlignCenter)
                cell.setFixedSize(BUILDS_SKILL_ORDER_CELL_WIDTH, BUILDS_SKILL_ORDER_CELL_HEIGHT)
                if level in levels:
                    cell.setStyleSheet(
                        "background: #3a7e93; border: 1px solid #30687a; color: #f3fbff; font-size: 9pt; font-weight: 700;"
                    )
                else:
                    cell.setStyleSheet(
                        "background: transparent; border: 1px solid #30687a; color: transparent; font-size: 9pt;"
                    )
                row_layout.addWidget(cell, 0, Qt.AlignVCenter)
            row_layout.addStretch(1)
            layout.addLayout(row_layout)

        footer_parts = []
        if win_rate is not None:
            footer_parts.append(f"{win_rate:.2f}% WR")
        if games is not None:
            footer_parts.append(f"{games:,} partidas")
        if footer_parts:
            footer = QLabel(" - ".join(footer_parts))
            footer.setObjectName("Muted")
            footer.setStyleSheet(f"font-weight: 700; color: {accent};")
            layout.addWidget(footer)


class BuildMatchupRow(QFrame):
    def __init__(self, matchup: LolalyticsMatchup, accent: str) -> None:
        super().__init__()
        self.setObjectName("BuildMatchupCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icon = QLabel()
        icon.setFixedSize(BUILDS_MATCHUP_ICON_SIZE, BUILDS_MATCHUP_ICON_SIZE)
        icon.setPixmap(_load_remote_image(_lolalytics_champion_icon_url(matchup.slug), BUILDS_MATCHUP_ICON_SIZE))
        icon.setStyleSheet("background: transparent;")

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(2)
        name = QLabel(matchup.champion)
        name.setObjectName("BuildMatchupName")
        meta = QLabel(f"{matchup.games:,} partidas")
        meta.setObjectName("BuildMatchupMeta")
        left.addWidget(name)
        left.addWidget(meta)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(2)
        wr = QLabel(f"{matchup.win_rate:.2f}% WR")
        wr.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        wr.setObjectName("BuildMatchupStat")
        wr.setStyleSheet(f"color: {accent};")
        delta = QLabel(f"Δ2 {matchup.delta_2:+.2f} · Δ1 {matchup.delta_1:+.2f}")
        delta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        delta.setObjectName("Muted")
        delta.setText(f"D2 {matchup.delta_2:+.2f} / D1 {matchup.delta_1:+.2f}")
        right.addWidget(wr)
        right.addWidget(delta)

        layout.addWidget(icon, 0, Qt.AlignVCenter)
        layout.addLayout(left, 1)
        layout.addLayout(right)


class HomeHeroCard(QFrame):
    def __init__(self, open_players, open_today, open_ranking, open_builds, open_live_games) -> None:
        super().__init__()
        self.setObjectName("HomeHeroCard")
        self.setMinimumHeight(620)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 26, 28, 26)
        root.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        brand_badge = QLabel("League of Legends")
        brand_badge.setObjectName("HomeTopBadge")

        app_badge = QLabel("MMR LoL")
        app_badge.setObjectName("HomeTopBadge")

        top_row.addWidget(brand_badge, 0, Qt.AlignLeft | Qt.AlignTop)
        top_row.addStretch(1)
        top_row.addWidget(app_badge, 0, Qt.AlignRight | Qt.AlignTop)

        root.addLayout(top_row)
        root.addStretch(1)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)

        kicker = QLabel("SoloQ Scouting")
        kicker.setObjectName("HomeKicker")

        title = QLabel("MMR\nLoL Scout")
        title.setObjectName("HomeHugeTitle")

        caption = QLabel("Ranking, builds y partidas activas en una portada más limpia.")
        caption.setText("Elo, MMR, builds y partidas activas del grupo en una sola app.")
        caption.setObjectName("HomeCaption")
        caption.setWordWrap(True)
        caption.setMaximumWidth(420)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 8, 0, 0)
        actions.setSpacing(12)

        primary_button = QPushButton("Jugadores")
        primary_button.setObjectName("HomePrimaryButton")
        primary_button.clicked.connect(open_players)

        actions.addWidget(primary_button)
        actions.addStretch(1)

        content.addWidget(kicker)
        content.addWidget(title)
        content.addWidget(caption)
        content.addLayout(actions)
        root.addLayout(content)
        root.addSpacing(18)

        quick_row = QHBoxLayout()
        quick_row.setContentsMargins(0, 0, 0, 0)
        quick_row.setSpacing(12)

        today_button = HomeQuickActionButton("Hoy", "LP del dia", "today")
        today_button.clicked.connect(open_today)

        ranking_button = HomeQuickActionButton("Ranking", "SoloQ", "ranking")
        ranking_button.clicked.connect(open_ranking)

        builds_button = HomeQuickActionButton("Builds", "Lolalytics", "builds")
        builds_button.clicked.connect(open_builds)

        live_button = HomeQuickActionButton("En partida", "Live", "live")
        live_button.clicked.connect(open_live_games)

        quick_row.addWidget(today_button)
        quick_row.addWidget(ranking_button)
        quick_row.addWidget(builds_button)
        quick_row.addWidget(live_button)
        root.addLayout(quick_row)

        credit = QLabel("Desarrollado por Noel Barcia Almagro")
        credit.setObjectName("HomeCredit")
        credit.setAlignment(Qt.AlignCenter)
        root.addSpacing(10)
        root.addWidget(credit)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
            path = QPainterPath()
            path.addRoundedRect(rect, 34, 34)
            painter.setClipPath(path)

            painter.drawPixmap(0, 0, _get_home_hero_background(max(1, self.width()), max(1, self.height())))

            left_overlay = QLinearGradient(0, 0, self.width() * 0.76, 0)
            left_overlay.setColorAt(0.0, QColor(7, 9, 12, 242))
            left_overlay.setColorAt(0.42, QColor(10, 12, 16, 188))
            left_overlay.setColorAt(0.82, QColor(10, 12, 16, 86))
            left_overlay.setColorAt(1.0, QColor(10, 12, 16, 28))
            painter.fillPath(path, left_overlay)

            bottom_overlay = QLinearGradient(0, self.height() * 0.58, 0, self.height())
            bottom_overlay.setColorAt(0.0, QColor(9, 11, 15, 18))
            bottom_overlay.setColorAt(1.0, QColor(8, 10, 14, 236))
            painter.fillPath(path, bottom_overlay)

            warm_tint = QLinearGradient(0, 0, self.width(), self.height())
            warm_tint.setColorAt(0.0, QColor(201, 164, 107, 34))
            warm_tint.setColorAt(0.55, QColor(201, 164, 107, 10))
            warm_tint.setColorAt(1.0, QColor(201, 164, 107, 0))
            painter.fillPath(path, warm_tint)

            painter.setClipping(False)
            painter.setPen(QPen(QColor("#5a4a33"), 1.4))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect, 34, 34)
            painter.setPen(QPen(QColor(255, 255, 255, 24), 1.0))
            painter.drawRoundedRect(QRectF(8, 8, self.width() - 16, self.height() - 16), 28, 28)
        finally:
            painter.end()


class HomeQuickActionButton(QPushButton):
    def __init__(self, title: str, subtitle: str, icon_key: str) -> None:
        super().__init__()
        self.setObjectName("HomeQuickCardButton")
        self.setCursor(Qt.PointingHandCursor)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(6)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        top_row.addStretch(1)

        icon_shell = QFrame()
        icon_shell.setObjectName("HomeQuickIconShell")
        icon_shell.setFixedSize(46, 46)

        icon_label = QLabel(icon_shell)
        icon_label.setObjectName("HomeQuickCardIcon")
        icon_label.setGeometry(6, 6, 34, 34)
        icon_label.setPixmap(_get_home_action_icon(icon_key, 34))
        icon_label.setScaledContents(True)
        icon_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        top_row.addWidget(icon_shell, 0, Qt.AlignRight | Qt.AlignTop)
        root.addLayout(top_row)

        title_label = QLabel(title)
        title_label.setObjectName("HomeQuickCardTitle")
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("HomeQuickCardSubtitle")
        subtitle_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        text_col.addWidget(title_label, 0, Qt.AlignLeft)
        text_col.addWidget(subtitle_label, 0, Qt.AlignLeft)

        root.addLayout(text_col)


class MainWindow(QMainWindow):
    INITIAL_LOADER_FAILSAFE_MS = 20000

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.worker_threads: dict[str, QThread] = {}
        self.workers: dict[str, QObject] = {}
        self.ranking_summaries: list[PlayerSummary] = []
        self.today_summaries: list[TodayLpSummary] = []
        self.live_game_summaries: list[LiveGameParticipantSummary] = []
        self.build_champions: list[LolalyticsChampion] = []
        self.current_build_detail: LolalyticsBuildDetail | None = None
        self.current_build_champion: LolalyticsChampion | None = None
        self.builds_loaded_once = False
        self.builds_index_loading = False
        self.build_detail_loading = False
        self.builds_render_generation = 0
        self.players_last_column_count = 0
        self.players_last_card_width = 0
        self.players_data_version = 0
        self.players_render_signature: tuple[int, int, int] | None = None
        self.players_render_generation = 0
        self.players_render_queue: list[PlayerSummary] = []
        self.players_render_index = 0
        self.players_render_columns = 1
        self.players_render_card_width = PLAYER_CARD_MIN_WIDTH
        self.players_rendering = False
        self.today_last_column_count = 0
        self.today_last_card_width = 0
        self.settings_unlocked = False
        self.initial_load_started = False
        self.initial_load_pending: set[str] = set()
        self.initial_loader_timed_out = False

        self.setWindowTitle("MMR LoL")
        self.setWindowIcon(QIcon(_get_app_logo(128)))
        self.resize(1280, 900)
        self.setStyleSheet(APP_STYLESHEET)
        self.setPalette(build_palette())

        self.container = QWidget()
        self.container.setObjectName("AppCanvas")
        self.setCentralWidget(self.container)
        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setContentsMargins(20, 20, 20, 20)
        self.root_layout.setSpacing(8)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_home_tab(), "Inicio")
        self.tabs.addTab(self._build_today_tab(), "Hoy")
        self.tabs.addTab(self._build_ranking_tab(), "Ranking")
        self.tabs.addTab(self._build_players_tab(), "Jugadores")
        self.tabs.addTab(self._build_live_games_tab(), "En partida")
        self.tabs.addTab(self._build_builds_tab(), "Builds")
        self.tabs.addTab(self._build_settings_tab(), "Configuración")
        self.tabs.currentChanged.connect(self._handle_tab_changed)
        self.root_layout.addWidget(self.tabs, 1)

        self.loader_overlay = self._build_loader_overlay()
        self.loader_overlay.hide()
        self.loader_hide_timer = QTimer(self)
        self.loader_hide_timer.setSingleShot(True)
        self.loader_hide_timer.timeout.connect(self._handle_initial_loader_timeout)
        self.today_resize_timer = QTimer(self)
        self.today_resize_timer.setSingleShot(True)
        self.today_resize_timer.timeout.connect(self._handle_today_resize_timeout)
        self.players_resize_timer = QTimer(self)
        self.players_resize_timer.setSingleShot(True)
        self.players_resize_timer.timeout.connect(self._handle_players_resize_timeout)
        QTimer.singleShot(0, self._start_initial_load)

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("HeaderCard")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(30, 28, 30, 28)
        layout.setSpacing(24)

        logo_card = QFrame()
        logo_card.setObjectName("HeaderLogoCard")
        logo_card.setFixedSize(112, 112)
        logo_layout = QVBoxLayout(logo_card)
        logo_layout.setContentsMargins(14, 14, 14, 14)
        logo_layout.setAlignment(Qt.AlignCenter)

        logo = QLabel()
        logo.setFixedSize(76, 76)
        logo.setPixmap(_get_app_logo(76))
        logo.setScaledContents(True)
        logo.setStyleSheet("background: transparent;")
        logo_layout.addWidget(logo)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)

        title = QLabel("MMR LoL Scout")
        title.setObjectName("HeaderMainTitle")
        subtitle = QLabel("Ranking, partida en vivo y scouting visual en una interfaz más limpia.")
        subtitle.setText("Elo, MMR, builds y partidas activas del grupo en una sola vista.")
        subtitle.setObjectName("HeaderLead")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(640)

        note = QLabel(
            "Herramienta pensada para uso real entre amigos y como proyecto personal "
            "de producto, UI y experiencia para portfolio."
        )
        note.setObjectName("HeaderNote")
        note.setWordWrap(True)
        note.setMaximumWidth(680)

        content.addWidget(title)
        content.addWidget(subtitle)
        content.addWidget(note)

        divider = QFrame()
        divider.setObjectName("HeaderDivider")
        divider.setFixedWidth(1)
        divider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        context = QVBoxLayout()
        context.setContentsMargins(0, 4, 0, 4)
        context.setSpacing(6)

        context_label = QLabel("Entre amigos")
        context_label.setObjectName("HeaderContextLabel")

        context_value = QLabel("SoloQ, live y builds")
        context_value.setObjectName("HeaderContextValue")

        context_note = QLabel(
            "Una app privada para seguir la soloq de un grupo de jugadores y, "
            "al mismo tiempo, prácticar el desarrollo completo de una app utilizando codex,"
            "para minimizar el tiempo de desarrollo y optimizar prompts a la hora de crear apps."
        )
        context_note.setText(
            "Una app privada para seguir la soloq de un grupo de jugadores y, "
            "al mismo tiempo, prácticar el desarrollo completo de una app utilizando codex,"
            "para minimizar el tiempo de desarrollo y optimizar prompts a la hora de crear apps."
        )
        context_note.setObjectName("HeaderContextNote")
        context_note.setWordWrap(True)
        context_note.setMaximumWidth(270)

        context.addWidget(context_label)
        context.addWidget(context_value)
        context.addWidget(context_note)
        context.addStretch(1)

        layout.addWidget(logo_card, 0, Qt.AlignTop)
        layout.addLayout(content, 1)
        layout.addWidget(divider)
        layout.addLayout(context, 0)
        return frame

    def _build_home_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_header())
        layout.addWidget(
            HomeHeroCard(
                open_players=lambda checked=False: self.tabs.setCurrentIndex(PLAYERS_TAB_INDEX),
                open_today=lambda checked=False: self.tabs.setCurrentIndex(TODAY_TAB_INDEX),
                open_ranking=lambda checked=False: self.tabs.setCurrentIndex(RANKING_TAB_INDEX),
                open_builds=lambda checked=False: self.tabs.setCurrentIndex(BUILDS_TAB_INDEX),
                open_live_games=lambda checked=False: self.tabs.setCurrentIndex(LIVE_GAMES_TAB_INDEX),
            ),
            1,
        )
        return wrapper

    def _build_today_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        controls = QFrame()
        controls.setObjectName("TodayHeroCard")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 16, 18, 16)
        controls_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)

        title = QLabel("Hoy")
        title.setObjectName("TodayHeroTitle")
        subtitle = QLabel("LP netos del grupo desde las 00:00 hasta el momento actual.")
        subtitle.setObjectName("TodayHeroLead")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(560)
        info.addWidget(title)
        info.addWidget(subtitle)

        self.today_button = QPushButton("Actualizar hoy")
        self.today_button.clicked.connect(self.start_today)

        self.today_status_label = QLabel("Pulsa para calcular el balance del dia.")
        self.today_status_label.setObjectName("TodayStatusNotice")
        self.today_status_label.setWordWrap(True)

        top_row.addLayout(info, 1)
        top_row.addWidget(self.today_button)
        controls_layout.addLayout(top_row)
        controls_layout.addWidget(self.today_status_label)

        self.today_stack = QStackedWidget()
        self.today_stack.addWidget(self._build_today_loading_view())

        self.today_area = QScrollArea()
        self.today_area.setWidgetResizable(True)
        self.today_content = QWidget()
        self.today_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.today_grid = QGridLayout(self.today_content)
        self.today_grid.setContentsMargins(0, 0, 0, 0)
        self.today_grid.setHorizontalSpacing(18)
        self.today_grid.setVerticalSpacing(18)
        self.today_grid.setAlignment(Qt.AlignTop)
        self.today_area.setWidget(self.today_content)
        self.today_stack.addWidget(self.today_area)
        self.today_stack.setCurrentIndex(1)

        layout.addWidget(controls)
        layout.addWidget(self.today_stack, 1)
        self._refresh_today_overview()
        return wrapper

    def _build_today_loading_view(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("LoaderShell")
        card.setMaximumWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(10)
        card_layout.setAlignment(Qt.AlignCenter)

        self.today_loader_spinner = LoaderSpinner(card)
        self.today_loader_spinner.setFixedSize(132, 132)

        title = QLabel("Calculando hoy")
        title.setObjectName("LoaderTitle")
        title.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(self.today_loader_spinner, 0, Qt.AlignCenter)
        card_layout.addWidget(title)
        layout.addWidget(card)
        return wrapper

    def _build_today_overview_card(self, label: str, accent: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("TodayOverviewCard")
        card.setMinimumWidth(138)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        value_label = QLabel("--")
        value_label.setObjectName("TodayOverviewValue")
        value_label.setStyleSheet(f"color: {accent};")
        value_label.setWordWrap(True)

        text_label = QLabel(label)
        text_label.setObjectName("TodayOverviewLabel")
        text_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(text_label)
        return card, value_label

    def _refresh_today_overview(self) -> None:
        if not hasattr(self, "today_overview_values"):
            return

        configured_count = len(self._configured_players())
        today_count = len(self.today_summaries) if self.today_summaries else configured_count
        available = [summary.lp_change for summary in self.today_summaries if summary.lp_change is not None]
        positive = sum(1 for change in available if change > 0)
        best = max(available) if available else None
        lowest = min(available) if available else None

        self.today_overview_values["players"].setText(str(today_count))
        self.today_overview_values["positive"].setText(str(positive))
        self.today_overview_values["best"].setText(self._format_lp_delta(best))
        self.today_overview_values["lowest"].setText(self._format_lp_delta(lowest))

    def _build_loader_overlay(self) -> QFrame:
        overlay = QFrame(self.container)
        overlay.setStyleSheet(
            "background: qradialgradient(cx:0.5, cy:0.42, radius:0.9, "
            "stop:0 rgba(24, 28, 36, 244), stop:1 rgba(9, 11, 15, 236));"
            "border: none;"
        )
        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(40, 40, 40, 40)
        overlay_layout.setSpacing(0)
        overlay_layout.setAlignment(Qt.AlignCenter)

        panel = QFrame(overlay)
        panel.setObjectName("LoaderShell")
        panel.setMaximumWidth(540)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(40, 34, 40, 34)
        panel_layout.setSpacing(12)
        panel_layout.setAlignment(Qt.AlignCenter)

        self.loader_spinner = LoaderSpinner(panel)
        self.loader_spinner.setFixedSize(164, 164)

        title = QLabel("Cargando datos iniciales")
        title.setObjectName("LoaderTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setText("Cargando ranking")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        title.setAutoFillBackground(False)
        title.setAttribute(Qt.WA_TranslucentBackground, True)

        status_card = QWidget(panel)
        status_card.setObjectName("LoaderStatusCard")
        status_card.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        status_card.setAutoFillBackground(False)
        status_card.setAttribute(Qt.WA_TranslucentBackground, True)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(18, 14, 18, 14)
        status_layout.setSpacing(6)

        self.loader_message_label = QLabel("Preparando ranking...")
        self.loader_message_label.setObjectName("LoaderStatus")
        self.loader_message_label.setAlignment(Qt.AlignCenter)
        self.loader_message_label.setWordWrap(True)
        self.loader_message_label.setAutoFillBackground(False)
        self.loader_message_label.setAttribute(Qt.WA_TranslucentBackground, True)

        caption = QLabel("Sincronizando datos del ranking")
        caption.setObjectName("LoaderHint")
        caption.setAlignment(Qt.AlignCenter)
        caption.setAutoFillBackground(False)
        caption.setAttribute(Qt.WA_TranslucentBackground, True)

        status_layout.addWidget(self.loader_message_label)
        status_layout.addWidget(caption)

        panel_layout.addWidget(self.loader_spinner, 0, Qt.AlignCenter)
        panel_layout.addWidget(title, 0, Qt.AlignHCenter)
        panel_layout.addWidget(status_card, 0, Qt.AlignHCenter)

        overlay_layout.addWidget(panel, 0, Qt.AlignCenter)
        overlay.raise_()
        return overlay

    def _build_ranking_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        controls = QFrame()
        controls.setObjectName("RankingHeroCard")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 16, 18, 16)
        controls_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)
        title = QLabel("Ranking SoloQ")
        title.setObjectName("RankingHeroTitle")
        subtitle = QLabel("Clasificación de los jugadores configurados por elo de SoloQ.")
        subtitle.setText("Sigue elo, LP y MMR del grupo.")
        subtitle.setObjectName("RankingHeroLead")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(520)
        info.addWidget(title)
        info.addWidget(subtitle)

        self.ranking_button = QPushButton("Actualizar ranking")
        self.ranking_button.clicked.connect(self.start_ranking)

        self.ranking_status_label = QLabel("Pulsa para cargar el ranking.")
        self.ranking_status_label.setObjectName("RankingStatusNotice")
        self.ranking_status_label.setWordWrap(True)

        top_row.addLayout(info, 1)
        top_row.addWidget(self.ranking_button)
        controls_layout.addLayout(top_row)
        controls_layout.addWidget(self.ranking_status_label)

        overview_row = QHBoxLayout()
        overview_row.setContentsMargins(0, 0, 0, 0)
        overview_row.setSpacing(8)

        self.ranking_overview_values: dict[str, QLabel] = {}
        for key, label, accent in (
            ("players", "Jugadores", "#f1eadf"),
            ("best_rank", "Mejor rango", "#d8b379"),
            ("leader_lp", "LP lider", "#c9a46b"),
            ("leader_mmr", "MMR lider", "#8fb9a6"),
        ):
            card, value_label = self._build_ranking_overview_card(label, accent)
            self.ranking_overview_values[key] = value_label
            overview_row.addWidget(card, 1)

        controls_layout.addLayout(overview_row)

        self.ranking_area = QScrollArea()
        self.ranking_area.setWidgetResizable(True)
        self.ranking_content = QWidget()
        self.ranking_layout = QVBoxLayout(self.ranking_content)
        self.ranking_layout.setContentsMargins(0, 0, 0, 0)
        self.ranking_layout.setSpacing(14)
        self.ranking_area.setWidget(self.ranking_content)

        layout.addWidget(controls)
        layout.addWidget(self.ranking_area, 1)
        self._refresh_ranking_overview()
        return wrapper

    def _build_ranking_overview_card(self, label: str, accent: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("RankingOverviewCard")
        card.setMinimumWidth(138)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        value_label = QLabel("--")
        value_label.setObjectName("RankingOverviewValue")
        value_label.setStyleSheet(f"color: {accent};")
        value_label.setWordWrap(True)

        text_label = QLabel(label)
        text_label.setObjectName("RankingOverviewLabel")
        text_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(text_label)
        return card, value_label

    def _build_live_overview_card(self, label: str, accent: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("LiveOverviewCard")
        card.setMinimumWidth(138)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        value_label = QLabel("--")
        value_label.setObjectName("LiveOverviewValue")
        value_label.setStyleSheet(f"color: {accent};")
        value_label.setWordWrap(True)

        text_label = QLabel(label)
        text_label.setObjectName("LiveOverviewLabel")
        text_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(text_label)
        return card, value_label

    def _refresh_live_games_overview(self, summaries: list[LiveGameParticipantSummary] | None = None) -> None:
        if not hasattr(self, "live_games_overview_values"):
            return

        configured_count = len(self._configured_players())
        if summaries is None:
            total_count = configured_count
            in_game_summaries = list(self.live_game_summaries)
        else:
            total_count = len(summaries)
            in_game_summaries = [summary for summary in summaries if summary.in_game]

        self.live_games_overview_values["tracked"].setText(str(total_count))
        self.live_games_overview_values["live"].setText(str(len(in_game_summaries)))

    def _build_players_overview_card(self, label: str, accent: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("PlayersOverviewCard")
        card.setMinimumWidth(138)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        value_label = QLabel("--")
        value_label.setObjectName("PlayersOverviewValue")
        value_label.setStyleSheet(f"color: {accent};")
        value_label.setWordWrap(True)

        text_label = QLabel(label)
        text_label.setObjectName("PlayersOverviewLabel")
        text_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(text_label)
        return card, value_label

    def _refresh_players_overview(self) -> None:
        if not hasattr(self, "players_overview_values"):
            return

        configured_count = len(self._configured_players())
        gallery_count = len(self.ranking_summaries)
        mastery_ready = sum(1 for summary in self.ranking_summaries if summary.top_mastery_champion_id > 0)

        self.players_overview_values["tracked"].setText(str(configured_count))
        self.players_overview_values["gallery"].setText(str(gallery_count if gallery_count else configured_count))
        self.players_overview_values["mastery"].setText(str(mastery_ready))

    def _refresh_group_room(self, full_render: bool = False) -> None:
        del full_render
        self._refresh_today_overview()
        self._refresh_ranking_overview()
        self._refresh_players_overview()
        self._refresh_live_games_overview()

    def _build_builds_overview_card(self, label: str, accent: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setObjectName("BuildsOverviewCard")
        card.setMinimumWidth(138)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        value_label = QLabel("--")
        value_label.setObjectName("BuildsOverviewValue")
        value_label.setStyleSheet(f"color: {accent};")
        value_label.setWordWrap(True)

        text_label = QLabel(label)
        text_label.setObjectName("BuildsOverviewLabel")
        text_label.setWordWrap(True)

        layout.addWidget(value_label)
        layout.addWidget(text_label)
        return card, value_label

    def _refresh_builds_overview(self) -> None:
        if not hasattr(self, "builds_overview_values"):
            return

        query = self.builds_search_input.text().strip().casefold() if hasattr(self, "builds_search_input") else ""
        if self.build_champions:
            result_count = sum(
                1
                for champion in self.build_champions
                if not query or query in champion.name.casefold() or query in champion.slug.casefold()
            )
        else:
            result_count = 0

        detail_value = self.current_build_detail.champion if self.current_build_detail is not None else "--"

        self.builds_overview_values["catalog"].setText(str(len(self.build_champions)))
        self.builds_overview_values["results"].setText(str(result_count))
        self.builds_overview_values["detail"].setText(detail_value)

    def _refresh_ranking_overview(self) -> None:
        if not hasattr(self, "ranking_overview_values"):
            return

        configured_players = len(self._configured_players())
        players_count = len(self.ranking_summaries) if self.ranking_summaries else configured_players
        leader = self.ranking_summaries[0] if self.ranking_summaries else None

        best_rank = "--"
        leader_lp = "--"
        leader_mmr = "--"

        if leader is not None and leader.soloq is not None and leader.soloq.tier:
            best_rank = f"{leader.soloq.tier.title()} {leader.soloq.rank}".strip()
            leader_lp = f"{leader.soloq.league_points} LP"
        elif leader is not None:
            best_rank = "Sin rango" if leader.ranked_available else "Sin SoloQ"
            leader_lp = "N/D"

        if leader is not None and leader.estimated_mmr is not None:
            leader_mmr = str(leader.estimated_mmr)

        self.ranking_overview_values["players"].setText(str(players_count))
        self.ranking_overview_values["best_rank"].setText(best_rank)
        self.ranking_overview_values["leader_lp"].setText(leader_lp)
        self.ranking_overview_values["leader_mmr"].setText(leader_mmr)

    def _build_players_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        controls = QFrame()
        controls.setObjectName("PlayersHeroCard")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 16, 18, 16)
        controls_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)

        title = QLabel("Galeria de jugadores")
        title.setObjectName("PlayersHeroTitle")
        subtitle = QLabel(
            "Galería visual por cuenta basada en su campeón con más maestria y su loading screen base."
        )
        subtitle.setObjectName("PlayersHeroLead")
        subtitle.setWordWrap(True)
        subtitle.setText("Cada cuenta muestra su campeon principal y su maestria.")
        subtitle.setMaximumWidth(560)
        info.addWidget(title)
        info.addWidget(subtitle)

        self.players_refresh_button = QPushButton("Actualizar jugadores")
        self.players_refresh_button.clicked.connect(self.start_ranking)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)
        right_col.setAlignment(Qt.AlignRight | Qt.AlignTop)

        self.players_status_label = QLabel("La galería se llenara con el ranking actual.")
        self.players_status_label.setObjectName("PlayersStatusNotice")
        self.players_status_label.setWordWrap(True)
        self.players_status_label.setText("La galeria se actualiza con el ranking actual.")

        top_row.addLayout(info, 1)
        right_col.addWidget(self.players_refresh_button, 0, Qt.AlignRight)
        top_row.addLayout(right_col)
        controls_layout.addLayout(top_row)
        controls_layout.addWidget(self.players_status_label)

        self.players_stack = QStackedWidget()
        self.players_stack.addWidget(self._build_players_loading_view())

        self.players_area = QScrollArea()
        self.players_area.setWidgetResizable(True)
        self.players_content = QWidget()
        self.players_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.players_grid = QGridLayout(self.players_content)
        self.players_grid.setContentsMargins(0, 0, 0, 0)
        self.players_grid.setHorizontalSpacing(20)
        self.players_grid.setVerticalSpacing(20)
        self.players_grid.setAlignment(Qt.AlignTop)
        self.players_area.setWidget(self.players_content)
        self.players_stack.addWidget(self.players_area)
        self.players_stack.setCurrentIndex(1)

        layout.addWidget(controls)
        layout.addWidget(self.players_stack, 1)
        self._refresh_players_overview()
        self._render_players()
        return wrapper

    def _build_players_loading_view(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("LoaderShell")
        card.setMaximumWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(10)
        card_layout.setAlignment(Qt.AlignCenter)

        self.players_loader_spinner = LoaderSpinner(card)
        self.players_loader_spinner.setFixedSize(132, 132)

        title = QLabel("Cargando galería")
        title.setObjectName("LoaderTitle")
        title.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(self.players_loader_spinner, 0, Qt.AlignCenter)
        card_layout.addWidget(title)
        layout.addWidget(card)
        return wrapper

    def _build_live_games_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        controls = QFrame()
        controls.setObjectName("LiveHeroCard")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 16, 18, 16)
        controls_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)

        title = QLabel("Radar de partidas")
        title.setObjectName("LiveHeroTitle")

        subtitle = QLabel(
            "Consulta quien esta jugando ahora y revisa la composicion de cada partida incluso con streamer mode."
        )
        subtitle.setObjectName("LiveHeroLead")
        subtitle.setWordWrap(True)
        subtitle.setText("Comprueba quien esta jugando y revisa la alineacion.")
        subtitle.setMaximumWidth(560)

        info.addWidget(title)
        info.addWidget(subtitle)

        self.live_games_button = QPushButton("Actualizar partidas")
        self.live_games_button.clicked.connect(self.start_live_games)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(0)
        right_col.setAlignment(Qt.AlignRight | Qt.AlignTop)

        self.live_games_status_label = QLabel("Pulsa para buscar partidas activas.")
        self.live_games_status_label.setObjectName("LiveStatusNotice")
        self.live_games_status_label.setWordWrap(True)

        top_row.addLayout(info, 1)
        right_col.addWidget(self.live_games_button, 0, Qt.AlignRight)
        top_row.addLayout(right_col)
        controls_layout.addLayout(top_row)

        overview_row = QHBoxLayout()
        overview_row.setContentsMargins(0, 0, 0, 0)
        overview_row.setSpacing(8)

        self.live_games_overview_values: dict[str, QLabel] = {}
        for key, label, accent in (
            ("tracked", "Configurados", "#f1eadf"),
            ("live", "En vivo", "#d8b379"),
        ):
            card, value_label = self._build_live_overview_card(label, accent)
            self.live_games_overview_values[key] = value_label
            overview_row.addWidget(card, 1)

        controls_layout.addLayout(overview_row)
        controls_layout.addWidget(self.live_games_status_label)

        self.live_games_area = QScrollArea()
        self.live_games_area.setWidgetResizable(True)
        self.live_games_content = QWidget()
        self.live_games_layout = QVBoxLayout(self.live_games_content)
        self.live_games_layout.setContentsMargins(0, 0, 0, 0)
        self.live_games_layout.setSpacing(16)
        self.live_games_area.setWidget(self.live_games_content)

        layout.addWidget(controls)
        layout.addWidget(self.live_games_area, 1)
        self._refresh_live_games_overview()
        return wrapper

    def _build_builds_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        controls = QFrame()
        controls.setObjectName("BuildsHeroCard")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(18, 16, 18, 16)
        controls_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(12)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)

        title = QLabel("Builds y matchups")
        title.setObjectName("BuildsHeroTitle")
        subtitle = QLabel("Explora campeones, builds optimas y counters en una sola vista.")
        subtitle.setObjectName("BuildsHeroLead")
        subtitle.setWordWrap(True)
        subtitle.setText("Busca campeones y abre build o counters sin perder sitio.")
        subtitle.setMaximumWidth(560)
        info.addWidget(title)
        info.addWidget(subtitle)

        self.builds_back_button = QPushButton("Volver")
        self.builds_back_button.clicked.connect(self._show_build_search_results)
        self.builds_back_button.hide()

        self.builds_refresh_button = QPushButton("Actualizar Builds")
        self.builds_refresh_button.clicked.connect(self._handle_builds_refresh_clicked)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(6)
        right_col.setAlignment(Qt.AlignRight | Qt.AlignTop)

        top_row.addLayout(info, 1)
        right_col.addWidget(self.builds_back_button, 0, Qt.AlignRight)
        right_col.addWidget(self.builds_refresh_button, 0, Qt.AlignRight)
        top_row.addLayout(right_col)

        self.builds_search_input = QLineEdit()
        self.builds_search_input.setObjectName("BuildsSearchInput")
        self.builds_search_input.setPlaceholderText("Busca un campeón...")
        self.builds_search_input.textChanged.connect(self._filter_builds_results)
        self.builds_search_input.setPlaceholderText("Busca un campeon...")

        self.builds_status_label = QLabel("Abre la pestaña para cargar el catálogo de campeones.")
        self.builds_status_label.setObjectName("BuildsStatusNotice")
        self.builds_status_label.setWordWrap(True)
        self.builds_status_label.setText("Abre la pestana para cargar el catalogo de campeones.")

        controls_layout.addLayout(top_row)
        overview_row = QHBoxLayout()
        overview_row.setContentsMargins(0, 0, 0, 0)
        overview_row.setSpacing(8)

        self.builds_overview_values: dict[str, QLabel] = {}
        for key, label, accent in (
            ("catalog", "Catalogo", "#f1eadf"),
            ("results", "Resultados", "#d8b379"),
            ("detail", "Ultimo detalle", "#8fb9a6"),
        ):
            card, value_label = self._build_builds_overview_card(label, accent)
            self.builds_overview_values[key] = value_label
            overview_row.addWidget(card, 1)

        controls_layout.addLayout(overview_row)
        controls_layout.addWidget(self.builds_search_input)
        controls_layout.addWidget(self.builds_status_label)

        self.builds_stack = QStackedWidget()
        self.builds_stack.addWidget(self._build_builds_results_view())
        self.builds_stack.addWidget(self._build_builds_detail_view())
        self._render_build_search_results([])

        layout.addWidget(controls)
        layout.addWidget(self.builds_stack, 1)
        self._refresh_builds_overview()
        return wrapper

    def _build_builds_results_view(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.builds_results_area = QScrollArea()
        self.builds_results_area.setWidgetResizable(True)
        self.builds_results_content = QWidget()
        self.builds_results_layout = QVBoxLayout(self.builds_results_content)
        self.builds_results_layout.setContentsMargins(0, 0, 0, 0)
        self.builds_results_layout.setSpacing(12)
        self.builds_results_area.setWidget(self.builds_results_content)

        layout.addWidget(self.builds_results_area, 1)
        return wrapper

    def _build_builds_detail_view(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.builds_detail_area = QScrollArea()
        self.builds_detail_area.setWidgetResizable(True)
        self.builds_detail_content = QWidget()
        self.builds_detail_layout = QVBoxLayout(self.builds_detail_content)
        self.builds_detail_layout.setContentsMargins(0, 0, 0, 0)
        self.builds_detail_layout.setSpacing(14)
        self.builds_detail_area.setWidget(self.builds_detail_content)

        layout.addWidget(self.builds_detail_area, 1)
        return wrapper

    def _build_settings_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        header = QFrame()
        header.setObjectName("Card")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 18, 20, 18)
        header_layout.setSpacing(8)

        title = QLabel("Configuración")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Gestiona los jugadores por defecto y el acceso a la carga de datos.")
        subtitle.setObjectName("SectionLead")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        self.settings_stack = QStackedWidget()
        self.settings_stack.addWidget(self._build_settings_login_view())
        self.settings_stack.addWidget(self._build_settings_editor_view())

        layout.addWidget(header)
        layout.addWidget(self.settings_stack, 1)
        self._set_settings_unlocked(False)
        return wrapper

    def _build_settings_login_view(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)

        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumWidth(420)
        card.setMaximumWidth(420)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 30, 32, 30)
        card_layout.setSpacing(18)

        title = QLabel("Configuración")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignCenter)

        form = QVBoxLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(14)

        self.settings_username_input = QLineEdit()
        self.settings_username_input.setObjectName("LoginInput")
        self.settings_username_input.setPlaceholderText("Usuario")
        self.settings_username_input.setMinimumHeight(42)

        self.settings_password_input = QLineEdit()
        self.settings_password_input.setObjectName("LoginInput")
        self.settings_password_input.setPlaceholderText("Contraseña")
        self.settings_password_input.setEchoMode(QLineEdit.Password)
        self.settings_password_input.setMinimumHeight(42)
        self.settings_password_input.returnPressed.connect(self._attempt_settings_login)

        form.addWidget(self.settings_username_input)
        form.addWidget(self.settings_password_input)

        login_button = QPushButton("Entrar")
        login_button.setObjectName("LoginButton")
        login_button.setMinimumHeight(48)
        login_button.clicked.connect(self._attempt_settings_login)

        self.settings_login_status = QLabel("Credenciales incorrectas.")
        self.settings_login_status.setObjectName("LoginStatus")
        self.settings_login_status.setAlignment(Qt.AlignCenter)
        self.settings_login_status.setWordWrap(True)
        self.settings_login_status.hide()

        card_layout.addWidget(title)
        card_layout.addLayout(form)
        card_layout.addWidget(login_button)
        card_layout.addWidget(self.settings_login_status)

        layout.addWidget(card, 0, Qt.AlignTop | Qt.AlignHCenter)
        layout.addStretch(1)
        return wrapper

    def _build_settings_editor_view(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        credentials_card = QFrame()
        credentials_card.setObjectName("Card")
        credentials_layout = QFormLayout(credentials_card)
        credentials_layout.setContentsMargins(20, 18, 20, 18)
        credentials_layout.setHorizontalSpacing(12)
        credentials_layout.setVerticalSpacing(12)

        self.settings_api_key_input = QLineEdit()
        self.settings_api_key_input.setPlaceholderText("Necesaria para espectear")
        self.settings_default_platform_combo = QComboBox()
        self.settings_default_platform_combo.addItems(PLATFORMS)
        self.settings_lol_game_path_input = QLineEdit()
        self.settings_lol_game_path_input.setPlaceholderText(
            r"C:\Riot Games\League of Legends\Game\League of Legends.exe"
        )

        credentials_layout.addRow("API Key Riot", self.settings_api_key_input)
        credentials_layout.addRow("Plataforma por defecto", self.settings_default_platform_combo)
        credentials_layout.addRow("Ruta de League", self.settings_lol_game_path_input)

        players_card = QFrame()
        players_card.setObjectName("Card")
        players_layout = QVBoxLayout(players_card)
        players_layout.setContentsMargins(20, 18, 20, 18)
        players_layout.setSpacing(14)

        players_title = QLabel("Jugadores por defecto")
        players_title.setStyleSheet("font-size: 15pt; font-weight: 700;")
        players_subtitle = QLabel("Puedes editar, anadir o eliminar Riot IDs usados en ranking y partidas.")
        players_subtitle.setObjectName("Muted")
        players_subtitle.setWordWrap(True)

        self.settings_players_area = QScrollArea()
        self.settings_players_area.setWidgetResizable(True)
        self.settings_players_content = QWidget()
        self.settings_players_layout = QVBoxLayout(self.settings_players_content)
        self.settings_players_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_players_layout.setSpacing(12)
        self.settings_players_area.setWidget(self.settings_players_content)

        actions = QHBoxLayout()
        add_button = QPushButton("Anadir jugador")
        add_button.clicked.connect(lambda: self._add_settings_player_row("", ""))
        save_button = QPushButton("Guardar cambios")
        save_button.clicked.connect(self._save_settings)
        lock_button = QPushButton("Bloquear")
        lock_button.clicked.connect(lambda: self._set_settings_unlocked(False))
        actions.addWidget(add_button)
        actions.addStretch(1)
        actions.addWidget(lock_button)
        actions.addWidget(save_button)

        self.settings_editor_status = QLabel("Configura los jugadores que se usan por defecto.")
        self.settings_editor_status.setObjectName("Muted")
        self.settings_editor_status.setWordWrap(True)

        players_layout.addWidget(players_title)
        players_layout.addWidget(players_subtitle)
        players_layout.addWidget(self.settings_players_area, 1)
        players_layout.addLayout(actions)
        players_layout.addWidget(self.settings_editor_status)

        layout.addWidget(credentials_card)
        layout.addWidget(players_card, 1)
        return wrapper

    def _configured_players(self) -> list[tuple[str, str]]:
        return [
            (str(player[0]).strip(), str(player[1]).strip())
            for player in self.config.ranking_players or []
            if len(player) == 2 and str(player[0]).strip() and str(player[1]).strip()
        ]

    def _set_settings_unlocked(self, unlocked: bool) -> None:
        self.settings_unlocked = unlocked
        self.settings_stack.setCurrentIndex(1 if unlocked else 0)
        if unlocked:
            self._populate_settings_editor()
            self.settings_login_status.setText("Acceso concedido.")
            self.settings_login_status.hide()
            self.settings_password_input.clear()
        else:
            self.settings_password_input.clear()
            self.settings_login_status.hide()
            self.settings_editor_status.setText("Configura los jugadores que se usan por defecto.")

    def _attempt_settings_login(self) -> None:
        username = self.settings_username_input.text().strip()
        password = self.settings_password_input.text().strip()
        if username == SETTINGS_USERNAME and password == SETTINGS_PASSWORD:
            self._set_settings_unlocked(True)
            return

        self.settings_login_status.setText("Credenciales incorrectas.")
        self.settings_login_status.show()
        self.settings_password_input.clear()

    def _populate_settings_editor(self) -> None:
        self.settings_api_key_input.setText(self.config.api_key)
        self.settings_default_platform_combo.setCurrentText(self.config.default_platform)
        self.settings_lol_game_path_input.setText(self.config.lol_game_path)
        self._clear_layout(self.settings_players_layout)
        for game_name, tag_line in self._configured_players():
            self._add_settings_player_row(game_name, tag_line)
        self.settings_players_layout.addStretch(1)

    def _add_settings_player_row(self, game_name: str, tag_line: str) -> None:
        self._remove_settings_players_stretch()
        row = PlayerConfigRow(game_name, tag_line)
        row.remove_button.clicked.connect(lambda checked=False, widget=row: self._remove_settings_player_row(widget))
        self.settings_players_layout.addWidget(row)
        self.settings_players_layout.addStretch(1)

    def _remove_settings_player_row(self, row: PlayerConfigRow | None) -> None:
        if row is None:
            return
        self._remove_settings_players_stretch()
        self.settings_players_layout.removeWidget(row)
        row.deleteLater()
        self.settings_players_layout.addStretch(1)

    def _remove_settings_players_stretch(self) -> None:
        count = self.settings_players_layout.count()
        if count == 0:
            return
        last_item = self.settings_players_layout.itemAt(count - 1)
        if last_item is not None and last_item.spacerItem() is not None:
            self.settings_players_layout.takeAt(count - 1)

    def _save_settings(self) -> None:
        players: list[list[str]] = []
        for index in range(self.settings_players_layout.count()):
            item = self.settings_players_layout.itemAt(index)
            widget = item.widget()
            if not isinstance(widget, PlayerConfigRow):
                continue
            game_name, tag_line = widget.values()
            if not game_name or not tag_line:
                continue
            players.append([game_name, tag_line])

        if not players:
            QMessageBox.warning(self, "Configuración invalida", "Debes guardar al menos un jugador.")
            return

        self.config.api_key = self.settings_api_key_input.text().strip()
        self.config.default_platform = self.settings_default_platform_combo.currentText()
        self.config.lol_game_path = self.settings_lol_game_path_input.text().strip()
        self.config.ranking_players = players
        save_config(self.config)
        self._refresh_players_overview()
        self._refresh_live_games_overview()

        self.settings_editor_status.setText(f"Configuración guardada. {len(players)} jugadores cargados.")
        self.today_status_label.setText("Configuración actualizada. Pulsa para recalcular Hoy.")
        self.ranking_status_label.setText("Configuración actualizada. Pulsa para refrescar el ranking.")
        self.players_status_label.setText("Configuración actualizada. Pulsa para refrescar la galería.")
        self.live_games_status_label.setText("Configuración actualizada. Pulsa para refrescar partidas.")

    def _handle_tab_changed(self, index: int) -> None:
        if index == TODAY_TAB_INDEX and not self.today_summaries and "today" not in self.worker_threads:
            self._start_today(show_dialog=False, force_refresh=False)
        if index == TODAY_TAB_INDEX and self.today_summaries:
            QTimer.singleShot(0, self._render_today)
        if index == PLAYERS_TAB_INDEX and self.ranking_summaries:
            QTimer.singleShot(0, self._render_players)
        if index == BUILDS_TAB_INDEX and not self.builds_loaded_once and not self.builds_index_loading:
            self._start_builds_index(show_dialog=False, force_refresh=False)

    def _preload_builds_index_if_idle(self) -> None:
        if self.builds_loaded_once or self.builds_index_loading or self.build_detail_loading:
            return
        if "builds_index" in self.worker_threads:
            return
        self._start_builds_index(show_dialog=False, force_refresh=False)

    def _prefetch_all_builds_index_assets_async(self, champions: list[LolalyticsChampion]) -> None:
        if not champions:
            return

        def _run_prefetch() -> None:
            try:
                BuildsIndexWorker._prefetch_assets(champions)
            except Exception:
                return

        Thread(target=_run_prefetch, daemon=True).start()

    def _handle_builds_refresh_clicked(self) -> None:
        if self.builds_stack.currentIndex() == 1 and self.current_build_champion is not None:
            self._start_build_detail(self.current_build_champion, show_dialog=True, force_refresh=True)
            return
        self._start_builds_index(show_dialog=True, force_refresh=True)

    def _start_builds_index(self, show_dialog: bool, force_refresh: bool = False) -> bool:
        if "builds_index" in self.worker_threads:
            return False

        self.builds_index_loading = True
        self.builds_refresh_button.setEnabled(False)
        self.builds_status_label.setText("Actualizando catálogo de Builds..." if force_refresh else "Cargando catálogo de Builds...")
        self._show_build_search_results()
        self._render_build_search_results([])
        self._start_worker(
            "builds_index",
            BuildsIndexWorker(force_refresh=force_refresh),
            self._on_builds_index_success,
            lambda message: self._handle_builds_index_failed(message, show_dialog),
            self.builds_status_label,
        )
        return True

    def _on_builds_index_success(self, champions: list[LolalyticsChampion]) -> None:
        self.builds_index_loading = False
        self.builds_loaded_once = True
        self.builds_refresh_button.setEnabled(True)
        self.build_champions = champions
        self._prefetch_all_builds_index_assets_async(champions)
        self._refresh_builds_overview()
        self.builds_status_label.setText(f"Catálogo listo. {len(champions)} campeones disponibles.")
        try:
            self._filter_builds_results()
        except Exception as exc:
            self.builds_status_label.setText(f"No se pudo mostrar el catálogo de Builds: {exc}")
            self._render_build_search_results([])

    def _handle_builds_index_failed(self, message: str, show_dialog: bool) -> None:
        self.builds_index_loading = False
        self.builds_refresh_button.setEnabled(True)
        self.builds_status_label.setText(message)
        self._refresh_builds_overview()
        self._render_build_search_results([])
        if show_dialog:
            QMessageBox.critical(self, "Error", message)

    def _filter_builds_results(self) -> None:
        query = self.builds_search_input.text().strip().casefold()
        if self.builds_stack.currentIndex() == 1:
            self._show_build_search_results()

        if not self.build_champions:
            self._render_build_search_results([])
            return

        filtered = [
            champion
            for champion in self.build_champions
            if not query
            or query in champion.name.casefold()
            or query in champion.slug.casefold()
        ]
        if query:
            self.builds_status_label.setText(f"{len(filtered)} resultados para \"{self.builds_search_input.text().strip()}\".")
        else:
            self.builds_status_label.setText(f"Catálogo listo. {len(filtered)} campeones disponibles.")
        self._refresh_builds_overview()
        self._render_build_search_results(filtered)

    def _append_build_search_results_batch(
        self,
        champions: list[LolalyticsChampion],
        start_index: int,
        generation: int,
    ) -> None:
        if generation != self.builds_render_generation:
            return

        end_index = min(len(champions), start_index + BUILDS_SEARCH_RENDER_BATCH_SIZE)
        for champion in champions[start_index:end_index]:
            self.builds_results_layout.addWidget(BuildSearchResultRow(champion, self._open_build_detail))

        if end_index < len(champions):
            QTimer.singleShot(
                0,
                lambda champs=champions, next_index=end_index, current_generation=generation: self._append_build_search_results_batch(
                    champs,
                    next_index,
                    current_generation,
                ),
            )
            return

        self.builds_results_layout.addStretch(1)

    def _render_build_search_results(self, champions: list[LolalyticsChampion]) -> None:
        self.builds_render_generation += 1
        generation = self.builds_render_generation
        self._clear_layout(self.builds_results_layout)
        if not self.build_champions:
            loading = QLabel(
                "Cargando catálogo de campeones..." if self.builds_index_loading else "Abre la pestaña para cargar el catálogo."
            )
            if self.builds_index_loading:
                self.builds_results_layout.addStretch(1)
                self.builds_results_layout.addWidget(
                    InlineLoaderCard(
                        "Cargando Builds",
                    ),
                    0,
                    Qt.AlignCenter,
                )
            else:
                loading.setObjectName("Muted")
                loading.setWordWrap(True)
                self.builds_results_layout.addWidget(loading)
            self.builds_results_layout.addStretch(1)
            return

        if not champions:
            empty = QLabel("No hay campeones que coincidan con la busqueda.")
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            self.builds_results_layout.addWidget(empty)
            self.builds_results_layout.addStretch(1)
            return

        self._append_build_search_results_batch(champions, 0, generation)

    def _open_build_detail(self, champion: LolalyticsChampion) -> None:
        self._start_build_detail(champion, show_dialog=True, force_refresh=False)

    def _start_build_detail(
        self,
        champion: LolalyticsChampion,
        show_dialog: bool,
        force_refresh: bool = False,
    ) -> bool:
        if "build_detail" in self.worker_threads:
            return False

        self.current_build_champion = champion
        self.current_build_detail = None
        self.build_detail_loading = True
        self.builds_back_button.setVisible(True)
        self.builds_back_button.setEnabled(False)
        self.builds_refresh_button.setEnabled(False)
        self.builds_stack.setCurrentIndex(1)
        self._clear_layout(self.builds_detail_layout)
        self.builds_detail_layout.addStretch(1)
        self.builds_detail_layout.addWidget(
            InlineLoaderCard(
                f"Cargando build de {champion.name}",
            ),
            0,
            Qt.AlignCenter,
        )
        self.builds_detail_layout.addStretch(1)
        self.builds_status_label.setText(
            f"Actualizando build de {champion.name}..." if force_refresh else f"Cargando build de {champion.name}..."
        )
        self._start_worker(
            "build_detail",
            BuildDetailWorker(champion, force_refresh=force_refresh),
            self._on_build_detail_success,
            lambda message: self._handle_build_detail_failed(message, show_dialog),
            self.builds_status_label,
        )
        return True

    def _on_build_detail_success(self, detail: LolalyticsBuildDetail) -> None:
        self.build_detail_loading = False
        self.current_build_detail = detail
        self.builds_back_button.setEnabled(True)
        self.builds_refresh_button.setEnabled(True)
        self.builds_status_label.setText(f"Build de {detail.champion} cargada desde Lolalytics.")
        self._refresh_builds_overview()
        try:
            self._render_build_detail(detail)
        except Exception as exc:
            self.current_build_detail = None
            self.builds_status_label.setText(f"No se pudo mostrar la build de {detail.champion}: {exc}")
            self._show_build_search_results()
            QMessageBox.critical(self, "Error", f"No se pudo mostrar la build de {detail.champion}: {exc}")

    def _handle_build_detail_failed(self, message: str, show_dialog: bool) -> None:
        self.build_detail_loading = False
        self.builds_back_button.setEnabled(True)
        self.builds_refresh_button.setEnabled(True)
        self.builds_status_label.setText(message)
        self._refresh_builds_overview()
        if self.current_build_detail is None:
            self._show_build_search_results()
        if show_dialog:
            QMessageBox.critical(self, "Error", message)

    def _show_build_search_results(self) -> None:
        self.builds_stack.setCurrentIndex(0)
        self.builds_back_button.hide()
        self.builds_back_button.setEnabled(True)
        self.builds_refresh_button.setEnabled(not self.builds_index_loading and not self.build_detail_loading)
        self._refresh_builds_overview()

    def _render_build_detail(self, detail: LolalyticsBuildDetail) -> None:
        self._clear_layout(self.builds_detail_layout)

        hero = QFrame()
        hero.setObjectName("BuildDetailHeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(16)

        hero_top = QHBoxLayout()
        hero_top.setContentsMargins(0, 0, 0, 0)
        hero_top.setSpacing(18)

        icon_shell = QFrame()
        icon_shell.setObjectName("BuildDetailIconShell")
        icon_shell.setFixedSize(98, 98)
        icon_shell_layout = QVBoxLayout(icon_shell)
        icon_shell_layout.setContentsMargins(5, 5, 5, 5)
        icon_shell_layout.setSpacing(0)

        icon = QLabel()
        icon.setFixedSize(88, 88)
        icon.setPixmap(_load_remote_image(detail.icon_url, 88))
        icon.setScaledContents(True)
        icon.setStyleSheet("background: transparent;")
        icon_shell_layout.addWidget(icon, 0, Qt.AlignCenter)

        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(6)

        eyebrow = QLabel("LOLALYTICS DOSSIER")
        eyebrow.setObjectName("BuildDetailEyebrow")

        title = QLabel(detail.champion)
        title.setObjectName("BuildDetailTitle")

        meta_parts = []
        if detail.role:
            meta_parts.append(detail.role)
        if detail.patch:
            meta_parts.append(f"Patch {detail.patch}")
        if detail.tier:
            meta_parts.append(f"Tier {detail.tier}")
        if detail.rank_label:
            meta_parts.append(f"Rank {detail.rank_label}")
        meta = QLabel(" · ".join(meta_parts) if meta_parts else "Build optima de Lolalytics")
        meta.setObjectName("BuildDetailMeta")
        meta.setWordWrap(True)
        meta.setText(" / ".join(meta_parts) if meta_parts else "Build optima de Lolalytics")

        summary = QLabel(detail.summary or "Sin resumen disponible.")
        summary.setWordWrap(True)
        summary.setObjectName("BuildDetailSummary")

        info_col.addWidget(eyebrow)
        info_col.addWidget(title)
        info_col.addWidget(meta)
        info_col.addWidget(summary)

        actions = QVBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        if detail.build_url:
            open_build_button = QPushButton("Abrir Build")
            open_build_button.setObjectName("BuildInlineButton")
            open_build_button.clicked.connect(
                lambda checked=False, url=detail.build_url: QDesktopServices.openUrl(QUrl(url))
            )
            actions.addWidget(open_build_button)
        if detail.counters_url:
            open_counters_button = QPushButton("Abrir Counters")
            open_counters_button.setObjectName("BuildInlineButton")
            open_counters_button.clicked.connect(
                lambda checked=False, url=detail.counters_url: QDesktopServices.openUrl(QUrl(url))
            )
            actions.addWidget(open_counters_button)
        actions.addStretch(1)

        hero_top.addWidget(icon_shell, 0, Qt.AlignTop)
        hero_top.addLayout(info_col, 1)
        hero_top.addLayout(actions)
        hero_layout.addLayout(hero_top)

        stats_row = QHBoxLayout()
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setSpacing(10)
        stats_row.addWidget(
            StatCard("Winrate", self._format_percent(detail.win_rate), accent="#7cc7ff", style_variant="ranking")
        )
        stats_row.addWidget(
            StatCard("Pick", self._format_percent(detail.pick_rate), accent="#ffbf69", style_variant="ranking")
        )
        stats_row.addWidget(
            StatCard("Ban", self._format_percent(detail.ban_rate), accent="#f58ab3", style_variant="ranking")
        )
        stats_row.addWidget(
            StatCard("Partidas", self._format_count(detail.games), accent="#9ed07b", style_variant="ranking")
        )
        hero_layout.addLayout(stats_row)

        quick_grid = QGridLayout()
        quick_grid.setContentsMargins(0, 0, 0, 0)
        quick_grid.setHorizontalSpacing(12)
        quick_grid.setVerticalSpacing(12)
        quick_grid.addWidget(
            BuildAssetCard(
                "Hechizos",
                detail.summoner_spells,
                accent="#7cc7ff",
                icon_size=BUILDS_ASSET_ICON_SIZE,
            ),
            0,
            0,
        )
        quick_grid.addWidget(
            BuildAssetCard(
                "Skill Priority",
                detail.skill_priority,
                accent="#f58ab3",
                icon_size=BUILDS_ASSET_ICON_SIZE,
                show_sequence=True,
            ),
            0,
            1,
        )
        quick_grid.addWidget(
            BuildAssetCard(
                "Runas Primarias",
                detail.primary_runes,
                accent="#ffbf69",
                icon_size=BUILDS_RUNE_ICON_SIZE,
            ),
            1,
            0,
        )
        quick_grid.addWidget(
            BuildAssetCard(
                "Runas Secundarias",
                detail.secondary_runes,
                accent="#9ed07b",
                icon_size=BUILDS_RUNE_ICON_SIZE,
            ),
            1,
            1,
        )
        hero_layout.addLayout(quick_grid)
        hero_layout.addWidget(
            BuildSkillOrderCard(
                detail.skill_order,
                detail.skill_order_win_rate,
                detail.skill_order_games,
                accent="#72d8a4",
            )
        )
        self.builds_detail_layout.addWidget(hero)

        build_grid = QGridLayout()
        build_grid.setContentsMargins(0, 0, 0, 0)
        build_grid.setHorizontalSpacing(12)
        build_grid.setVerticalSpacing(12)
        build_grid.addWidget(self._build_item_section_card(detail.starting_items, "#7cc7ff"), 0, 0)
        build_grid.addWidget(self._build_item_section_card(detail.core_build, "#ffbf69"), 0, 1)
        build_grid.addWidget(self._build_item_options_card("Item 4", detail.item_four, "#9ed07b"), 1, 0)
        build_grid.addWidget(self._build_item_options_card("Item 5", detail.item_five, "#e08dd3"), 1, 1)
        build_grid.addWidget(self._build_item_options_card("Item 6", detail.item_six, "#78d0c8"), 2, 0, 1, 2)
        self.builds_detail_layout.addLayout(build_grid)

        matchups_row = QHBoxLayout()
        matchups_row.setContentsMargins(0, 0, 0, 0)
        matchups_row.setSpacing(12)
        matchups_row.addWidget(self._build_matchups_card("Mejores Matchups", detail.best_matchups, "#7fd79a"))
        matchups_row.addWidget(self._build_matchups_card("Peores Matchups", detail.worst_matchups, "#ff8ea1"))
        self.builds_detail_layout.addLayout(matchups_row)
        self.builds_detail_layout.addStretch(1)

    def _build_item_section_card(self, section: LolalyticsBuildSection | None, accent: str) -> QWidget:
        if section is None:
            return BuildAssetCard("Build", [], accent=accent)
        footer = ""
        if section.win_rate is not None or section.games is not None:
            footer = f"{self._format_percent(section.win_rate)} · {self._format_count(section.games)}"
        return BuildAssetCard(
            section.title,
            section.items,
            footer=footer,
            accent=accent,
            icon_size=BUILDS_ITEM_ICON_SIZE,
            show_sequence=len(section.items) > 1 and section.title.casefold() != "inicio",
        )

    def _build_item_options_card(
        self,
        title: str,
        options: list[LolalyticsBuildSection],
        accent: str,
    ) -> QWidget:
        lines = [
            f"{option.items[0]} · {self._format_percent(option.win_rate)} · {self._format_count(option.games)}"
            for option in options
            if option.items
        ]
        return BuildItemOptionsCard(title, options, accent)

    def _build_matchups_card(
        self,
        title: str,
        matchups: list[LolalyticsMatchup],
        accent: str,
    ) -> QFrame:
        frame = QFrame()
        frame.setObjectName("BuildPanelCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("BuildPanelTitle")
        title_label.setStyleSheet(f"color: {accent};")
        layout.addWidget(title_label)

        if not matchups:
            empty = QLabel("Sin datos de matchup.")
            empty.setObjectName("BuildMatchupMeta")
            layout.addWidget(empty)
        else:
            for matchup in matchups:
                layout.addWidget(BuildMatchupRow(matchup, accent))
        layout.addStretch(1)
        return frame

    @staticmethod
    def _format_percent(value: float | None) -> str:
        return f"{value:.2f}%" if value is not None else "N/D"

    @staticmethod
    def _format_count(value: int | None) -> str:
        return f"{value:,}" if value is not None else "N/D"

    @staticmethod
    def _format_lp_delta(value: int | None) -> str:
        if value is None:
            return "--"
        if value > 0:
            return f"+{value} LP"
        return f"{value} LP"

    def start_today(self) -> None:
        self._start_today(show_dialog=True, force_refresh=True)

    def _start_today(self, show_dialog: bool, force_refresh: bool = False) -> bool:
        if "today" in self.worker_threads:
            return False

        api_key = self.config.api_key.strip()
        platform = self.config.default_platform
        players = self._configured_players()
        self._refresh_today_overview()
        if not players:
            self.today_status_label.setText("No hay jugadores configurados para calcular Hoy.")
            self._refresh_group_room(full_render=True)
            return False

        self.config.api_key = api_key
        self.config.default_platform = platform
        save_config(self.config)

        self.today_button.setEnabled(False)
        self.today_status_label.setText("Calculando balance del día..." if force_refresh else "Cargando Hoy...")
        if hasattr(self, "today_stack"):
            self.today_stack.setCurrentIndex(0)
        self._start_worker(
            "today",
            TodayLpWorker(api_key, platform, players, force_refresh=force_refresh),
            self._on_today_success,
            lambda message: self._handle_today_failed(message, show_dialog),
            self.today_status_label,
        )
        return True

    def start_ranking(self) -> None:
        self._start_ranking(show_dialog=True, force_refresh=True)

    def _start_ranking(self, show_dialog: bool, force_refresh: bool = False) -> bool:
        if "ranking" in self.worker_threads:
            return False

        api_key = self.config.api_key.strip()
        platform = self.config.default_platform
        players = self._configured_players()
        self._refresh_ranking_overview()
        if not players:
            self.ranking_status_label.setText("No hay jugadores configurados para el ranking.")
            self.players_status_label.setText("No hay jugadores configurados para construir la galería.")
            self._refresh_group_room(full_render=True)
            return False

        self.config.api_key = api_key
        self.config.default_platform = platform
        save_config(self.config)

        self.ranking_button.setEnabled(False)
        self.players_refresh_button.setEnabled(False)
        self.ranking_status_label.setText("Actualizando ranking..." if force_refresh else "Iniciando ranking...")
        self._refresh_ranking_overview()
        self.players_status_label.setText("Actualizando galería..." if force_refresh else "Preparando galería...")
        self._start_worker(
            "ranking",
            RankingWorker(api_key, platform, players, force_refresh=force_refresh),
            self._on_ranking_success,
            lambda message: self._handle_ranking_failed(message, show_dialog),
            self.ranking_status_label,
        )
        return True

    def start_live_games(self) -> None:
        self._start_live_games(show_dialog=True, switch_tab=True)

    def _start_live_games(self, show_dialog: bool, switch_tab: bool = True) -> bool:
        if "live_games" in self.worker_threads:
            return False

        api_key = self.config.api_key.strip()
        platform = self.config.default_platform
        players = self._configured_players()
        if not players:
            self.live_games_status_label.setText("No hay jugadores configurados para consultar partidas.")
            self._refresh_group_room(full_render=True)
            return False

        self.config.api_key = api_key
        self.config.default_platform = platform
        save_config(self.config)

        self.live_games_button.setEnabled(False)
        self.live_games_status_label.setText("Iniciando consulta de partidas...")
        if switch_tab:
            self.tabs.setCurrentIndex(LIVE_GAMES_TAB_INDEX)
        self._start_worker(
            "live_games",
            LiveGameWorker(api_key, platform, players),
            self._on_live_games_success,
            lambda message: self._handle_live_games_failed(message, show_dialog),
            self.live_games_status_label,
        )
        return True

    def _start_worker(
        self,
        task_key: str,
        worker: QObject,
        success_slot: object,
        failed_slot: object,
        progress_label: QLabel,
    ) -> None:
        thread = QThread(self)
        self.worker_threads[task_key] = thread
        self.workers[task_key] = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(
            lambda message, key=task_key, label=progress_label: self._handle_worker_progress(key, label, message)
        )
        worker.finished.connect(success_slot)
        worker.failed.connect(failed_slot)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda key=task_key: self._clear_worker_refs(key))
        thread.start()

    def _clear_worker_refs(self, task_key: str) -> None:
        self.worker_threads.pop(task_key, None)
        self.workers.pop(task_key, None)

    def _handle_worker_progress(self, task_key: str, progress_label: QLabel, message: str) -> None:
        progress_label.setText(message)
        if self.loader_overlay.isVisible():
            self.loader_message_label.setText(message)

    def _on_today_success(self, summaries: list[TodayLpSummary]) -> None:
        self.today_button.setEnabled(True)
        self.today_summaries = sorted(
            summaries,
            key=lambda summary: (
                summary.lp_change if summary.lp_change is not None else -10_000,
                self._ranking_score(summary.player),
            ),
            reverse=True,
        )
        if self.today_summaries:
            fresh_rankings = [summary.player for summary in self.today_summaries]
            if fresh_rankings:
                self.ranking_summaries = sorted(fresh_rankings, key=self._ranking_score, reverse=True)
                self.players_data_version += 1
                self.players_render_signature = None
        self.today_last_column_count = 0
        self.today_last_card_width = 0
        self._refresh_today_overview()
        self._refresh_ranking_overview()
        self._refresh_players_overview()
        self._render_ranking()
        self._render_today()
        if self.tabs.currentIndex() == PLAYERS_TAB_INDEX:
            QTimer.singleShot(0, self._render_players)
        timestamp = datetime.now().astimezone().strftime("%H:%M")
        resolved = sum(1 for summary in self.today_summaries if summary.lp_change is not None)
        self.today_status_label.setText(
            f"Hoy actualizado. {resolved}/{len(self.today_summaries)} jugadores con referencia hasta las {timestamp}."
        )
        self._refresh_group_room(full_render=True)

    def _on_today_failed(self, message: str) -> None:
        self._handle_today_failed(message, show_dialog=True)

    def _handle_today_failed(self, message: str, show_dialog: bool) -> None:
        self.today_button.setEnabled(True)
        self.today_status_label.setText(message)
        if hasattr(self, "today_stack"):
            self.today_stack.setCurrentIndex(1)
        self._refresh_today_overview()
        self._refresh_group_room(full_render=True)
        if show_dialog:
            QMessageBox.critical(self, "Error", message)

    def _on_ranking_success(self, summaries: list[PlayerSummary]) -> None:
        self.ranking_button.setEnabled(True)
        self.players_refresh_button.setEnabled(True)
        self.ranking_status_label.setText("Ranking actualizado.")
        self.ranking_summaries = sorted(summaries, key=self._ranking_score, reverse=True)
        self._refresh_ranking_overview()
        self._refresh_players_overview()
        self.players_data_version += 1
        self.players_render_signature = None
        with _ASSET_CACHE_LOCK:
            _PLAYER_SHOWCASE_DATA_CACHE.clear()
        mastery_ready = sum(1 for summary in self.ranking_summaries if summary.top_mastery_champion_id > 0)
        if mastery_ready == len(self.ranking_summaries) and self.ranking_summaries:
            self.players_status_label.setText(f"Galería actualizada. {mastery_ready} loading screens listas.")
        elif mastery_ready > 0:
            self.players_status_label.setText(
                f"Galería actualizada. {mastery_ready}/{len(self.ranking_summaries)} jugadores con maestria detectada."
            )
        else:
            self.players_status_label.setText(
                "Galería actualizada, pero falta Riot API o datos de maestria para cargar las loading screens."
            )
        if self.today_summaries and "today" not in self.worker_threads:
            self.today_status_label.setText("Ranking actualizado. Pulsa para recalcular Hoy.")
        self._render_ranking()
        self._refresh_group_room(full_render=True)
        if self.tabs.currentIndex() == PLAYERS_TAB_INDEX:
            QTimer.singleShot(0, self._render_players)
        self._mark_initial_task_complete("ranking")

    def _on_ranking_failed(self, message: str) -> None:
        self._handle_ranking_failed(message, show_dialog=True)

    def _handle_ranking_failed(self, message: str, show_dialog: bool) -> None:
        self.ranking_button.setEnabled(True)
        self.players_refresh_button.setEnabled(True)
        self.ranking_status_label.setText(message)
        self.players_status_label.setText(message)
        if self.today_summaries:
            self.today_status_label.setText("Hoy mantiene el último cálculo disponible.")
        self._refresh_ranking_overview()
        self._refresh_players_overview()
        self._refresh_group_room(full_render=True)
        self._mark_initial_task_complete("ranking")
        if show_dialog:
            QMessageBox.critical(self, "Error", message)

    def _on_live_games_success(self, summaries: list[LiveGameParticipantSummary]) -> None:
        self.live_games_button.setEnabled(True)
        in_game_count = sum(1 for summary in summaries if summary.in_game)
        in_game_summaries = [summary for summary in summaries if summary.in_game]
        unverifiable_count = sum(
            1
            for summary in summaries
            if not summary.in_game and summary.status_text not in {"Fuera de partida", ""}
        )
        if unverifiable_count == len(summaries) and summaries:
            self.live_games_status_label.setText(
                "No se ha podido confirmar el estado en vivo de ningún jugador con las fuentes disponibles."
            )
        else:
            self.live_games_status_label.setText(
                f"Consulta completada. {in_game_count} de {len(summaries)} jugadores estan en partida."
            )
        self.live_game_summaries = sorted(
            in_game_summaries,
            key=lambda summary: (summary.game_name.lower(), summary.tag_line.lower()),
        )
        self._refresh_live_games_overview(summaries)
        self._render_live_games()
        self._refresh_group_room(full_render=True)
        self._mark_initial_task_complete("live_games")

    def _on_live_games_failed(self, message: str) -> None:
        self._handle_live_games_failed(message, show_dialog=True)

    def _handle_live_games_failed(self, message: str, show_dialog: bool) -> None:
        self.live_games_button.setEnabled(True)
        self.live_games_status_label.setText(message)
        self._refresh_group_room(full_render=True)
        self._mark_initial_task_complete("live_games")
        if show_dialog:
            QMessageBox.critical(self, "Error", message)

    def _render_today(self) -> None:
        if not hasattr(self, "today_grid"):
            return

        self._clear_layout(self.today_grid)
        if not self.today_summaries:
            empty = QLabel("Actualiza Hoy para ver el balance diario del grupo.")
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            self.today_grid.addWidget(empty, 0, 0)
            self.today_last_column_count = 1
            self.today_last_card_width = 0
            if hasattr(self, "today_stack"):
                self.today_stack.setCurrentIndex(1)
            return

        columns, card_width = self._today_layout_metrics()
        self.today_last_column_count = columns
        self.today_last_card_width = card_width

        for index, summary in enumerate(self.today_summaries):
            row = index // columns
            column = index % columns
            card = TodayLpOverlayCard(summary, card_width=card_width)
            self.today_grid.addWidget(card, row, column, Qt.AlignTop | Qt.AlignHCenter)

        for column in range(columns):
            self.today_grid.setColumnStretch(column, 1)
            self.today_grid.setColumnMinimumWidth(column, card_width)

        if hasattr(self, "today_stack"):
            self.today_stack.setCurrentIndex(1)

    def _today_layout_metrics(self) -> tuple[int, int]:
        viewport = self.today_area.viewport().width() if hasattr(self, "today_area") else 0
        gap = self.today_grid.horizontalSpacing() if hasattr(self, "today_grid") else 18
        available_width = max(viewport - 6, TODAY_CARD_MIN_WIDTH)
        player_count = max(1, len(self.today_summaries))
        max_fit_columns = max(1, (available_width + gap) // (TODAY_CARD_MIN_WIDTH + gap))
        max_columns = min(3, player_count, max_fit_columns)
        columns = 1
        for candidate in range(max_columns, 0, -1):
            width = (available_width - (gap * (candidate - 1))) // candidate
            if width >= TODAY_CARD_MIN_WIDTH:
                columns = candidate
                break
        card_width = max(
            TODAY_CARD_MIN_WIDTH,
            (available_width - (gap * (columns - 1))) // columns,
        )
        return columns, card_width

    def _render_ranking(self) -> None:
        self._clear_layout(self.ranking_layout)
        if not self.ranking_summaries:
            empty = QLabel("No hay jugadores para mostrar.")
            empty.setObjectName("Muted")
            self.ranking_layout.addWidget(empty)
            self.ranking_layout.addStretch(1)
            return

        total = len(self.ranking_summaries)
        for index, summary in enumerate(self.ranking_summaries, start=1):
            row = RankingRow(index, summary)
            self.ranking_layout.addWidget(row)
            if index < total:
                self.ranking_layout.addWidget(RankingConnector())
        self.ranking_layout.addStretch(1)

    def _render_players(self) -> None:
        if not hasattr(self, "players_grid"):
            return

        if not self.ranking_summaries:
            self._clear_layout(self.players_grid)
            empty = QLabel(
                "No hay jugadores para mostrar. Actualiza el ranking para construir la galería visual."
            )
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            self.players_grid.addWidget(empty, 0, 0)
            if hasattr(self, "players_stack"):
                self.players_stack.setCurrentIndex(1)
            self.players_rendering = False
            self.players_render_queue = []
            self.players_render_index = 0
            self.players_render_signature = None
            self.players_last_column_count = 1
            self.players_last_card_width = 0
            return

        columns, card_width = self._players_layout_metrics()
        signature = (self.players_data_version, columns, card_width)
        if self.players_rendering and self.players_render_signature == signature:
            self._show_players_loading(
                f"Cargando galería de jugadores... {self.players_render_index}/{len(self.players_render_queue)}"
            )
            return
        if self.players_render_signature == signature:
            if hasattr(self, "players_stack"):
                self.players_stack.setCurrentIndex(1)
            return

        self._clear_layout(self.players_grid)
        self.players_render_signature = signature
        self.players_last_column_count = columns
        self.players_last_card_width = card_width
        self.players_render_generation += 1
        self.players_render_queue = list(self.ranking_summaries)
        self.players_render_index = 0
        self.players_render_columns = columns
        self.players_render_card_width = card_width
        self.players_rendering = True
        self._show_players_loading(f"Cargando galería de jugadores... 0/{len(self.players_render_queue)}")
        QTimer.singleShot(0, lambda generation=self.players_render_generation: self._continue_players_render(generation))

    def _continue_players_render(self, generation: int) -> None:
        if generation != self.players_render_generation or not self.players_rendering:
            return

        total = len(self.players_render_queue)
        batch_size = 2 if total > 6 else 3
        end_index = min(self.players_render_index + batch_size, total)

        for index in range(self.players_render_index, end_index):
            summary = self.players_render_queue[index]
            row = index // self.players_render_columns
            column = index % self.players_render_columns
            card = PlayerShowcaseCard(summary, card_width=self.players_render_card_width)
            self.players_grid.addWidget(card, row, column, Qt.AlignTop | Qt.AlignHCenter)

        for column in range(self.players_render_columns):
            self.players_grid.setColumnStretch(column, 1)
            self.players_grid.setColumnMinimumWidth(column, self.players_render_card_width)

        self.players_render_index = end_index
        if end_index < total:
            self._show_players_loading(f"Cargando galería de jugadores... {end_index}/{total}")
            QTimer.singleShot(0, lambda generation=generation: self._continue_players_render(generation))
            return

        self.players_rendering = False
        if hasattr(self, "players_stack"):
            self.players_stack.setCurrentIndex(1)

    def _show_players_loading(self, message: str) -> None:
        del message
        if hasattr(self, "players_stack"):
            self.players_stack.setCurrentIndex(0)

    def _players_layout_metrics(self) -> tuple[int, int]:
        viewport = self.players_area.viewport().width() if hasattr(self, "players_area") else 0
        gap = self.players_grid.horizontalSpacing() if hasattr(self, "players_grid") else 18
        available_width = max(viewport - 6, PLAYER_CARD_MIN_WIDTH)
        player_count = max(1, len(self.ranking_summaries))
        max_fit_columns = max(1, (available_width + gap) // (PLAYER_CARD_MIN_WIDTH + gap))
        max_columns = min(5, player_count, max_fit_columns)
        columns = 1
        for candidate in range(max_columns, 0, -1):
            width = (available_width - (gap * (candidate - 1))) // candidate
            if width >= PLAYER_CARD_MIN_WIDTH:
                columns = candidate
                break
        card_width = max(
            PLAYER_CARD_MIN_WIDTH,
            (available_width - (gap * (columns - 1))) // columns,
        )
        return columns, card_width

    def _render_live_games(self) -> None:
        self._clear_layout(self.live_games_layout)
        if not self.live_game_summaries:
            empty = QLabel("No hay ningún jugador configurado jugando ahora mismo.")
            empty.setObjectName("Muted")
            empty.setWordWrap(True)
            self.live_games_layout.addWidget(empty)
            self.live_games_layout.addStretch(1)
            return

        for summary in self.live_game_summaries:
            self.live_games_layout.addWidget(LiveGameRow(summary))
        self.live_games_layout.addStretch(1)

    def _resolve_lol_game_path(self) -> Path | None:
        candidates: list[Path] = []
        configured = self.config.lol_game_path.strip()
        if configured:
            candidates.append(Path(configured))
        candidates.extend(
            [
                Path(r"C:\Riot Games\League of Legends\Game\League of Legends.exe"),
                Path(r"C:\Program Files\Riot Games\League of Legends\Game\League of Legends.exe"),
            ]
        )
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    def _build_spectate_bat(self, game_exe: Path, spectator: SpectatorSession) -> Path:
        temp_dir = Path(tempfile.gettempdir())
        bat_path = temp_dir / f"lolscout_spectate_{spectator.game_id}.bat"
        command = (
            f'"{game_exe}" "8394" "LoLLauncher.exe" "" '
            f'"spectator {spectator.observer_host} {spectator.encryption_key} {spectator.game_id} {spectator.platform_id}"'
        )
        bat_path.write_text(f"@echo off\r\nstart \"\" {command}\r\n", encoding="utf-8")
        return bat_path

    def _spectate_live_game(self, summary: LiveGameParticipantSummary) -> None:
        if summary.spectator is None:
            QMessageBox.warning(self, "Espectear no disponible", "No hay datos de espectador para esta partida.")
            return

        game_exe = self._resolve_lol_game_path()
        if game_exe is None:
            QMessageBox.warning(
                self,
                "Ruta no configurada",
                "Configura la ruta de League of Legends en Configuración para poder espectear.",
            )
            return

        try:
            bat_path = self._build_spectate_bat(game_exe, summary.spectator)
            os.startfile(str(bat_path))
        except OSError as exc:
            QMessageBox.critical(self, "Error al espectear", f"No se pudo lanzar el espectador: {exc}")

    @staticmethod
    def _ranking_score(summary: PlayerSummary) -> int:
        if summary.soloq is None or not summary.soloq.tier:
            return -1
        return (
            RANK_TIER_SCORE.get(summary.soloq.tier.upper(), -1)
            + RANK_DIVISION_SCORE.get(summary.soloq.rank, 0)
            + summary.soloq.league_points
        )

    def _start_initial_load(self) -> None:
        if self.initial_load_started:
            return
        self.initial_load_started = True
        self.initial_loader_timed_out = False
        players = self._configured_players()
        self.initial_load_pending = {"ranking"} if players else set()
        if self.initial_load_pending:
            self.loader_message_label.setText("Preparando ranking...")
            self._update_loader_geometry()
            self.loader_overlay.show()
            self.loader_overlay.raise_()
            self.loader_hide_timer.start(self.INITIAL_LOADER_FAILSAFE_MS)
        if not self._start_ranking(show_dialog=False, force_refresh=False):
            self.initial_load_pending.clear()
            self.loader_hide_timer.stop()
            self.loader_overlay.hide()
            QTimer.singleShot(250, self._preload_builds_index_if_idle)

    def _handle_initial_loader_timeout(self) -> None:
        if not self.initial_load_pending:
            return
        self.initial_loader_timed_out = True
        self.loader_overlay.hide()
        if self.ranking_summaries:
            self.ranking_status_label.setText("Mostrando cache. La carga completa ha excedido 20 s y sigue en segundo plano.")
        else:
            self.ranking_status_label.setText("La carga inicial ha excedido 20 s y sigue en segundo plano.")

    def _mark_initial_task_complete(self, task_key: str) -> None:
        if task_key not in self.initial_load_pending:
            return

        self.initial_load_pending.remove(task_key)
        if self.initial_load_pending:
            remaining = " y ".join(sorted(self.initial_load_pending))
            self.loader_message_label.setText(f"Cargando {remaining}...")
            return

        self.loader_hide_timer.stop()
        self.loader_overlay.hide()
        QTimer.singleShot(250, self._preload_builds_index_if_idle)

    def _update_loader_geometry(self) -> None:
        margin = 28
        self.loader_overlay.setGeometry(
            margin,
            margin,
            max(0, self.container.width() - (margin * 2)),
            max(0, self.container.height() - (margin * 2)),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_loader_geometry()
        if hasattr(self, "today_area") and self.today_summaries:
            columns, card_width = self._today_layout_metrics()
            if columns != self.today_last_column_count or card_width != self.today_last_card_width:
                if self.tabs.currentIndex() == TODAY_TAB_INDEX:
                    self.today_resize_timer.start(90)
                else:
                    self.today_last_column_count = 0
                    self.today_last_card_width = 0
        if hasattr(self, "players_area") and self.ranking_summaries:
            columns, card_width = self._players_layout_metrics()
            if columns != self.players_last_column_count or card_width != self.players_last_card_width:
                if self.tabs.currentIndex() == PLAYERS_TAB_INDEX:
                    self.players_resize_timer.start(90)
                else:
                    self.players_render_signature = None

    def _handle_today_resize_timeout(self) -> None:
        if self.tabs.currentIndex() == TODAY_TAB_INDEX and self.today_summaries:
            self._render_today()

    def _handle_players_resize_timeout(self) -> None:
        if self.tabs.currentIndex() == PLAYERS_TAB_INDEX and self.ranking_summaries:
            self._render_players()

    @staticmethod
    def _clear_layout(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                MainWindow._clear_layout(child_layout)
