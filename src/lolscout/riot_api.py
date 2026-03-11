from __future__ import annotations

from dataclasses import dataclass
import html
import re
from typing import Callable
from urllib.parse import quote

import requests

from .models import MatchSummary, PlayerSummary, RankedEntry


class RiotApiError(Exception):
    pass


PLATFORM_TO_REGION = {
    "BR1": "americas",
    "EUN1": "europe",
    "EUW1": "europe",
    "JP1": "asia",
    "KR": "asia",
    "LA1": "americas",
    "LA2": "americas",
    "ME1": "europe",
    "NA1": "americas",
    "OC1": "sea",
    "PH2": "sea",
    "RU": "europe",
    "SG2": "sea",
    "TH2": "sea",
    "TR1": "europe",
    "TW2": "sea",
    "VN2": "sea",
}

QUEUE_NAMES = {
    400: "Normal Draft",
    420: "Ranked Solo/Duo",
    430: "Normal Blind",
    440: "Ranked Flex",
    450: "ARAM",
    700: "Clash",
    900: "URF",
    1700: "Arena",
}

MATCH_PAGE_SIZE = 20
MAX_RECENT_MATCHES = 20
PLATFORM_TO_OPGG_REGION = {
    "BR1": "br",
    "EUN1": "eune",
    "EUW1": "euw",
    "KR": "kr",
    "LA1": "lan",
    "LA2": "las",
    "ME1": "me",
    "NA1": "na",
    "OC1": "oce",
    "RU": "ru",
    "TR1": "tr",
}
PLATFORM_TO_UGG_REGION = {
    "BR1": "br1",
    "EUN1": "eun1",
    "EUW1": "euw1",
    "KR": "kr",
    "LA1": "la1",
    "LA2": "la2",
    "ME1": "me1",
    "NA1": "na1",
    "OC1": "oc1",
    "RU": "ru",
    "TR1": "tr1",
}
TIER_ALIASES = {
    "iron": "IRON",
    "bronze": "BRONZE",
    "silver": "SILVER",
    "gold": "GOLD",
    "platinum": "PLATINUM",
    "emerald": "EMERALD",
    "diamond": "DIAMOND",
    "master": "MASTER",
    "grandmaster": "GRANDMASTER",
    "challenger": "CHALLENGER",
}
DIVISION_ALIASES = {
    "1": "I",
    "2": "II",
    "3": "III",
    "4": "IV",
    "I": "I",
    "II": "II",
    "III": "III",
    "IV": "IV",
}
ROLE_ALIASES = {
    "TOP": "TOP",
    "JUNGLE": "JUNGLE",
    "MIDDLE": "MIDDLE",
    "MID": "MIDDLE",
    "BOTTOM": "BOTTOM",
    "BOT": "BOTTOM",
    "UTILITY": "UTILITY",
    "SUPPORT": "UTILITY",
}


@dataclass
class RiotApiClient:
    api_key: str
    timeout: int = 20
    progress_callback: Callable[[str], None] | None = None

    def _emit_progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _raise_api_error(self, message: str, response: requests.Response) -> None:
        detail = ""
        try:
            payload = response.json()
            if isinstance(payload, dict):
                status = payload.get("status")
                if isinstance(status, dict):
                    detail = status.get("message", "")
                else:
                    detail = payload.get("message", "")
        except ValueError:
            detail = response.text.strip()

        if detail:
            raise RiotApiError(f"{message} Detalle: {detail}")
        raise RiotApiError(message)

    def _headers(self) -> dict[str, str]:
        return {"X-Riot-Token": self.api_key.strip()}

    def _get(self, url: str, context: str, **params: object) -> dict | list:
        try:
            response = requests.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RiotApiError(f"{context}: no se pudo conectar con Riot: {exc}") from exc

        if response.status_code == 401:
            self._raise_api_error(f"{context}: API Key invalida o caducada.", response)
        if response.status_code == 403:
            self._raise_api_error(f"{context}: acceso denegado por Riot API.", response)
        if response.status_code == 404:
            self._raise_api_error(f"{context}: jugador no encontrado.", response)
        if response.status_code == 429:
            self._raise_api_error(
                f"{context}: limite de peticiones alcanzado. Intentalo de nuevo en unos segundos.",
                response,
            )
        if response.status_code >= 400:
            self._raise_api_error(f"{context}: error Riot API ({response.status_code}).", response)

        return response.json()

    def _get_text(self, url: str, context: str, headers: dict[str, str] | None = None) -> str:
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RiotApiError(f"{context}: no se pudo conectar: {exc}") from exc

        if response.status_code >= 400:
            self._raise_api_error(f"{context}: error HTTP ({response.status_code}).", response)
        return response.text

    def _parse_opgg_rank_block(self, text: str, label: str, queue_type: str) -> dict | None:
        normalized_text = " ".join(text.split())
        primary_pattern = re.compile(
            rf"{re.escape(label)}\s+(?:(unranked)|([a-z]+)\s+([1-4]|IV|III|II|I)\s+(\d+)\s+LP)"
            rf"(?:\s+(\d+)\s*W\s+(\d+)\s*L)?",
            re.IGNORECASE,
        )
        match = primary_pattern.search(normalized_text)

        section = ""
        label_match = re.search(re.escape(label), normalized_text, re.IGNORECASE)
        if label_match:
            section = normalized_text[label_match.start():label_match.start() + 1200]

        if match and match.group(1):
            return None
        if not match and section and re.search(r"\bunranked\b", section, re.IGNORECASE):
            return None

        if match:
            tier_raw = match.group(2)
            rank_raw = match.group(3)
            lp_raw = match.group(4)
            wins_raw = match.group(5)
            losses_raw = match.group(6)
        else:
            rank_match = re.search(
                r"\b([a-z]+)\s+([1-4]|IV|III|II|I)\s+(\d+)\s+LP\b",
                section,
                re.IGNORECASE,
            )
            if not rank_match:
                return None
            tier_raw = rank_match.group(1)
            rank_raw = rank_match.group(2)
            lp_raw = rank_match.group(3)
            wins_losses_match = re.search(r"\b(\d+)\s*W\s+(\d+)\s*L\b", section, re.IGNORECASE)
            wins_raw = wins_losses_match.group(1) if wins_losses_match else None
            losses_raw = wins_losses_match.group(2) if wins_losses_match else None

        tier = TIER_ALIASES.get(tier_raw.lower())
        rank = DIVISION_ALIASES.get(rank_raw.upper(), rank_raw.upper())
        if not tier:
            return None

        winrate_source = section or normalized_text
        lp_anchor = re.search(r"\b\d+\s+LP\b", winrate_source, re.IGNORECASE)
        if lp_anchor:
            winrate_source = winrate_source[lp_anchor.end():]
        winrate_match = re.search(r"\b(\d+(?:\.\d+)?)\s*%\b", winrate_source)

        return {
            "queueType": queue_type,
            "tier": tier,
            "rank": rank,
            "leaguePoints": int(lp_raw),
            "wins": int(wins_raw or 0),
            "losses": int(losses_raw or 0),
            "winrate": float(winrate_match.group(1)) if winrate_match else None,
        }

    @staticmethod
    def _extract_total_games(section: str) -> int | None:
        wins_losses_match = re.search(r"\b(\d+)\s*W\s+(\d+)\s*L\b", section, re.IGNORECASE)
        if wins_losses_match:
            return int(wins_losses_match.group(1)) + int(wins_losses_match.group(2))

        for pattern in (
            r"\b(\d+)\s+(?:Played|Games?|Matches)\b",
            r"\b(?:Played|Games?|Matches)\s+(\d+)\b",
        ):
            match = re.search(pattern, section, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _normalize_role(self, participant: dict) -> str:
        raw_role = (
            participant.get("individualPosition")
            or participant.get("teamPosition")
            or participant.get("lane")
            or ""
        )
        normalized = ROLE_ALIASES.get(str(raw_role).upper(), "")
        return normalized or "UNKNOWN"

    def _load_ranked_from_opgg(self, platform: str, game_name: str, tag_line: str) -> list[dict]:
        opgg_region = PLATFORM_TO_OPGG_REGION.get(platform)
        if not opgg_region:
            return []

        slug = f"{game_name}-{tag_line}"
        url = f"https://op.gg/lol/summoners/{opgg_region}/{quote(slug)}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        page = self._get_text(url, context="Fallback OP.GG", headers=headers)

        text = html.unescape(re.sub(r"<[^>]+>", " ", page))
        soloq = self._parse_opgg_rank_block(text, "Ranked Solo/Duo", "RANKED_SOLO_5x5")
        flex = self._parse_opgg_rank_block(text, "Ranked Flex", "RANKED_FLEX_SR")

        entries: list[dict] = []
        if soloq:
            entries.append(soloq)
        if flex:
            entries.append(flex)
        return entries

    def _load_winrate_from_ugg(self, platform: str, game_name: str, tag_line: str) -> float | None:
        ugg_region = PLATFORM_TO_UGG_REGION.get(platform)
        if not ugg_region:
            return None

        slug = f"{game_name}-{tag_line}".lower()
        url = f"https://u.gg/lol/profile/{ugg_region}/{quote(slug)}/overview"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        page = self._get_text(url, context="Fallback U.GG", headers=headers)
        text = html.unescape(re.sub(r"<[^>]+>", " ", page))
        normalized_text = " ".join(text.split())

        patterns = [
            r"Ranked Solo(?:/Duo)?\s+.*?\b(\d+(?:\.\d+)?)%\s+Win Rate\b",
            r"Ranked Solo(?:/Duo)?\s+.*?\b(\d+(?:\.\d+)?)%\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized_text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def _load_games_from_opgg(self, platform: str, game_name: str, tag_line: str) -> int | None:
        for entry in self._load_ranked_from_opgg(platform, game_name, tag_line):
            queue_type = str(entry.get("queueType", "")).replace("x", "X").upper()
            if queue_type == "RANKED_SOLO_5X5" or (
                "RANKED" in queue_type and "SOLO" in queue_type and "FLEX" not in queue_type
            ):
                wins = int(entry.get("wins", 0))
                losses = int(entry.get("losses", 0))
                total_games = wins + losses
                if total_games > 0:
                    return total_games
        return None

    def _load_games_from_ugg(self, platform: str, game_name: str, tag_line: str) -> int | None:
        ugg_region = PLATFORM_TO_UGG_REGION.get(platform)
        if not ugg_region:
            return None

        slug = f"{game_name}-{tag_line}".lower()
        url = f"https://u.gg/lol/profile/{ugg_region}/{quote(slug)}/overview"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        page = self._get_text(url, context="Fallback U.GG", headers=headers)
        text = html.unescape(re.sub(r"<[^>]+>", " ", page))
        normalized_text = " ".join(text.split())
        patterns = (
            r"Overview Champion Stats Live Game Highlights Ranked Solo(?:/Duo)?\s+.*?(?:Ranked Flex|Your Highlights|Champion Stats|$)",
            r"Ranked Solo(?:/Duo)?\s+[A-Za-z]+\s+(?:[1-4]|IV|III|II|I)\s+\d+\s+LP.*?(?:Ranked Flex|Your Highlights|Champion Stats|$)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, normalized_text, re.IGNORECASE):
                total_games = self._extract_total_games(match.group(0))
                if total_games is not None:
                    return total_games
        return self._extract_total_games(normalized_text)

    def _load_ranked_entries(
        self,
        platform: str,
        puuid: str,
        summoner_id: str | None,
        legacy_summoner_name: str | None = None,
    ) -> tuple[list[dict], bool]:
        league_entries: list[dict] = []
        ranked_available = True

        if summoner_id:
            self._emit_progress("Consultando clasificatorias...")
            by_summoner = self._get(
                f"https://{platform.lower()}.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}",
                context="Clasificatorias",
            )
            if isinstance(by_summoner, list):
                league_entries = [entry for entry in by_summoner if isinstance(entry, dict)]

        if league_entries:
            return league_entries, ranked_available

        self._emit_progress("Consultando clasificatorias por PUUID...")
        by_puuid: dict | list | None = None
        try:
            by_puuid = self._get(
                f"https://{platform.lower()}.api.riotgames.com/lol/league-exp/v4/entries/by-puuid/{puuid}",
                context="Clasificatorias por PUUID",
            )
        except RiotApiError as exc:
            if "acceso denegado" in str(exc).lower() or "forbidden" in str(exc).lower():
                ranked_available = bool(league_entries)
            else:
                raise
        if isinstance(by_puuid, list):
            filtered = [entry for entry in by_puuid if isinstance(entry, dict)]
            return filtered, ranked_available

        if legacy_summoner_name:
            self._emit_progress("Resolviendo summonerId legacy...")
            try:
                by_name = self._get(
                    f"https://{platform.lower()}.api.riotgames.com/lol/summoner/v4/summoners/by-name/{quote(legacy_summoner_name)}",
                    context="Resolucion legacy por summonerName",
                )
                legacy_summoner_id = None
                if isinstance(by_name, dict):
                    legacy_summoner_id = by_name.get("id") or by_name.get("summonerId")
                if legacy_summoner_id:
                    by_legacy_summoner = self._get(
                        f"https://{platform.lower()}.api.riotgames.com/lol/league/v4/entries/by-summoner/{legacy_summoner_id}",
                        context="Clasificatorias legacy por summonerName",
                    )
                    if isinstance(by_legacy_summoner, list):
                        filtered = [entry for entry in by_legacy_summoner if isinstance(entry, dict)]
                        return filtered, ranked_available
            except RiotApiError:
                pass

        return [], ranked_available

    def _fallback_ranked_entries(
        self,
        platform: str,
        puuid: str,
        summoner_id: str | None,
        game_name: str,
        tag_line: str,
        legacy_summoner_name: str | None = None,
    ) -> tuple[list[dict], bool]:
        league_entries, ranked_available = self._load_ranked_entries(
            platform,
            puuid,
            summoner_id,
            legacy_summoner_name=legacy_summoner_name,
        )
        if league_entries:
            return league_entries, ranked_available

        self._emit_progress("Intentando fallback de ranked con OP.GG...")
        try:
            opgg_entries = self._load_ranked_from_opgg(platform, game_name, tag_line)
        except RiotApiError:
            return league_entries, ranked_available
        if opgg_entries:
            return opgg_entries, True

        return [], ranked_available

    def _extract_legacy_summoner_name(self, regional: str, puuid: str, match_ids: list[str]) -> str | None:
        for match_id in match_ids[:5]:
            try:
                match = self._get(
                    f"https://{regional}.api.riotgames.com/lol/match/v5/matches/{match_id}",
                    context=f"Legacy summonerName en partida {match_id}",
                )
            except RiotApiError:
                continue

            if not isinstance(match, dict):
                continue
            info = match.get("info")
            if not isinstance(info, dict):
                continue
            participants = info.get("participants")
            if not isinstance(participants, list):
                continue

            for item in participants:
                if not isinstance(item, dict):
                    continue
                if item.get("puuid") != puuid:
                    continue
                summoner_name = item.get("summonerName")
                if isinstance(summoner_name, str) and summoner_name.strip():
                    return summoner_name.strip()
        return None

    def _parse_ranked_entries(self, league_entries: list[dict]) -> tuple[RankedEntry | None, RankedEntry | None, float | None, float | None]:
        soloq = None
        flex = None
        soloq_winrate = None
        flex_winrate = None
        for entry in league_entries:
            parsed = RankedEntry(
                queue_type=entry["queueType"],
                tier=entry.get("tier", ""),
                rank=entry.get("rank", ""),
                league_points=int(entry.get("leaguePoints", 0)),
                wins=int(entry.get("wins", 0)),
                losses=int(entry.get("losses", 0)),
            )
            normalized_queue = parsed.queue_type.replace("x", "X").upper()
            if normalized_queue == "RANKED_SOLO_5X5" or (
                "RANKED" in normalized_queue and "SOLO" in normalized_queue and "FLEX" not in normalized_queue
            ):
                soloq = parsed
                if entry.get("winrate") is not None:
                    soloq_winrate = float(entry["winrate"])
            elif normalized_queue == "RANKED_FLEX_SR":
                flex = parsed
                if entry.get("winrate") is not None:
                    flex_winrate = float(entry["winrate"])
        return soloq, flex, soloq_winrate, flex_winrate

    def _build_summary(
        self,
        account: dict,
        summoner: dict,
        platform: str,
        league_entries: list[dict],
        game_name: str,
        tag_line: str,
        ranked_available: bool,
        matches: list[MatchSummary],
        recent_winrate: float,
    ) -> PlayerSummary:
        soloq, flex, soloq_winrate, flex_winrate = self._parse_ranked_entries(league_entries)
        estimated_mmr = estimate_mmr(soloq, recent_winrate)
        global_winrate = None
        ranked_games = soloq.total_games if soloq and soloq.total_games > 0 else None
        if soloq_winrate is not None:
            global_winrate = round(soloq_winrate, 1)
        elif soloq and soloq.total_games > 0:
            global_winrate = round(soloq.winrate, 1)
        elif flex_winrate is not None:
            global_winrate = round(flex_winrate, 1)
        elif flex and flex.total_games > 0:
            global_winrate = round(flex.winrate, 1)
        elif soloq is not None:
            try:
                ugg_winrate = self._load_winrate_from_ugg(platform, game_name, tag_line)
            except RiotApiError:
                ugg_winrate = None
            if ugg_winrate is not None:
                global_winrate = round(ugg_winrate, 1)
        if ranked_games is None:
            try:
                opgg_games = self._load_games_from_opgg(platform, game_name, tag_line)
            except RiotApiError:
                opgg_games = None
            if opgg_games is not None:
                ranked_games = opgg_games
            else:
                try:
                    ugg_games = self._load_games_from_ugg(platform, game_name, tag_line)
                except RiotApiError:
                    ugg_games = None
                if ugg_games is not None:
                    ranked_games = ugg_games

        return PlayerSummary(
            game_name=account.get("gameName") or game_name,
            tag_line=account.get("tagLine") or tag_line,
            summoner_level=int(summoner.get("summonerLevel", 0)),
            profile_icon_id=int(summoner.get("profileIconId", 0)),
            platform=platform,
            soloq=soloq,
            flex=flex,
            estimated_mmr=estimated_mmr,
            global_winrate=global_winrate,
            ranked_games=ranked_games,
            recent_winrate=recent_winrate,
            matches=matches,
            ranked_available=ranked_available,
        )

    def fetch_player_overview(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
    ) -> PlayerSummary:
        regional = PLATFORM_TO_REGION[platform]
        account = self._get(
            f"https://{regional}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
            f"{quote(game_name)}/{quote(tag_line)}",
            context="Cuenta",
        )

        puuid = account.get("puuid")
        if not puuid:
            raise RiotApiError("La cuenta no devolvio un PUUID valido.")

        summoner = self._get(
            f"https://{platform.lower()}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}",
            context="Perfil de invocador",
        )
        summoner_id = summoner.get("id") or summoner.get("summonerId")
        legacy_summoner_name = None
        if not summoner_id:
            match_ids = self._get(
                f"https://{regional}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids",
                context="Historial de partidas",
                start=0,
                count=5,
            )
            if isinstance(match_ids, list):
                legacy_summoner_name = self._extract_legacy_summoner_name(regional, puuid, match_ids)
        league_entries, ranked_available = self._fallback_ranked_entries(
            platform,
            puuid,
            summoner_id,
            game_name,
            tag_line,
            legacy_summoner_name=legacy_summoner_name,
        )

        # Use global winrate when available; otherwise neutral recent form for overview/MMR.
        return self._build_summary(
            account=account,
            summoner=summoner,
            platform=platform,
            league_entries=league_entries,
            game_name=game_name,
            tag_line=tag_line,
            ranked_available=ranked_available,
            matches=[],
            recent_winrate=50.0,
        )

    def fetch_player_summary(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
    ) -> PlayerSummary:
        regional = PLATFORM_TO_REGION[platform]
        self._emit_progress("Buscando cuenta de Riot...")
        account = self._get(
            f"https://{regional}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
            f"{quote(game_name)}/{quote(tag_line)}",
            context="Cuenta",
        )

        puuid = account.get("puuid")
        if not puuid:
            raise RiotApiError("La cuenta no devolvio un PUUID valido.")

        self._emit_progress("Cargando perfil del invocador...")
        summoner = self._get(
            f"https://{platform.lower()}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}",
            context="Perfil de invocador",
        )
        summoner_id = summoner.get("id") or summoner.get("summonerId")
        self._emit_progress("Cargando las 20 partidas mas recientes...")
        matches = self._get(
            f"https://{regional}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids",
            context="Historial de partidas",
            start=0,
            count=MATCH_PAGE_SIZE,
        )
        if not isinstance(matches, list):
            raise RiotApiError("Historial de partidas: respuesta invalida de Riot API.")
        matches = matches[:MAX_RECENT_MATCHES]
        legacy_summoner_name = None
        if not summoner_id:
            legacy_summoner_name = self._extract_legacy_summoner_name(regional, puuid, matches)
        league_entries, ranked_available = self._fallback_ranked_entries(
            platform,
            puuid,
            summoner_id,
            game_name,
            tag_line,
            legacy_summoner_name=legacy_summoner_name,
        )

        match_summaries = []
        wins = 0
        total_matches = len(matches)
        for index, match_id in enumerate(matches, start=1):
            self._emit_progress(f"Analizando partida {index}/{total_matches}...")
            match = self._get(
                f"https://{regional}.api.riotgames.com/lol/match/v5/matches/{match_id}",
                context=f"Detalle de partida {match_id}",
            )
            info = match["info"]
            participant = next(
                item for item in info["participants"] if item["puuid"] == puuid
            )
            won = bool(participant["win"])
            if won:
                wins += 1

            kills = int(participant["kills"])
            deaths = int(participant["deaths"])
            assists = int(participant["assists"])
            kda = round((kills + assists) / max(1, deaths), 2)

            match_summaries.append(
                MatchSummary(
                    match_id=match_id,
                    champion=participant["championName"],
                    champion_id=int(participant.get("championId", 0)),
                    role=self._normalize_role(participant),
                    queue_name=QUEUE_NAMES.get(info["queueId"], f"Queue {info['queueId']}"),
                    won=won,
                    kills=kills,
                    deaths=deaths,
                    assists=assists,
                    cs=int(participant["totalMinionsKilled"] + participant.get("neutralMinionsKilled", 0)),
                    duration_min=max(1, int(info["gameDuration"] // 60)),
                    damage=int(participant["totalDamageDealtToChampions"]),
                    gold=int(participant["goldEarned"]),
                    kda=kda,
                )
            )

        recent_winrate = round((wins / max(1, len(match_summaries))) * 100, 1)
        return self._build_summary(
            account=account,
            summoner=summoner,
            platform=platform,
            league_entries=league_entries,
            game_name=game_name,
            tag_line=tag_line,
            ranked_available=ranked_available,
            matches=match_summaries,
            recent_winrate=recent_winrate,
        )


TIER_BASE = {
    "IRON": 800,
    "BRONZE": 950,
    "SILVER": 1100,
    "GOLD": 1275,
    "PLATINUM": 1450,
    "EMERALD": 1600,
    "DIAMOND": 1800,
    "MASTER": 2050,
    "GRANDMASTER": 2200,
    "CHALLENGER": 2350,
}

RANK_OFFSET = {"IV": 0, "III": 65, "II": 130, "I": 195}


def estimate_mmr(entry: RankedEntry | None, recent_winrate: float) -> int | None:
    if not entry or not entry.tier:
        return None

    base = TIER_BASE.get(entry.tier.upper(), 1000)
    division = RANK_OFFSET.get(entry.rank, 0)
    lp_factor = int(entry.league_points * 0.8)
    form_factor = int((recent_winrate - 50) * 6)
    return base + division + lp_factor + form_factor
