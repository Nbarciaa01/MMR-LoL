from __future__ import annotations

import json
import os
from pathlib import Path

from lolscout.config import DEFAULT_PLAYERS
from lolscout.persistence import get_store
from lolscout.scraping_client import ScrapingClient, TODAY_LP_SNAPSHOT_DEDUP_SECONDS


def main() -> None:
    store = get_store()
    if store is None:
        raise SystemExit("DATABASE_URL no esta configurada.")

    platform = os.getenv("MMRLOL_PLATFORM", "EUW1").strip().upper()
    source_dir = Path(
        os.getenv("MMRLOL_SNAPSHOT_SOURCE")
        or Path(os.getenv("APPDATA", Path.home())) / "LoLScout" / "cache"
    )
    client = ScrapingClient()
    imported = 0

    for game_name, tag_line in DEFAULT_PLAYERS:
        filename = client._daily_lp_cache_path(platform, game_name, tag_line).name
        path = source_dir / filename
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        snapshots = payload.get("snapshots", [])
        if not isinstance(snapshots, list):
            continue
        for snapshot in snapshots[-200:]:
            if not isinstance(snapshot, dict):
                continue
            try:
                store.append_snapshot(
                    platform,
                    game_name,
                    tag_line,
                    snapshot,
                    TODAY_LP_SNAPSHOT_DEDUP_SECONDS,
                )
            except (KeyError, TypeError, ValueError):
                continue
            imported += 1

    print(f"Importadas {imported} referencias de LP desde {source_dir}.")


if __name__ == "__main__":
    main()
