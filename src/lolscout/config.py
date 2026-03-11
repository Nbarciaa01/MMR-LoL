from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "LoLScout"
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_API_KEY = "RGAPI-1908837d-a64c-4245-b6c9-41df41bccebe"


@dataclass
class AppConfig:
    api_key: str = DEFAULT_API_KEY
    default_platform: str = "EUW1"


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
    )


def save_config(config: AppConfig) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(asdict(config), indent=2),
        encoding="utf-8",
    )
