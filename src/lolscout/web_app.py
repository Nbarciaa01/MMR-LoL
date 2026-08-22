from __future__ import annotations

import os
import hmac
import copy
import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .app import _load_dotenv
from .config import AppConfig, VALID_PLATFORMS, load_config, save_config
from .lolalytics import LolalyticsClient, LolalyticsError
from .models import PlayerSummary, RankedEntry
from .persistence import get_store
from .riot_client import RiotApiError, RiotClient
from .scraping_client import ScrapingClient, ScrapingError


_load_dotenv()

WEB_ROOT = Path(__file__).resolve().parent / "web"
STATIC_ROOT = WEB_ROOT / "static"
ASSET_ROOT = Path(__file__).resolve().parent / "ui" / "img"

app = FastAPI(title="MMR LoL Web", version="0.2.0")

_response_cache: dict[str, tuple[float, dict]] = {}
_response_cache_lock = Lock()

allowed_hosts = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()]
if allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' https: data:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'"
    )
    if request.method == "GET" and response.status_code == 200:
        cache_ttl = {
            "/api/ranking": 90,
            "/api/today": 45,
            "/api/live": 15,
        }.get(request.url.path)
        if cache_ttl and request.query_params.get("force_refresh", "false").casefold() != "true":
            response.headers["Cache-Control"] = (
                f"public, max-age=0, s-maxage={cache_ttl}, stale-while-revalidate={cache_ttl}"
            )
    return response


class PlayerInput(BaseModel):
    game_name: str
    tag_line: str

    @field_validator("game_name", "tag_line")
    @classmethod
    def clean_riot_id_part(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or "#" in cleaned or len(cleaned) > 32:
            raise ValueError("Riot ID no valido.")
        return cleaned


class ConfigInput(BaseModel):
    default_platform: str
    players: list[PlayerInput]

    @field_validator("default_platform")
    @classmethod
    def clean_platform(cls, value: str) -> str:
        normalised = value.strip().upper()
        if normalised not in VALID_PLATFORMS:
            raise ValueError("Plataforma no valida.")
        return normalised

    @field_validator("players")
    @classmethod
    def limit_players(cls, value: list[PlayerInput]) -> list[PlayerInput]:
        if not value:
            raise ValueError("Debe haber al menos un jugador.")
        if len(value) > 25:
            raise ValueError("El limite actual es de 25 jugadores.")
        keys = {(player.game_name.casefold(), player.tag_line.casefold()) for player in value}
        if len(keys) != len(value):
            raise ValueError("Hay Riot IDs duplicados.")
        return value


_riot_instance: tuple[str, RiotClient] | None = None


def _riot_client() -> RiotClient | None:
    global _riot_instance
    api_key = os.getenv("RIOT_API_KEY", "").strip()
    if not api_key:
        return None
    if _riot_instance is None or _riot_instance[0] != api_key:
        _riot_instance = (api_key, RiotClient(api_key))
    return _riot_instance[1]


def _require_admin(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("MMRLOL_ADMIN_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="La gestion web no esta habilitada en el servidor.")
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not hmac.compare_digest(
        supplied.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Token de administracion incorrecto.")


def _platform(value: str) -> str:
    normalised = value.strip().upper()
    if normalised not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail="Plataforma no valida.")
    return normalised


def _ranked_payload(entry: RankedEntry | None) -> dict | None:
    if entry is None:
        return None
    payload = asdict(entry)
    payload.update(
        total_games=entry.total_games,
        winrate=round(entry.winrate, 1),
        display_rank=entry.display_rank,
    )
    return payload


def _player_payload(player: PlayerSummary) -> dict:
    payload = asdict(player)
    payload["soloq"] = _ranked_payload(player.soloq)
    payload["flex"] = _ranked_payload(player.flex)
    if player.profile_icon_id > 0:
        payload["profile_icon_url"] = (
            "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/"
            f"v1/profile-icons/{player.profile_icon_id}.jpg"
        )
    else:
        payload["profile_icon_url"] = None
    return payload


def _players() -> list[tuple[str, str]]:
    config = load_config()
    return [(str(player[0]), str(player[1])) for player in config.ranking_players or []]


def _cache_key(view: str, platform: str, source: str, players: list[tuple[str, str]]) -> str:
    fingerprint = hashlib.sha256(
        json.dumps(players, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return f"{view}:{platform}:{source}:{fingerprint}"


def _get_cached_response(cache_key: str, force_refresh: bool) -> dict | None:
    if force_refresh:
        return None
    store = get_store()
    if store is not None:
        return store.get_cached_response(cache_key)
    now = time.monotonic()
    with _response_cache_lock:
        cached = _response_cache.get(cache_key)
    if cached is None or cached[0] <= now:
        return None
    return copy.deepcopy(cached[1])


def _set_cached_response(cache_key: str, payload: dict, ttl_seconds: int) -> None:
    store = get_store()
    if store is not None:
        store.set_cached_response(cache_key, payload, ttl_seconds)
        return
    with _response_cache_lock:
        _response_cache[cache_key] = (time.monotonic() + ttl_seconds, copy.deepcopy(payload))


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "riot_configured": bool(os.getenv("RIOT_API_KEY", "").strip()),
        "management_enabled": bool(os.getenv("MMRLOL_ADMIN_TOKEN", "").strip()),
        "database_configured": get_store() is not None,
    }


@app.get("/api/config")
def config() -> dict:
    current = load_config()
    return {
        "default_platform": current.default_platform,
        "platforms": sorted(VALID_PLATFORMS),
        "players": [
            {"game_name": game_name, "tag_line": tag_line}
            for game_name, tag_line in _players()
        ],
        "riot_configured": bool(os.getenv("RIOT_API_KEY", "").strip()),
        "management_enabled": bool(os.getenv("MMRLOL_ADMIN_TOKEN", "").strip()),
        "database_configured": get_store() is not None,
    }


@app.put("/api/config")
def update_config(payload: ConfigInput, _: None = Depends(_require_admin)) -> dict:
    riot = _riot_client()
    canonical_players: list[list[str]] = []
    for player in payload.players:
        if riot is None:
            canonical_players.append([player.game_name, player.tag_line])
            continue
        try:
            identity = riot.resolve_identity(payload.default_platform, player.game_name, player.tag_line)
        except RiotApiError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"{player.game_name}#{player.tag_line}: {exc}",
            ) from exc
        canonical_players.append([identity.game_name, identity.tag_line])

    save_config(AppConfig(default_platform=payload.default_platform, ranking_players=canonical_players))
    return {"ok": True, "players": len(canonical_players)}


@app.get("/api/ranking")
def ranking(
    platform: str = "EUW1",
    source: Literal["auto", "riot", "scraping"] = "auto",
    force_refresh: bool = False,
) -> dict:
    platform = _platform(platform)
    players = _players()
    cache_key = _cache_key("ranking", platform, source, players)
    cached = _get_cached_response(cache_key, force_refresh)
    if cached is not None:
        return cached
    riot = _riot_client() if source in {"auto", "riot"} else None
    if source == "riot" and riot is None:
        raise HTTPException(status_code=503, detail="RIOT_API_KEY no esta configurada en el servidor.")

    scraping = ScrapingClient()
    results: list[dict] = []
    for game_name, tag_line in players:
        used_source = "riot" if riot is not None else "scraping"
        try:
            if riot is not None:
                try:
                    summary = riot.fetch_player_ranking(game_name, tag_line, platform)
                except RiotApiError:
                    if source == "riot":
                        raise
                    used_source = "scraping"
                    summary = scraping.fetch_player_ranking(
                        game_name, tag_line, platform, force_refresh=force_refresh
                    )
            else:
                summary = scraping.fetch_player_ranking(
                    game_name, tag_line, platform, force_refresh=force_refresh
                )
            results.append({"ok": True, "source": used_source, "player": _player_payload(summary)})
        except (RiotApiError, ScrapingError) as exc:
            results.append(
                {
                    "ok": False,
                    "source": used_source,
                    "riot_id": f"{game_name}#{tag_line}",
                    "error": str(exc),
                }
            )

    results.sort(
        key=lambda item: (
            item.get("player", {}).get("estimated_mmr") is not None,
            item.get("player", {}).get("estimated_mmr") or -1,
        ),
        reverse=True,
    )
    payload = {"platform": platform, "players": results}
    _set_cached_response(cache_key, payload, 90)
    return payload


@app.get("/api/today")
def today(
    platform: str = "EUW1",
    source: Literal["auto", "riot", "scraping"] = "auto",
    force_refresh: bool = False,
) -> dict:
    platform = _platform(platform)
    players = _players()
    cache_key = _cache_key("today", platform, source, players)
    cached = _get_cached_response(cache_key, force_refresh)
    if cached is not None:
        return cached
    riot = _riot_client() if source in {"auto", "riot"} else None
    if source == "riot" and riot is None:
        raise HTTPException(status_code=503, detail="RIOT_API_KEY no esta configurada en el servidor.")
    scraping = ScrapingClient()
    results: list[dict] = []
    for game_name, tag_line in players:
        used_source = "riot" if riot is not None else "scraping"
        try:
            if riot is not None:
                try:
                    summary = riot.fetch_today_summary(
                        game_name,
                        tag_line,
                        platform,
                        force_refresh=force_refresh,
                    )
                except RiotApiError:
                    if source == "riot":
                        raise
                    used_source = "scraping"
                    summary = scraping.fetch_player_today_lp(
                        game_name, tag_line, platform, force_refresh=force_refresh
                    )
            else:
                summary = scraping.fetch_player_today_lp(
                    game_name, tag_line, platform, force_refresh=force_refresh
                )
            payload = asdict(summary)
            payload["player"] = _player_payload(summary.player)
            payload["riot_id"] = summary.riot_id
            payload["change_text"] = summary.change_text
            results.append({"ok": True, "source": used_source, "summary": payload})
        except (RiotApiError, ScrapingError) as exc:
            results.append(
                {"ok": False, "source": used_source, "riot_id": f"{game_name}#{tag_line}", "error": str(exc)}
            )
    payload = {"platform": platform, "players": results}
    _set_cached_response(cache_key, payload, 45)
    return payload


@app.get("/api/live")
def live(
    platform: str = "EUW1",
    source: Literal["auto", "riot", "scraping"] = "auto",
) -> dict:
    platform = _platform(platform)
    players = _players()
    cache_key = _cache_key("live", platform, source, players)
    cached = _get_cached_response(cache_key, False)
    if cached is not None:
        return cached
    riot = _riot_client() if source in {"auto", "riot"} else None
    if source == "riot" and riot is None:
        raise HTTPException(status_code=503, detail="RIOT_API_KEY no esta configurada en el servidor.")
    scraping = ScrapingClient()
    results = []
    for game_name, tag_line in players:
        used_source = "riot" if riot is not None else "scraping"
        try:
            if riot is not None:
                try:
                    summary = riot.fetch_live_game_summary(game_name, tag_line, platform)
                except RiotApiError:
                    if source == "riot":
                        raise
                    used_source = "scraping"
                    summary = scraping.fetch_live_game_summary(game_name, tag_line, platform)
            else:
                summary = scraping.fetch_live_game_summary(game_name, tag_line, platform)
            results.append({"ok": True, "source": used_source, "summary": asdict(summary)})
        except (RiotApiError, ScrapingError) as exc:
            results.append(
                {"ok": False, "source": used_source, "riot_id": f"{game_name}#{tag_line}", "error": str(exc)}
            )
    payload = {"platform": platform, "players": results}
    _set_cached_response(cache_key, payload, 15)
    return payload


@app.get("/api/builds/champions")
def champions(force_refresh: bool = False) -> dict:
    try:
        items = LolalyticsClient().fetch_champion_index(force_refresh=force_refresh)
        return {"champions": [asdict(item) for item in items]}
    except LolalyticsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/builds/{slug}")
def build_detail(slug: str, force_refresh: bool = False) -> dict:
    safe_slug = slug.strip().casefold()
    if not safe_slug or not safe_slug.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Campeon no valido.")
    try:
        return asdict(LolalyticsClient().fetch_build_detail(safe_slug, force_refresh=force_refresh))
    except LolalyticsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


app.mount("/assets", StaticFiles(directory=ASSET_ROOT), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_ROOT / "index.html")


@app.get("/privacy", include_in_schema=False)
def privacy() -> FileResponse:
    return FileResponse(STATIC_ROOT / "privacy.html")


@app.get("/terms", include_in_schema=False)
def terms() -> FileResponse:
    return FileResponse(STATIC_ROOT / "terms.html")


@app.get("/riot.txt", include_in_schema=False, response_class=PlainTextResponse)
def riot_verification() -> str:
    verification_text = os.getenv("RIOT_VERIFICATION_TEXT", "").strip()
    if not verification_text:
        raise HTTPException(status_code=404, detail="Verificacion de Riot no configurada.")
    return verification_text
