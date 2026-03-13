from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import json
import os
from pathlib import Path
import tempfile
import sys
import requests

from PySide6.QtCore import QUrl
from PySide6.QtCore import QObject, QPointF, QSize, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
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
from ..models import LiveGameParticipantSummary, LiveGamePlayerDetails, PlayerSummary, RankedEntry, SpectatorSession
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
RANKING_TAB_INDEX = 0
LIVE_GAMES_TAB_INDEX = 1
SETTINGS_TAB_INDEX = 2
_CHAMPION_ICON_CACHE: dict[int, QPixmap] = {}
_ROLE_ICON_CACHE: dict[str, QPixmap] = {}
_SUMMONER_SPELL_ICON_CACHE: dict[int, QPixmap] = {}
_DISCORD_AVATAR_CACHE: dict[str, QPixmap] = {}
_OPGG_ICON_CACHE: QPixmap | None = None
_DISCORD_USER_MAP: dict[str, str] | None = None
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BUNDLED_ROOT = Path(getattr(sys, "_MEIPASS", _PROJECT_ROOT))
_UI_ROOT = Path(__file__).resolve().parent
_OPGG_ICON_PATHS = (
    _UI_ROOT / "img" / "op-gg.webp",
    _PROJECT_ROOT / "src" / "lolscout" / "ui" / "img" / "op-gg.webp",
    _BUNDLED_ROOT / "src" / "lolscout" / "ui" / "img" / "op-gg.webp",
    _BUNDLED_ROOT / "ui" / "img" / "op-gg.webp",
)
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
ROLE_DISPLAY_NAMES = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLA",
    "MIDDLE": "MID",
    "BOTTOM": "ADC",
    "UTILITY": "SUPPORT",
}


class RankingWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, api_key: str, platform: str, players: list[tuple[str, str]]) -> None:
        super().__init__()
        self.api_key = api_key
        self.platform = platform
        self.players = players

    def _fetch_ranking_player(self, game_name: str, tag_line: str) -> PlayerSummary:
        client = RiotApiClient(self.api_key, timeout=12)
        try:
            return client.fetch_player_summary(
                game_name=game_name,
                tag_line=tag_line,
                platform=self.platform,
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
            max_workers = min(2, total)
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

        self.progress.emit("Procesando ranking...")
        self.finished.emit([summary for summary in summaries if summary is not None])


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

        self.progress.emit("Procesando partidas activas...")
        self.finished.emit([summary for summary in summaries if summary is not None])


class StatCard(QFrame):
    def __init__(self, label: str, value: str, accent: str = "#54d2a0") -> None:
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        value_label = QLabel(value)
        value_label.setObjectName("StatValue")
        value_label.setStyleSheet(f"color: {accent};")
        text_label = QLabel(label)
        text_label.setObjectName("StatLabel")

        layout.addWidget(value_label)
        layout.addWidget(text_label)


class LoaderSpinner(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)
        self._timer.start(80)
        self.setFixedSize(112, 112)

    def _advance(self) -> None:
        self._angle = (self._angle + 1) % 12
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(112, 112)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)

            center_x = self.width() / 2
            center_y = self.height() / 2
            orbit_radius = 34
            dot_radius = 6

            for index in range(12):
                painter.save()
                painter.translate(center_x, center_y)
                painter.rotate(index * 30)
                distance = (index - self._angle) % 12
                alpha = max(35, 255 - (distance * 18))
                color = QColor("#54d2a0")
                color.setAlpha(alpha)
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(
                    int(orbit_radius - dot_radius),
                    -dot_radius,
                    dot_radius * 2,
                    dot_radius * 2,
                )
                painter.restore()
        finally:
            painter.end()


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
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(16)

        position_label = QLabel(f"#{position}")
        position_label.setStyleSheet("font-size: 18pt; font-weight: 700; color: #ffbf69;")

        avatar_label = QLabel()
        avatar_label.setFixedSize(DISCORD_AVATAR_SIZE, DISCORD_AVATAR_SIZE)
        avatar_label.setPixmap(_load_discord_avatar(summary))
        avatar_label.setScaledContents(True)
        avatar_label.setStyleSheet(
            f"border-radius: {DISCORD_AVATAR_SIZE // 2}px; background: #17172e; border: 1px solid #2f3750;"
        )

        name_col = QVBoxLayout()
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)

        escaped_name = html.escape(summary.game_name)
        name_label = QLabel()
        if summary.opgg_url:
            name_label.setText(
                f'<a href="{html.escape(summary.opgg_url, quote=True)}" '
                f'style="text-decoration:none;">{escaped_name}</a>'
            )
            name_label.setTextFormat(Qt.RichText)
            name_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
            name_label.setOpenExternalLinks(True)
        else:
            name_label.setText(escaped_name)
        name_label.setStyleSheet("font-size: 13pt; font-weight: 700;")

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

        meta_label = QLabel(
            f"Nivel {summary.summoner_level} - {summary.platform}"
            if summary.summoner_level > 0
            else f"{summary.platform} - sin datos"
        )
        meta_label.setObjectName("Muted")
        name_col.addLayout(title_row)
        name_col.addWidget(meta_label)

        soloq_text = summary.soloq.display_rank if summary.soloq else ("No disponible" if not summary.ranked_available else "Sin rango")
        mmr_text = str(summary.estimated_mmr) if summary.estimated_mmr is not None else "N/D"
        winrate_text = f"{summary.global_winrate:.1f}%" if summary.global_winrate is not None else "N/D"
        games_total = summary.ranked_games
        if games_total is None and summary.soloq and summary.soloq.total_games > 0:
            games_total = summary.soloq.total_games
        games_text = str(games_total) if games_total is not None else "N/D"

        info_col = QHBoxLayout()
        info_col.setSpacing(12)
        info_col.addWidget(StatCard("SoloQ", soloq_text, accent="#7cc7ff"))
        info_col.addWidget(StatCard("Partidas", games_text, accent="#f58ab3"))
        info_col.addWidget(StatCard("MMR", mmr_text, accent="#ffbf69"))
        info_col.addWidget(StatCard("Winrate", winrate_text, accent="#54d2a0"))

        top_row.addWidget(position_label, 0, Qt.AlignTop)
        top_row.addWidget(avatar_label, 0, Qt.AlignTop)
        top_row.addLayout(name_col, 2)
        top_row.addLayout(info_col, 3)
        layout.addLayout(top_row)

        insights_row = self._build_insights_row(summary)
        if insights_row is not None:
            layout.addWidget(insights_row)

    def _build_insights_row(self, summary: PlayerSummary) -> QWidget | None:
        if not summary.most_played_champions:
            return None

        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(self._build_champion_insights(summary))
        return wrapper

    def _build_champion_insights(self, summary: PlayerSummary) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)

        title = QLabel("Campeones mas jugados en SoloQ")
        title.setStyleSheet("font-size: 9pt; font-weight: 700; color: #8aa0bf; text-transform: uppercase;")
        column.addWidget(title)

        chips = QHBoxLayout()
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(18)
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
        item = QWidget()
        item.setFixedWidth(126)
        item.setFixedHeight(30)
        item.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout = QHBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        icon = QLabel()
        icon.setFixedSize(26, 26)
        icon.setPixmap(
            _load_champion_icon(champion_id).scaled(26, 26, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        )
        icon.setScaledContents(True)
        icon.setStyleSheet("border-radius: 6px; background: transparent;")

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)

        name = QLabel(champion_name)
        name.setStyleSheet("font-size: 9.5pt; font-weight: 700; color: #e5edf7;")
        name.setFixedWidth(88)
        games_label = QLabel(f"{games} partidas")
        games_label.setStyleSheet("font-size: 8.5pt; color: #8aa0bf;")

        text_col.addWidget(name)
        text_col.addWidget(games_label)
        text_col.addStretch(1)

        layout.addWidget(icon, 0, Qt.AlignTop)
        layout.addLayout(text_col, 1)
        return item


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
            line_bottom_y = self.height() - 12.0

            gradient = QLinearGradient(center_x, top_y, center_x, line_bottom_y)
            gradient.setColorAt(0.0, QColor(84, 210, 160, 15))
            gradient.setColorAt(0.45, QColor(84, 210, 160, 150))
            gradient.setColorAt(1.0, QColor(124, 199, 255, 45))

            painter.setPen(QPen(gradient, 2))
            painter.drawLine(QPointF(center_x, top_y), QPointF(center_x, line_bottom_y))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#54d2a0"))
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(center_x - 6, line_bottom_y - 1),
                        QPointF(center_x + 6, line_bottom_y - 1),
                        QPointF(center_x, self.height() - 3),
                    ]
                )
            )
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
                avatar_url = _build_discord_avatar_url(user_id)
                if avatar_url:
                    try:
                        response = requests.get(avatar_url, timeout=6)
                        response.raise_for_status()
                        downloaded = QPixmap()
                        if downloaded.loadFromData(response.content):
                            pixmap = downloaded.scaled(
                                DISCORD_AVATAR_SIZE,
                                DISCORD_AVATAR_SIZE,
                                Qt.KeepAspectRatioByExpanding,
                                Qt.SmoothTransformation,
                            )
                    except requests.RequestException:
                        pass

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

        if champion_id > 0:
            try:
                response = requests.get(
                    f"https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/champion-icons/{champion_id}.png",
                    timeout=5,
                )
                response.raise_for_status()
                downloaded = QPixmap()
                if downloaded.loadFromData(response.content):
                    pixmap = downloaded.scaled(
                        CHAMPION_ICON_SIZE,
                        CHAMPION_ICON_SIZE,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
            except requests.RequestException:
                pass

        _CHAMPION_ICON_CACHE[champion_id] = pixmap
        return pixmap

def _load_role_icon(role: str) -> QPixmap:
        cached = _ROLE_ICON_CACHE.get(role)
        if cached is not None:
            return cached

        pixmap = QPixmap(ROLE_ICON_SIZE, ROLE_ICON_SIZE)
        pixmap.fill(Qt.transparent)

        url = ROLE_ICON_URLS.get(role)
        if url:
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                downloaded = QPixmap()
                if downloaded.loadFromData(response.content):
                    pixmap = downloaded.scaled(
                        ROLE_ICON_SIZE,
                        ROLE_ICON_SIZE,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
            except requests.RequestException:
                pass

        _ROLE_ICON_CACHE[role] = pixmap
        return pixmap


def _load_summoner_spell_icon(spell_id: int) -> QPixmap:
        cached = _SUMMONER_SPELL_ICON_CACHE.get(spell_id)
        if cached is not None:
            return cached

        size = DETAIL_SPELL_ICON_SIZE
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        icon_file = SUMMONER_SPELL_ICON_FILES.get(spell_id)
        if icon_file:
            try:
                version = "15.6.1"
                response = requests.get(
                    f"https://ddragon.leagueoflegends.com/cdn/{version}/img/spell/{icon_file}",
                    timeout=5,
                )
                response.raise_for_status()
                downloaded = QPixmap()
                if downloaded.loadFromData(response.content):
                    pixmap = downloaded.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            except requests.RequestException:
                pass

        _SUMMONER_SPELL_ICON_CACHE[spell_id] = pixmap
        return pixmap


class LiveGameRow(QFrame):
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

        role_label = QLabel(icon_stack)
        role_label.setGeometry(
            CHAMPION_ICON_SIZE - ROLE_ICON_SIZE,
            CHAMPION_ICON_SIZE - ROLE_ICON_SIZE,
            ROLE_ICON_SIZE,
            ROLE_ICON_SIZE,
        )
        role_label.setPixmap(_load_role_icon(summary.role))
        role_label.setScaledContents(True)
        role_label.setStyleSheet("background: transparent;")

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
        right.addWidget(
            StatCard(
                "Campeon",
                summary.champion or "N/D",
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


class LiveGamePlayerDetailRow(QFrame):
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

        subheader_parts = [participant.champion or "Campeon desconocido"]
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.worker_threads: dict[str, QThread] = {}
        self.workers: dict[str, RankingWorker | LiveGameWorker] = {}
        self.ranking_summaries: list[PlayerSummary] = []
        self.live_game_summaries: list[LiveGameParticipantSummary] = []
        self.settings_unlocked = False
        self.initial_load_started = False
        self.initial_load_pending: set[str] = set()

        self.setWindowTitle("MMR LoL")
        self.resize(1280, 900)
        self.setStyleSheet(APP_STYLESHEET)
        self.setPalette(build_palette())

        self.container = QWidget()
        self.setCentralWidget(self.container)
        root = QVBoxLayout(self.container)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(18)

        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_ranking_tab(), "Ranking")
        self.tabs.addTab(self._build_live_games_tab(), "En partida")
        self.tabs.addTab(self._build_settings_tab(), "Configuracion")
        root.addWidget(self.tabs, 1)

        self.loader_overlay = self._build_loader_overlay()
        self.loader_overlay.hide()
        QTimer.singleShot(0, self._start_initial_load)

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("HeaderCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(8)

        title = QLabel("MMR LoL")
        title.setObjectName("HeroTitle")
        subtitle = QLabel("Ranking comparativo y ficha individual para Riot ID.")
        subtitle.setObjectName("Muted")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return frame

    def _build_loader_overlay(self) -> QFrame:
        overlay = QFrame(self.container)
        overlay.setStyleSheet(
            "background: qradialgradient(cx:0.5, cy:0.42, radius:0.9, "
            "stop:0 rgba(12, 22, 40, 242), stop:1 rgba(4, 8, 16, 232));"
            "border: none;"
        )
        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(32, 32, 32, 32)
        overlay_layout.setSpacing(16)
        overlay_layout.setAlignment(Qt.AlignCenter)

        self.loader_spinner = LoaderSpinner(overlay)

        title = QLabel("Cargando datos iniciales")
        title.setStyleSheet("font-size: 22pt; font-weight: 800; letter-spacing: 0.5px;")
        title.setAlignment(Qt.AlignCenter)

        self.loader_message_label = QLabel("Preparando ranking...")
        self.loader_message_label.setObjectName("Muted")
        self.loader_message_label.setAlignment(Qt.AlignCenter)
        self.loader_message_label.setStyleSheet("font-size: 11pt; color: #a7b8d6;")

        caption = QLabel("Sincronizando datos del ranking")
        caption.setAlignment(Qt.AlignCenter)
        caption.setStyleSheet(
            "font-size: 9.5pt; text-transform: uppercase; letter-spacing: 1.8px; color: #54d2a0;"
        )

        overlay_layout.addWidget(self.loader_spinner, 0, Qt.AlignCenter)
        overlay_layout.addSpacing(10)
        overlay_layout.addWidget(title)
        overlay_layout.addWidget(self.loader_message_label)
        overlay_layout.addWidget(caption)
        overlay.raise_()
        return overlay

    def _build_ranking_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        controls = QFrame()
        controls.setObjectName("Card")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(20, 18, 20, 18)
        controls_layout.setSpacing(16)

        info = QVBoxLayout()
        title = QLabel("Ranking SoloQ")
        title.setStyleSheet("font-size: 18pt; font-weight: 700;")
        subtitle = QLabel("Clasificacion de los jugadores configurados por elo de SoloQ.")
        subtitle.setObjectName("Muted")
        info.addWidget(title)
        info.addWidget(subtitle)

        self.ranking_button = QPushButton("Actualizar ranking")
        self.ranking_button.clicked.connect(self.start_ranking)

        self.ranking_status_label = QLabel("Pulsa para cargar el ranking.")
        self.ranking_status_label.setObjectName("Muted")
        self.ranking_status_label.setWordWrap(True)

        controls_layout.addLayout(info, 1)
        controls_layout.addWidget(self.ranking_button)

        self.ranking_area = QScrollArea()
        self.ranking_area.setWidgetResizable(True)
        self.ranking_content = QWidget()
        self.ranking_layout = QVBoxLayout(self.ranking_content)
        self.ranking_layout.setContentsMargins(0, 0, 0, 0)
        self.ranking_layout.setSpacing(12)
        self.ranking_area.setWidget(self.ranking_content)

        layout.addWidget(controls)
        layout.addWidget(self.ranking_status_label)
        layout.addWidget(self.ranking_area, 1)
        return wrapper

    def _build_live_games_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        controls = QFrame()
        controls.setObjectName("Card")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(20, 18, 20, 18)
        controls_layout.setSpacing(16)

        info = QVBoxLayout()
        title = QLabel("Jugadores en partida")
        title.setStyleSheet("font-size: 18pt; font-weight: 700;")
        subtitle = QLabel("Comprueba si los jugadores por defecto estan jugando ahora mismo.")
        subtitle.setObjectName("Muted")
        info.addWidget(title)
        info.addWidget(subtitle)

        self.live_games_button = QPushButton("Actualizar partidas")
        self.live_games_button.clicked.connect(self.start_live_games)

        self.live_games_status_label = QLabel("Pulsa para buscar partidas activas.")
        self.live_games_status_label.setObjectName("Muted")
        self.live_games_status_label.setWordWrap(True)

        controls_layout.addLayout(info, 1)
        controls_layout.addWidget(self.live_games_button)

        self.live_games_area = QScrollArea()
        self.live_games_area.setWidgetResizable(True)
        self.live_games_content = QWidget()
        self.live_games_layout = QVBoxLayout(self.live_games_content)
        self.live_games_layout.setContentsMargins(0, 0, 0, 0)
        self.live_games_layout.setSpacing(12)
        self.live_games_area.setWidget(self.live_games_content)

        layout.addWidget(controls)
        layout.addWidget(self.live_games_status_label)
        layout.addWidget(self.live_games_area, 1)
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

        title = QLabel("Configuracion")
        title.setStyleSheet("font-size: 18pt; font-weight: 700;")
        subtitle = QLabel("Gestiona los jugadores por defecto y el acceso a la carga de datos.")
        subtitle.setObjectName("Muted")
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("Card")
        card.setFixedWidth(440)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        title = QLabel("Acceso restringido")
        title.setStyleSheet("font-size: 16pt; font-weight: 700;")
        detail = QLabel("Introduce usuario y contrasena para editar la configuracion.")
        detail.setObjectName("Muted")
        detail.setWordWrap(True)

        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.settings_username_input = QLineEdit()
        self.settings_username_input.setPlaceholderText("Usuario")
        self.settings_password_input = QLineEdit()
        self.settings_password_input.setPlaceholderText("Contrasena")
        self.settings_password_input.setEchoMode(QLineEdit.Password)
        self.settings_password_input.returnPressed.connect(self._attempt_settings_login)

        form.addRow("Usuario", self.settings_username_input)
        form.addRow("Contrasena", self.settings_password_input)

        login_button = QPushButton("Entrar")
        login_button.clicked.connect(self._attempt_settings_login)
        self.settings_login_status = QLabel("Solo usuarios autorizados pueden modificar esta pagina.")
        self.settings_login_status.setObjectName("Muted")
        self.settings_login_status.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(detail)
        card_layout.addLayout(form)
        card_layout.addWidget(login_button)
        card_layout.addWidget(self.settings_login_status)

        layout.addWidget(card)
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
            self.settings_password_input.clear()
        else:
            self.settings_password_input.clear()
            self.settings_editor_status.setText("Configura los jugadores que se usan por defecto.")

    def _attempt_settings_login(self) -> None:
        username = self.settings_username_input.text().strip()
        password = self.settings_password_input.text().strip()
        if username == SETTINGS_USERNAME and password == SETTINGS_PASSWORD:
            self._set_settings_unlocked(True)
            return

        self.settings_login_status.setText("Credenciales incorrectas.")
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
            QMessageBox.warning(self, "Configuracion invalida", "Debes guardar al menos un jugador.")
            return

        self.config.api_key = self.settings_api_key_input.text().strip()
        self.config.default_platform = self.settings_default_platform_combo.currentText()
        self.config.lol_game_path = self.settings_lol_game_path_input.text().strip()
        self.config.ranking_players = players
        save_config(self.config)

        self.settings_editor_status.setText(f"Configuracion guardada. {len(players)} jugadores cargados.")
        self.ranking_status_label.setText("Configuracion actualizada. Pulsa para refrescar el ranking.")
        self.live_games_status_label.setText("Configuracion actualizada. Pulsa para refrescar partidas.")

    def start_ranking(self) -> None:
        self._start_ranking(show_dialog=True)

    def _start_ranking(self, show_dialog: bool) -> bool:
        if "ranking" in self.worker_threads:
            return False

        api_key = self.config.api_key.strip()
        platform = self.config.default_platform
        players = self._configured_players()
        if not players:
            self.ranking_status_label.setText("No hay jugadores configurados para el ranking.")
            return False

        self.config.api_key = api_key
        self.config.default_platform = platform
        save_config(self.config)

        self.ranking_button.setEnabled(False)
        self.ranking_status_label.setText("Iniciando ranking...")
        self._start_worker(
            "ranking",
            RankingWorker(api_key, platform, players),
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
        worker: RankingWorker | LiveGameWorker,
        success_slot: object,
        failed_slot: object,
        progress_label: QLabel,
    ) -> None:
        thread = QThread(self)
        self.worker_threads[task_key] = thread
        self.workers[task_key] = worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(progress_label.setText)
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

    def _on_ranking_success(self, summaries: list[PlayerSummary]) -> None:
        self.ranking_button.setEnabled(True)
        self.ranking_status_label.setText("Ranking actualizado.")
        self.ranking_summaries = sorted(summaries, key=self._ranking_score, reverse=True)
        self._render_ranking()
        self._mark_initial_task_complete("ranking")

    def _on_ranking_failed(self, message: str) -> None:
        self._handle_ranking_failed(message, show_dialog=True)

    def _handle_ranking_failed(self, message: str, show_dialog: bool) -> None:
        self.ranking_button.setEnabled(True)
        self.ranking_status_label.setText(message)
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
                "No se ha podido confirmar el estado en vivo de ningun jugador con las fuentes disponibles."
            )
        else:
            self.live_games_status_label.setText(
                f"Consulta completada. {in_game_count} de {len(summaries)} jugadores estan en partida."
            )
        self.live_game_summaries = sorted(
            in_game_summaries,
            key=lambda summary: (summary.game_name.lower(), summary.tag_line.lower()),
        )
        self._render_live_games()
        self._mark_initial_task_complete("live_games")

    def _on_live_games_failed(self, message: str) -> None:
        self._handle_live_games_failed(message, show_dialog=True)

    def _handle_live_games_failed(self, message: str, show_dialog: bool) -> None:
        self.live_games_button.setEnabled(True)
        self.live_games_status_label.setText(message)
        self._mark_initial_task_complete("live_games")
        if show_dialog:
            QMessageBox.critical(self, "Error", message)

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

    def _render_live_games(self) -> None:
        self._clear_layout(self.live_games_layout)
        if not self.live_game_summaries:
            empty = QLabel("No hay ningun jugador configurado jugando ahora mismo.")
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
                "Configura la ruta de League of Legends en Configuracion para poder espectear.",
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

        pending: set[str] = set()
        if self._start_ranking(show_dialog=False):
            pending.add("ranking")

        self.initial_load_pending = pending
        if pending:
            self.loader_message_label.setText("Preparando ranking...")
            self._update_loader_geometry()
            self.loader_overlay.show()
            self.loader_overlay.raise_()

    def _mark_initial_task_complete(self, task_key: str) -> None:
        if task_key not in self.initial_load_pending:
            return

        self.initial_load_pending.remove(task_key)
        if self.initial_load_pending:
            remaining = " y ".join(sorted(self.initial_load_pending))
            self.loader_message_label.setText(f"Cargando {remaining}...")
            return

        self.loader_overlay.hide()

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

    @staticmethod
    def _clear_layout(layout: QVBoxLayout | QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                MainWindow._clear_layout(child_layout)
