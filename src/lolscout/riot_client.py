from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from urllib.parse import quote, urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import (
    LiveGameParticipantSummary,
    LiveGamePlayerDetails,
    LiveGameSummary,
    MatchSummary,
    PlayerSummary,
    RankedEntry,
    TodayLpSummary,
)
from .scraping_client import ScrapingClient, ScrapingError, estimate_mmr
from .time_utils import app_now, to_app_timezone


PLATFORM_TO_REGIONAL_ROUTE = {
    "BR1": "americas",
    "LA1": "americas",
    "LA2": "americas",
    "NA1": "americas",
    "EUN1": "europe",
    "EUW1": "europe",
    "ME1": "europe",
    "RU": "europe",
    "TR1": "europe",
    "KR": "asia",
    "OC1": "sea",
}

QUEUE_NAMES = {
    0: "Partida personalizada",
    400: "Normal Reclutamiento",
    420: "Ranked Solo/Duo",
    430: "Normal a ciegas",
    440: "Ranked Flex",
    450: "ARAM",
    490: "Partida rapida",
}

MAP_NAMES = {11: "Grieta del Invocador", 12: "Abismo de los Lamentos"}

SPELL_NAMES = {
    1: "Limpiar",
    3: "Extenuacion",
    4: "Destello",
    6: "Fantasmal",
    7: "Curar",
    11: "Aplastar",
    12: "Teleportar",
    13: "Claridad",
    14: "Prender",
    21: "Barrera",
    32: "Marca",
}


class RiotApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class RiotIdentity:
    puuid: str
    summoner_id: str
    game_name: str
    tag_line: str
    summoner_level: int
    profile_icon_id: int


@dataclass
class RiotClient:
    api_key: str
    timeout: int = 12
    session: requests.Session = field(init=False, repr=False)
    _cache: dict[str, tuple[float, object]] = field(init=False, repr=False, default_factory=dict)
    _cache_lock: Lock = field(init=False, repr=False, default_factory=Lock)

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ValueError("RIOT_API_KEY no esta configurada.")
        self.session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            status=2,
            backoff_factor=0.4,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    @staticmethod
    def regional_route(platform: str) -> str:
        normalised = platform.strip().upper()
        try:
            return PLATFORM_TO_REGIONAL_ROUTE[normalised]
        except KeyError as exc:
            raise RiotApiError(f"Plataforma Riot no soportada: {platform}") from exc

    def _get_json(
        self,
        url: str,
        *,
        ttl_seconds: int = 0,
        allow_not_found: bool = False,
    ) -> object | None:
        now = time.monotonic()
        if ttl_seconds > 0:
            with self._cache_lock:
                cached = self._cache.get(url)
            if cached and cached[0] > now:
                return copy.deepcopy(cached[1])

        try:
            response = self.session.get(
                url,
                headers={"X-Riot-Token": self.api_key, "Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RiotApiError("No se pudo conectar con Riot Games.") from exc

        if response.status_code == 401:
            raise RiotApiError("Riot rechazo la autenticacion de la API.")
        if response.status_code == 403:
            raise RiotApiError("La clave de Riot no es valida o ha caducado.")
        if response.status_code == 404 and allow_not_found:
            return None
        if response.status_code == 404:
            raise RiotApiError("No se encontro ese Riot ID en la plataforma seleccionada.")
        if response.status_code == 429:
            raise RiotApiError("Se alcanzo el limite temporal de peticiones de Riot.")
        try:
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RiotApiError(f"Riot devolvio una respuesta inesperada ({response.status_code}).") from exc

        if ttl_seconds > 0:
            with self._cache_lock:
                self._cache[url] = (now + ttl_seconds, copy.deepcopy(payload))
        return payload

    def _account_by_puuid(self, platform: str, puuid: str) -> dict | None:
        regional = self.regional_route(platform)
        url = (
            f"https://{regional}.api.riotgames.com/riot/account/v1/accounts/by-puuid/"
            f"{quote(puuid, safe='')}"
        )
        payload = self._get_json(url, ttl_seconds=6 * 60 * 60, allow_not_found=True)
        return payload if isinstance(payload, dict) else None

    def resolve_identity(self, platform: str, game_name: str, tag_line: str) -> RiotIdentity:
        platform = platform.strip().upper()
        regional = self.regional_route(platform)
        account_url = (
            f"https://{regional}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
            f"{quote(game_name.strip(), safe='')}/{quote(tag_line.strip(), safe='')}"
        )
        account = self._get_json(account_url, ttl_seconds=6 * 60 * 60)
        if not isinstance(account, dict) or not account.get("puuid"):
            raise RiotApiError("Riot no devolvio una identidad valida.")

        puuid = str(account["puuid"])
        summoner_url = (
            f"https://{platform.lower()}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/"
            f"{quote(puuid, safe='')}"
        )
        summoner = self._get_json(summoner_url, ttl_seconds=15 * 60)
        if not isinstance(summoner, dict) or not summoner.get("puuid"):
            raise RiotApiError("Riot no devolvio los datos de invocador.")

        return RiotIdentity(
            puuid=puuid,
            summoner_id=str(summoner.get("id") or puuid),
            game_name=str(account.get("gameName") or game_name),
            tag_line=str(account.get("tagLine") or tag_line),
            summoner_level=int(summoner.get("summonerLevel", 0) or 0),
            profile_icon_id=int(summoner.get("profileIconId", 0) or 0),
        )

    def fetch_ranked_entries(self, platform: str, puuid: str) -> list[RankedEntry]:
        platform = platform.strip().upper()
        url = (
            f"https://{platform.lower()}.api.riotgames.com/lol/league/v4/entries/by-puuid/"
            f"{quote(puuid, safe='')}"
        )
        payload = self._get_json(url, ttl_seconds=90)
        if not isinstance(payload, list):
            raise RiotApiError("Riot no devolvio una lista de clasificatorias valida.")

        entries: list[RankedEntry] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            entries.append(
                RankedEntry(
                    queue_type=str(item.get("queueType", "")),
                    tier=str(item.get("tier", "")),
                    rank=str(item.get("rank", "")),
                    league_points=int(item.get("leaguePoints", 0) or 0),
                    wins=int(item.get("wins", 0) or 0),
                    losses=int(item.get("losses", 0) or 0),
                )
            )
        return entries

    def _ranking_from_identity(self, platform: str, identity: RiotIdentity) -> PlayerSummary:
        entries = self.fetch_ranked_entries(platform, identity.puuid)
        soloq = next((entry for entry in entries if entry.queue_type == "RANKED_SOLO_5x5"), None)
        flex = next((entry for entry in entries if entry.queue_type == "RANKED_FLEX_SR"), None)
        ranked_games = soloq.total_games if soloq and soloq.total_games else None
        global_winrate = round(soloq.winrate, 1) if soloq and soloq.total_games else None
        return PlayerSummary(
            game_name=identity.game_name,
            tag_line=identity.tag_line,
            summoner_level=identity.summoner_level,
            profile_icon_id=identity.profile_icon_id,
            platform=platform,
            opgg_url=ScrapingClient.build_opgg_profile_url(platform, identity.game_name, identity.tag_line),
            soloq=soloq,
            flex=flex,
            estimated_mmr=estimate_mmr(soloq, global_winrate or 50.0),
            global_winrate=global_winrate,
            ranked_games=ranked_games,
            ranked_available=True,
        )

    def fetch_player_ranking(self, game_name: str, tag_line: str, platform: str) -> PlayerSummary:
        platform = platform.strip().upper()
        identity = self.resolve_identity(platform, game_name, tag_line)
        return self._ranking_from_identity(platform, identity)

    @staticmethod
    def _relative_time(played_at: datetime, now_local: datetime) -> str:
        seconds = max(0, int((now_local - played_at).total_seconds()))
        if seconds < 60:
            return "Ahora"
        if seconds < 3600:
            return f"Hace {seconds // 60} min"
        return f"Hace {seconds // 3600} h"

    def _match_summary(self, detail: dict, puuid: str, now_local: datetime) -> MatchSummary | None:
        metadata = detail.get("metadata")
        info = detail.get("info")
        if not isinstance(metadata, dict) or not isinstance(info, dict):
            return None
        if int(info.get("queueId", 0) or 0) != 420:
            return None
        participants = info.get("participants")
        if not isinstance(participants, list):
            return None
        participant = next(
            (item for item in participants if isinstance(item, dict) and item.get("puuid") == puuid),
            None,
        )
        if participant is None:
            return None

        duration_seconds = int(info.get("gameDuration", 0) or 0)
        timestamp_ms = int(
            info.get("gameEndTimestamp", 0)
            or info.get("gameStartTimestamp", 0)
            or info.get("gameCreation", 0)
            or 0
        )
        played_at = to_app_timezone(datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc))
        kills = int(participant.get("kills", 0) or 0)
        deaths = int(participant.get("deaths", 0) or 0)
        assists = int(participant.get("assists", 0) or 0)
        champion_id = int(participant.get("championId", 0) or 0)
        return MatchSummary(
            match_id=str(metadata.get("matchId", "")),
            champion=str(participant.get("championName") or f"Champion {champion_id}"),
            champion_id=champion_id,
            role=str(participant.get("teamPosition") or participant.get("individualPosition") or "UNKNOWN"),
            queue_name="Ranked Solo/Duo",
            won=bool(participant.get("win", False)),
            kills=kills,
            deaths=deaths,
            assists=assists,
            cs=int(participant.get("totalMinionsKilled", 0) or 0)
            + int(participant.get("neutralMinionsKilled", 0) or 0),
            duration_min=max(1, duration_seconds // 60),
            damage=int(participant.get("totalDamageDealtToChampions", 0) or 0),
            gold=int(participant.get("goldEarned", 0) or 0),
            kda=round((kills + assists) / max(1, deaths), 2),
            played_at_iso=played_at.isoformat(),
            played_at_text=self._relative_time(played_at, now_local),
        )

    def fetch_today_matches(
        self,
        platform: str,
        puuid: str,
        *,
        now_local: datetime | None = None,
    ) -> list[MatchSummary]:
        platform = platform.strip().upper()
        regional = self.regional_route(platform)
        now_local = now_local or app_now()
        start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        query = urlencode(
            {
                "startTime": int(start_of_day.astimezone(timezone.utc).timestamp()),
                "queue": 420,
                "start": 0,
                "count": 20,
            }
        )
        list_url = (
            f"https://{regional}.api.riotgames.com/lol/match/v5/matches/by-puuid/"
            f"{quote(puuid, safe='')}/ids?{query}"
        )
        match_ids = self._get_json(list_url, ttl_seconds=60)
        if not isinstance(match_ids, list):
            raise RiotApiError("Riot no devolvio un historial de partidas valido.")

        matches: list[MatchSummary] = []
        for raw_match_id in match_ids:
            match_id = str(raw_match_id or "").strip()
            if not match_id:
                continue
            detail_url = (
                f"https://{regional}.api.riotgames.com/lol/match/v5/matches/"
                f"{quote(match_id, safe='')}"
            )
            detail = self._get_json(detail_url, ttl_seconds=24 * 60 * 60)
            if not isinstance(detail, dict):
                continue
            summary = self._match_summary(detail, puuid, now_local)
            if summary is None:
                continue
            played_at = to_app_timezone(datetime.fromisoformat(summary.played_at_iso or ""))
            if played_at >= start_of_day:
                matches.append(summary)
        matches.sort(key=lambda match: match.played_at_iso or "", reverse=True)
        return matches

    def fetch_today_summary(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
        *,
        force_refresh: bool = False,
    ) -> TodayLpSummary:
        platform = platform.strip().upper()
        identity = self.resolve_identity(platform, game_name, tag_line)
        player = self._ranking_from_identity(platform, identity)
        matches = self.fetch_today_matches(platform, identity.puuid)
        rank_text = player.soloq.display_rank if player.soloq else "Sin SoloQ"
        tracker = ScrapingClient()
        current_score = tracker._lp_score_from_ranked_entry(player.soloq)
        if current_score is None:
            return TodayLpSummary(
                player=player,
                current_rank_text=rank_text,
                baseline_note="Sin datos de SoloQ para hoy.",
                today_matches=matches[:5],
            )

        now_local = app_now()
        start_of_day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        candidates = tracker._load_daily_lp_snapshot_candidates(platform, game_name, tag_line)
        if identity.game_name.casefold() != game_name.casefold() or identity.tag_line.casefold() != tag_line.casefold():
            candidates.extend(
                tracker._load_daily_lp_snapshot_candidates(platform, identity.game_name, identity.tag_line)
            )

        current_total_games = player.soloq.total_games if player.soloq is not None else None
        expected_baseline_total = (
            max(0, current_total_games - len(matches))
            if current_total_games is not None and matches
            else None
        )
        has_game_baseline = expected_baseline_total is not None and any(
            candidate.total_games == expected_baseline_total for candidate in candidates
        )
        if matches and not has_game_baseline:
            try:
                opgg_page = tracker._load_opgg_profile_page(
                    platform,
                    identity.game_name,
                    identity.tag_line,
                    force_refresh=force_refresh,
                )
            except ScrapingError:
                opgg_page = None
            if opgg_page:
                candidates.extend(tracker._build_today_candidates_from_opgg_page(opgg_page))

        first_match_at = None
        for match in matches:
            if not match.played_at_iso:
                continue
            try:
                played_at = to_app_timezone(datetime.fromisoformat(match.played_at_iso))
            except ValueError:
                continue
            if first_match_at is None or played_at < first_match_at:
                first_match_at = played_at

        baseline = tracker._select_today_baseline_candidate(
            candidates,
            start_of_day,
            now_local,
            first_match_at=first_match_at,
            current_total_games=current_total_games,
            today_match_count=len(matches),
            current_lp_score=current_score,
        )
        tracker._append_daily_lp_snapshot(player, cache_game_name=game_name, cache_tag_line=tag_line)
        if baseline is None:
            return TodayLpSummary(
                player=player,
                lp_change=0 if not matches else None,
                current_lp_score=current_score,
                baseline_lp_score=current_score if not matches else None,
                current_rank_text=rank_text,
                baseline_rank_text=rank_text if not matches else "",
                baseline_local_time=now_local.strftime("%d %b %H:%M") if not matches else None,
                baseline_source="Referencia actual" if not matches else "",
                baseline_note=(
                    "Sin partidas detectadas hoy; se toma el LP actual como base."
                    if not matches
                    else "Primera consulta del dia: el balance estara disponible desde el siguiente cambio de LP."
                ),
                today_matches=matches[:5],
            )

        return TodayLpSummary(
            player=player,
            lp_change=current_score - baseline.score,
            current_lp_score=current_score,
            baseline_lp_score=baseline.score,
            current_rank_text=rank_text,
            baseline_rank_text=baseline.rank_text,
            baseline_local_time=baseline.observed_at.strftime("%d %b %H:%M"),
            baseline_source="Riot API + snapshot local",
            baseline_note=f"Referencia guardada {baseline.observed_at.strftime('%d %b %H:%M')}",
            today_matches=matches[:5],
        )

    def fetch_live_game_summary(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
    ) -> LiveGameParticipantSummary:
        platform = platform.strip().upper()
        identity = self.resolve_identity(platform, game_name, tag_line)
        url = (
            f"https://{platform.lower()}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/"
            f"{quote(identity.puuid, safe='')}"
        )
        active_game = self._get_json(url, ttl_seconds=20, allow_not_found=True)
        if active_game is None:
            return LiveGameParticipantSummary(
                game_name=identity.game_name,
                tag_line=identity.tag_line,
                platform=platform,
                in_game=False,
                status_text="Fuera de partida",
            )
        if not isinstance(active_game, dict):
            raise RiotApiError("Riot no devolvio una partida activa valida.")

        raw_participants = active_game.get("participants")
        if not isinstance(raw_participants, list):
            raw_participants = []
        participants: list[LiveGamePlayerDetails] = []
        tracked_participant: dict | None = None
        for item in raw_participants:
            if not isinstance(item, dict):
                continue
            participant_puuid = str(item.get("puuid", "") or "")
            if participant_puuid == identity.puuid:
                tracked_participant = item
            account = self._account_by_puuid(platform, participant_puuid) if participant_puuid else None
            spell_ids = [int(item.get("spell1Id", 0) or 0), int(item.get("spell2Id", 0) or 0)]
            participants.append(
                LiveGamePlayerDetails(
                    game_name=str((account or {}).get("gameName") or "Jugador"),
                    tag_line=str((account or {}).get("tagLine") or ""),
                    team_color="Azul" if int(item.get("teamId", 0) or 0) == 100 else "Rojo",
                    champion=f"Champion {int(item.get('championId', 0) or 0)}",
                    champion_id=int(item.get("championId", 0) or 0),
                    spell_ids=spell_ids,
                    spell_names=[SPELL_NAMES.get(spell_id, str(spell_id)) for spell_id in spell_ids],
                )
            )

        queue_id = int(active_game.get("gameQueueConfigId", 0) or 0)
        map_id = int(active_game.get("mapId", 0) or 0)
        game = LiveGameSummary(
            queue_name=QUEUE_NAMES.get(queue_id, f"Cola {queue_id}"),
            game_mode=str(active_game.get("gameMode", "")),
            map_name=MAP_NAMES.get(map_id, f"Mapa {map_id}"),
            duration_min=max(0, int(active_game.get("gameLength", 0) or 0) // 60),
            team_size=sum(1 for item in raw_participants if isinstance(item, dict) and item.get("teamId") == 100),
            enemy_team_size=sum(1 for item in raw_participants if isinstance(item, dict) and item.get("teamId") == 200),
        )
        champion_id = int((tracked_participant or {}).get("championId", 0) or 0)
        return LiveGameParticipantSummary(
            game_name=identity.game_name,
            tag_line=identity.tag_line,
            platform=platform,
            in_game=True,
            champion=f"Champion {champion_id}",
            champion_id=champion_id,
            game=game,
            status_text=f"En partida · {game.queue_name}",
            participants=participants,
        )
