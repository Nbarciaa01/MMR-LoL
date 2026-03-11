from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtGui import QPixmap
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig, load_config, save_config
from ..models import MatchSummary, PlayerSummary, RankedEntry
from ..riot_api import RiotApiClient, RiotApiError
from .theme import APP_STYLESHEET, build_palette


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
    ("BLEEEEEHH", "K1TTY"),
    ("LUDA png", "EUW"),
    ("StephanieBullet", "EUW"),
    ("RoZaNiAs", "EUW"),
]

VISIBLE_MATCHES_STEP = 10
CHAMPION_ICON_SIZE = 56
ROLE_ICON_SIZE = 22
_CHAMPION_ICON_CACHE: dict[int, QPixmap] = {}
_ROLE_ICON_CACHE: dict[str, QPixmap] = {}
ROLE_ICON_URLS = {
    "TOP": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-top.png",
    "JUNGLE": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-jungle.png",
    "MIDDLE": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-middle.png",
    "BOTTOM": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-bottom.png",
    "UTILITY": "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-parties/global/default/icon-position-utility.png",
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


class SearchWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, api_key: str, game_name: str, tag_line: str, platform: str) -> None:
        super().__init__()
        self.api_key = api_key
        self.game_name = game_name
        self.tag_line = tag_line
        self.platform = platform

    def run(self) -> None:
        try:
            client = RiotApiClient(self.api_key, progress_callback=self.progress.emit)
            summary = client.fetch_player_summary(
                game_name=self.game_name,
                tag_line=self.tag_line,
                platform=self.platform,
            )
        except RiotApiError as exc:
            self.failed.emit(str(exc))
            return
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Fallo inesperado: {exc}")
            return

        self.finished.emit(summary)


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
        client = RiotApiClient(self.api_key)
        try:
            return client.fetch_player_overview(
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
            max_workers = min(3, total)
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


class RankingRow(QFrame):
    clicked = Signal(str, str, str)

    def __init__(self, position: int, summary: PlayerSummary) -> None:
        super().__init__()
        self.summary = summary
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        position_label = QLabel(f"#{position}")
        position_label.setStyleSheet("font-size: 18pt; font-weight: 700; color: #ffbf69;")

        name_col = QVBoxLayout()
        name_label = QLabel(f"{summary.game_name}#{summary.tag_line}")
        name_label.setStyleSheet("font-size: 13pt; font-weight: 700;")
        meta_label = QLabel(
            f"Nivel {summary.summoner_level} - {summary.platform}"
            if summary.summoner_level > 0
            else f"{summary.platform} - sin datos"
        )
        meta_label.setObjectName("Muted")
        name_col.addWidget(name_label)
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

        layout.addWidget(position_label, 0, Qt.AlignTop)
        layout.addLayout(name_col, 2)
        layout.addLayout(info_col, 3)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.summary.game_name, self.summary.tag_line, self.summary.platform)
        super().mousePressEvent(event)


class MatchCard(QFrame):
    def __init__(self, match: MatchSummary) -> None:
        super().__init__()
        self.setObjectName("MatchWin" if match.won else "MatchLoss")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(16)

        icon_stack = QWidget()
        icon_stack.setFixedSize(CHAMPION_ICON_SIZE, CHAMPION_ICON_SIZE)

        icon_label = QLabel(icon_stack)
        icon_label.setGeometry(0, 0, CHAMPION_ICON_SIZE, CHAMPION_ICON_SIZE)
        icon_label.setPixmap(self._load_champion_icon(match.champion_id))
        icon_label.setScaledContents(True)
        icon_label.setStyleSheet("background: transparent;")

        role_label = QLabel(icon_stack)
        role_label.setGeometry(
            CHAMPION_ICON_SIZE - ROLE_ICON_SIZE,
            CHAMPION_ICON_SIZE - ROLE_ICON_SIZE,
            ROLE_ICON_SIZE,
            ROLE_ICON_SIZE,
        )
        role_label.setPixmap(self._load_role_icon(match.role))
        role_label.setScaledContents(True)
        role_label.setStyleSheet("background: transparent;")

        left = QVBoxLayout()
        champ = QLabel(match.champion)
        champ.setObjectName("Muted")
        champ.setStyleSheet("font-size: 9pt; background: transparent;")
        queue = QLabel(f"{match.queue_name} - {match.duration_min} min")
        queue.setStyleSheet("font-size: 15pt; font-weight: 700; background: transparent;")
        result = QLabel("Victoria" if match.won else "Derrota")
        result.setStyleSheet(
            "font-weight: 700; color: #54d2a0; background: transparent;"
            if match.won
            else "font-weight: 700; color: #ff7d9b; background: transparent;"
        )
        left.addWidget(champ)
        left.addWidget(queue)
        left.addWidget(result)

        middle = QVBoxLayout()
        kda = QLabel(f"{match.kills}/{match.deaths}/{match.assists} - KDA {match.kda}")
        kda.setStyleSheet("font-weight: 600; background: transparent;")
        farm = QLabel(f"CS {match.cs} - Oro {match.gold}")
        farm.setObjectName("Muted")
        farm.setStyleSheet("background: transparent;")
        dmg = QLabel(f"Dano {match.damage}")
        dmg.setObjectName("Muted")
        dmg.setStyleSheet("background: transparent;")
        middle.addWidget(kda)
        middle.addWidget(farm)
        middle.addWidget(dmg)

        layout.addWidget(icon_stack, 0, Qt.AlignTop)
        layout.addLayout(left, 2)
        layout.addLayout(middle, 2)

    @staticmethod
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

    @staticmethod
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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.worker_thread: QThread | None = None
        self.worker: SearchWorker | RankingWorker | None = None
        self.current_summary: PlayerSummary | None = None
        self.visible_matches = 0
        self.ranking_summaries: list[PlayerSummary] = []

        self.setWindowTitle("LoL Scout")
        self.resize(1280, 900)
        self.setStyleSheet(APP_STYLESHEET)
        self.setPalette(build_palette())

        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(18)

        root.addWidget(self._build_header())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_ranking_tab(), "Ranking")
        self.tabs.addTab(self._build_detail_tab(), "Jugador")
        root.addWidget(self.tabs, 1)

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("HeaderCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(8)

        title = QLabel("LoL Scout")
        title.setObjectName("HeroTitle")
        subtitle = QLabel("Ranking comparativo y ficha individual para Riot ID.")
        subtitle.setObjectName("Muted")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        return frame

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

    def _build_detail_tab(self) -> QWidget:
        wrapper = QWidget()
        content = QHBoxLayout(wrapper)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(18)

        content.addWidget(self._build_sidebar(), 0)
        content.addWidget(self._build_results_panel(), 1)
        return wrapper

    def _build_sidebar(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Card")
        frame.setFixedWidth(350)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)

        self.game_name_input = QLineEdit()
        self.game_name_input.setPlaceholderText("Nombre del jugador")

        self.tag_line_input = QLineEdit()
        self.tag_line_input.setPlaceholderText("EUW / TAG")

        self.platform_combo = QComboBox()
        self.platform_combo.addItems(PLATFORMS)
        self.platform_combo.setCurrentText(self.config.default_platform)

        form.addRow("Riot ID", self.game_name_input)
        form.addRow("Tag", self.tag_line_input)
        form.addRow("Plataforma", self.platform_combo)

        layout.addLayout(form)

        self.search_button = QPushButton("Buscar jugador")
        self.search_button.clicked.connect(self.start_search)

        self.status_label = QLabel("Introduce un Riot ID para consultar el perfil.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("Muted")

        tips = QLabel(
            "Notas:\n"
            "- Riot no expone el MMR real.\n"
            "- El MMR mostrado es una estimacion.\n"
            "- Se cargan las 20 partidas mas recientes y se muestran por bloques de 10.\n"
            "- Las API Keys de desarrollo caducan."
        )
        tips.setObjectName("Muted")
        tips.setWordWrap(True)

        layout.addWidget(self.search_button)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        layout.addWidget(tips)
        return frame

    def _build_results_panel(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        self.profile_frame = QFrame()
        self.profile_frame.setObjectName("Card")
        profile_layout = QVBoxLayout(self.profile_frame)
        profile_layout.setContentsMargins(20, 20, 20, 20)
        profile_layout.setSpacing(10)

        self.player_name_label = QLabel("Sin resultados")
        self.player_name_label.setStyleSheet("font-size: 20pt; font-weight: 700;")
        self.player_meta_label = QLabel("Busca un invocador para ver sus estadisticas.")
        self.player_meta_label.setObjectName("Muted")

        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(14)

        profile_layout.addWidget(self.player_name_label)
        profile_layout.addWidget(self.player_meta_label)
        profile_layout.addLayout(self.stats_row)

        self.matches_area = QScrollArea()
        self.matches_area.setWidgetResizable(True)
        self.matches_content = QWidget()
        self.matches_layout = QVBoxLayout(self.matches_content)
        self.matches_layout.setContentsMargins(0, 0, 0, 0)
        self.matches_layout.setSpacing(12)
        self.matches_area.setWidget(self.matches_content)

        layout.addWidget(self.profile_frame)
        layout.addWidget(self.matches_area, 1)
        return wrapper

    def start_ranking(self) -> None:
        api_key = self.config.api_key.strip()
        platform = self.config.default_platform
        if not api_key:
            QMessageBox.warning(self, "Configuracion incompleta", "No hay una API Key configurada.")
            return

        self.config = AppConfig(api_key=api_key, default_platform=platform)
        save_config(self.config)
        self.platform_combo.setCurrentText(platform)

        self.ranking_button.setEnabled(False)
        self.ranking_status_label.setText("Iniciando ranking...")
        self._start_worker(
            RankingWorker(api_key, platform, RANKING_PLAYERS),
            self._on_ranking_success,
            self._on_ranking_failed,
            self.ranking_status_label,
        )

    def start_search(self) -> None:
        api_key = self.config.api_key.strip()
        game_name = self.game_name_input.text().strip()
        tag_line = self.tag_line_input.text().strip()
        platform = self.platform_combo.currentText()

        if not game_name or not tag_line:
            QMessageBox.warning(self, "Datos incompletos", "Rellena nombre y tag.")
            return

        if not api_key:
            QMessageBox.warning(self, "Configuracion incompleta", "No hay una API Key configurada.")
            return

        self.config = AppConfig(api_key=api_key, default_platform=platform)
        save_config(self.config)

        self.current_summary = None
        self.visible_matches = 0
        self.search_button.setEnabled(False)
        self.status_label.setText("Iniciando consulta...")
        self.tabs.setCurrentIndex(1)

        self._start_worker(
            SearchWorker(api_key, game_name, tag_line, platform),
            self.on_search_success,
            self.on_search_failed,
            self.status_label,
        )

    def _start_worker(
        self,
        worker: SearchWorker | RankingWorker,
        success_slot: object,
        failed_slot: object,
        progress_label: QLabel,
    ) -> None:
        self.worker_thread = QThread(self)
        self.worker = worker
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(progress_label.setText)
        self.worker.finished.connect(success_slot)
        self.worker.failed.connect(failed_slot)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(self._clear_worker_refs)
        self.worker_thread.start()

    def _clear_worker_refs(self) -> None:
        self.worker_thread = None
        self.worker = None

    def _on_ranking_success(self, summaries: list[PlayerSummary]) -> None:
        self.ranking_button.setEnabled(True)
        self.ranking_status_label.setText("Ranking actualizado.")
        self.ranking_summaries = sorted(summaries, key=self._ranking_score, reverse=True)
        self._render_ranking()

    def _on_ranking_failed(self, message: str) -> None:
        self.ranking_button.setEnabled(True)
        self.ranking_status_label.setText(message)
        QMessageBox.critical(self, "Error", message)

    def _render_ranking(self) -> None:
        self._clear_layout(self.ranking_layout)
        if not self.ranking_summaries:
            empty = QLabel("No hay jugadores para mostrar.")
            empty.setObjectName("Muted")
            self.ranking_layout.addWidget(empty)
            self.ranking_layout.addStretch(1)
            return

        for index, summary in enumerate(self.ranking_summaries, start=1):
            row = RankingRow(index, summary)
            row.clicked.connect(self._open_player_from_ranking)
            self.ranking_layout.addWidget(row)
        self.ranking_layout.addStretch(1)

    @staticmethod
    def _ranking_score(summary: PlayerSummary) -> int:
        if summary.soloq is None or not summary.soloq.tier:
            return -1
        return (
            RANK_TIER_SCORE.get(summary.soloq.tier.upper(), -1)
            + RANK_DIVISION_SCORE.get(summary.soloq.rank, 0)
            + summary.soloq.league_points
        )

    def on_search_success(self, summary: PlayerSummary) -> None:
        self.search_button.setEnabled(True)
        self.status_label.setText("Consulta completada.")
        self.render_summary(summary)

    def on_search_failed(self, message: str) -> None:
        self.search_button.setEnabled(True)
        self.status_label.setText(message)
        QMessageBox.critical(self, "Error", message)

    def _open_player_from_ranking(self, game_name: str, tag_line: str, platform: str) -> None:
        self.game_name_input.setText(game_name)
        self.tag_line_input.setText(tag_line)
        self.platform_combo.setCurrentText(platform)
        self.tabs.setCurrentIndex(1)
        self.start_search()

    def render_summary(self, summary: PlayerSummary) -> None:
        self.current_summary = summary
        self.visible_matches = 0

        self.player_name_label.setText(f"{summary.game_name}#{summary.tag_line}")
        if not summary.ranked_available:
            soloq = "SoloQ no disponible"
        else:
            soloq = summary.soloq.display_rank if summary.soloq else "Sin rango en SoloQ"
        self.player_meta_label.setText(
            f"Nivel {summary.summoner_level} - {summary.platform} - {soloq}"
        )

        self._clear_layout(self.stats_row)
        self.stats_row.addWidget(
            StatCard(
                "Winrate global",
                f"{summary.global_winrate:.1f}%" if summary.global_winrate is not None else "N/D",
            )
        )
        self.stats_row.addWidget(
            StatCard(
                "Elo SoloQ",
                summary.soloq.display_rank if summary.soloq else ("No disponible" if not summary.ranked_available else "Unranked"),
                accent="#7cc7ff",
            )
        )
        self.stats_row.addWidget(
            StatCard(
                "MMR estimado",
                str(summary.estimated_mmr) if summary.estimated_mmr is not None else ("No disponible" if not summary.ranked_available else "N/D"),
                accent="#ffbf69",
            )
        )
        self.stats_row.addWidget(
            StatCard("Partidas cargadas", str(len(summary.matches)), accent="#f58ab3")
        )

        self._clear_layout(self.matches_layout)
        if not summary.matches:
            empty = QLabel("No hay partidas para mostrar.")
            empty.setObjectName("Muted")
            self.matches_layout.addWidget(empty)
            self.matches_layout.addStretch(1)
            return

        self._append_more_matches()

    def _append_more_matches(self) -> None:
        if self.current_summary is None:
            return

        matches = self.current_summary.matches
        next_visible = min(len(matches), self.visible_matches + VISIBLE_MATCHES_STEP)
        for match in matches[self.visible_matches:next_visible]:
            self.matches_layout.addWidget(MatchCard(match))
        self.visible_matches = next_visible

        if self.visible_matches < len(matches):
            remaining = len(matches) - self.visible_matches
            button = QPushButton(f"Ver mas ({remaining} restantes)")
            button.clicked.connect(self._load_more_matches)
            self.matches_layout.addWidget(button)

        self.matches_layout.addStretch(1)

    def _load_more_matches(self) -> None:
        self._remove_trailing_stretch()

        count = self.matches_layout.count()
        if count > 0:
            last_item = self.matches_layout.takeAt(count - 1)
            if last_item is not None:
                widget = last_item.widget()
                if widget is not None:
                    widget.deleteLater()

        self._append_more_matches()

    def _remove_trailing_stretch(self) -> None:
        count = self.matches_layout.count()
        if count == 0:
            return

        last_item = self.matches_layout.itemAt(count - 1)
        if last_item is not None and last_item.spacerItem() is not None:
            self.matches_layout.takeAt(count - 1)

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
