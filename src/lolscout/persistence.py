from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mmrlol_config (
    id SMALLINT PRIMARY KEY CHECK (id = 1),
    default_platform TEXT NOT NULL,
    players_json TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS mmrlol_lp_snapshots (
    id BIGSERIAL PRIMARY KEY,
    player_key TEXT NOT NULL,
    platform TEXT NOT NULL,
    game_name TEXT NOT NULL,
    tag_line TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    lp_score INTEGER NOT NULL,
    rank_text TEXT NOT NULL,
    wins INTEGER,
    losses INTEGER,
    total_games INTEGER
);
CREATE INDEX IF NOT EXISTS mmrlol_lp_snapshots_player_time
    ON mmrlol_lp_snapshots (player_key, observed_at DESC);
CREATE TABLE IF NOT EXISTS mmrlol_response_cache (
    cache_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def _player_key(platform: str, game_name: str, tag_line: str) -> str:
    return f"{platform.strip().upper()}:{game_name.strip()}#{tag_line.strip()}".casefold()


class PostgresStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._schema_ready = False
        self._schema_lock = Lock()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL requiere psycopg en el entorno web.") from exc
        return psycopg.connect(self.database_url, connect_timeout=8)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(SCHEMA_SQL)
            self._schema_ready = True

    def healthcheck(self) -> bool:
        self._ensure_schema()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)

    def load_config(self) -> dict[str, Any] | None:
        self._ensure_schema()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT default_platform, players_json FROM mmrlol_config WHERE id = 1"
                )
                row = cursor.fetchone()
        if row is None:
            return None
        try:
            players = json.loads(row[1])
        except (TypeError, json.JSONDecodeError):
            return None
        return {"default_platform": row[0], "ranking_players": players}

    def save_config(self, default_platform: str, players: list[list[str]]) -> None:
        self._ensure_schema()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO mmrlol_config (id, default_platform, players_json, updated_at)
                    VALUES (1, %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        default_platform = EXCLUDED.default_platform,
                        players_json = EXCLUDED.players_json,
                        updated_at = NOW()
                    """,
                    (default_platform, json.dumps(players, ensure_ascii=False)),
                )

    def load_snapshots(self, platform: str, game_name: str, tag_line: str) -> list[dict[str, Any]]:
        self._ensure_schema()
        key = _player_key(platform, game_name, tag_line)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT observed_at, lp_score, rank_text, wins, losses, total_games
                    FROM mmrlol_lp_snapshots
                    WHERE player_key = %s
                    ORDER BY observed_at ASC
                    LIMIT 200
                    """,
                    (key,),
                )
                rows = cursor.fetchall()
        return [
            {
                "observed_at": row[0].isoformat(),
                "lp_score": row[1],
                "rank_text": row[2],
                "wins": row[3],
                "losses": row[4],
                "total_games": row[5],
            }
            for row in rows
        ]

    def append_snapshot(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
        snapshot: dict[str, Any],
        dedup_seconds: int,
    ) -> None:
        self._ensure_schema()
        key = _player_key(platform, game_name, tag_line)
        observed_at = datetime.fromisoformat(str(snapshot["observed_at"]))
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=timezone.utc)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT observed_at, lp_score FROM mmrlol_lp_snapshots
                    WHERE player_key = %s ORDER BY observed_at DESC LIMIT 1
                    """,
                    (key,),
                )
                previous = cursor.fetchone()
                if previous is not None:
                    elapsed = abs((observed_at - previous[0]).total_seconds())
                    if int(previous[1]) == int(snapshot["lp_score"]) and elapsed < dedup_seconds:
                        return
                cursor.execute(
                    """
                    INSERT INTO mmrlol_lp_snapshots (
                        player_key, platform, game_name, tag_line, observed_at,
                        lp_score, rank_text, wins, losses, total_games
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        key,
                        platform.strip().upper(),
                        game_name.strip(),
                        tag_line.strip(),
                        observed_at,
                        int(snapshot["lp_score"]),
                        str(snapshot["rank_text"]),
                        snapshot.get("wins"),
                        snapshot.get("losses"),
                        snapshot.get("total_games"),
                    ),
                )
                cursor.execute(
                    """
                    DELETE FROM mmrlol_lp_snapshots WHERE id IN (
                        SELECT id FROM mmrlol_lp_snapshots
                        WHERE player_key = %s ORDER BY observed_at DESC OFFSET 200
                    )
                    """,
                    (key,),
                )

    def get_cached_response(self, cache_key: str) -> dict[str, Any] | None:
        self._ensure_schema()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload_json FROM mmrlol_response_cache
                    WHERE cache_key = %s AND expires_at > NOW()
                    """,
                    (cache_key,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def set_cached_response(self, cache_key: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        self._ensure_schema()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO mmrlol_response_cache (cache_key, payload_json, expires_at, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (cache_key) DO UPDATE SET
                        payload_json = EXCLUDED.payload_json,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW()
                    """,
                    (cache_key, json.dumps(payload, ensure_ascii=False), expires_at),
                )


_store: PostgresStore | None = None
_store_url = ""
_store_lock = Lock()


def get_store() -> PostgresStore | None:
    global _store, _store_url
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return None
    if _store is not None and _store_url == database_url:
        return _store
    with _store_lock:
        if _store is None or _store_url != database_url:
            _store = PostgresStore(database_url)
            _store_url = database_url
    return _store
