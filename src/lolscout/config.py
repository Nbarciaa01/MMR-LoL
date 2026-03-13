from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "LoLScout"
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_API_KEY = ""
LEGACY_DEFAULT_API_KEYS = {
    "RGAPI-b63d0dae-bd02-4309-90bb-c8277ea0fbee",
    "RGAPI-1908837d-a64c-4245-b6c9-41df41bccebe",
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
DEFAULT_PLAYER_SET = {(game_name.casefold(), tag_line.casefold()) for game_name, tag_line in DEFAULT_PLAYERS}


@dataclass
class AppConfig:
    api_key: str = DEFAULT_API_KEY
    default_platform: str = "EUW1"
    lol_game_path: str = ""
    ranking_players: list[list[str]] | list[tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        if not self.api_key or self.api_key in LEGACY_DEFAULT_API_KEYS:
            self.api_key = DEFAULT_API_KEY

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

        for game_name, tag_line in DEFAULT_PLAYERS:
            lookup_key = (game_name.casefold(), tag_line.casefold())
            if lookup_key in DEFAULT_PLAYER_SET and lookup_key not in seen_players:
                sanitized.append([game_name, tag_line])
                seen_players.add(lookup_key)

        self.ranking_players = sanitized or [list(player) for player in DEFAULT_PLAYERS]


def load_config() -> AppConfig:
    if not CONFIG_PATH.exists():
        return AppConfig()

    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()

    return AppConfig(
        api_key=data.get("api_key", DEFAULT_API_KEY),
        default_platform=data.get("default_platform", "EUW1"),
        lol_game_path=data.get("lol_game_path", ""),
        ranking_players=data.get("ranking_players"),
    )


def save_config(config: AppConfig) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(asdict(config), indent=2),
        encoding="utf-8",
    )
