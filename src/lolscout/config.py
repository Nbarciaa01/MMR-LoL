from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .persistence import get_store


APP_DIR = Path(os.getenv("MMRLOL_DATA_DIR") or os.getenv("APPDATA", Path.home())) / "LoLScout"
CONFIG_PATH = APP_DIR / "config.json"
VALID_PLATFORMS = {
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
}
DEFAULT_PLAYERS = [
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
@dataclass
class AppConfig:
    default_platform: str = "EUW1"
    ranking_players: list[list[str]] | list[tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        self.default_platform = str(self.default_platform or "EUW1").strip().upper()
        if self.default_platform not in VALID_PLATFORMS:
            self.default_platform = "EUW1"

        if self.ranking_players is None:
            self.ranking_players = [list(player) for player in DEFAULT_PLAYERS]
            return

        sanitized: list[list[str]] = []
        seen_players: set[tuple[str, str]] = set()
        for player in self.ranking_players:
            if not isinstance(player, (list, tuple)) or len(player) != 2:
                continue
            game_name = str(player[0]).strip()
            tag_line = str(player[1]).strip()
            if not game_name or not tag_line:
                continue
            lookup_key = (game_name.casefold(), tag_line.casefold())
            if lookup_key in seen_players:
                continue
            seen_players.add(lookup_key)
            sanitized.append([game_name, tag_line])

        self.ranking_players = sanitized or [list(player) for player in DEFAULT_PLAYERS]


def load_config() -> AppConfig:
    store = get_store()
    if store is not None:
        data = store.load_config()
        if data is not None:
            return AppConfig(
                default_platform=data.get("default_platform", "EUW1"),
                ranking_players=data.get("ranking_players"),
            )

    if not CONFIG_PATH.exists():
        return AppConfig()

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()

    return AppConfig(
        default_platform=data.get("default_platform", "EUW1"),
        ranking_players=data.get("ranking_players"),
    )


def save_config(config: AppConfig) -> None:
    store = get_store()
    if store is not None:
        store.save_config(config.default_platform, [list(player) for player in config.ranking_players or []])
        return

    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(asdict(config), indent=2),
        encoding="utf-8",
    )
