from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import html
import json
import re
import time
from typing import Callable
import unicodedata
from urllib.parse import quote, quote_plus

import requests

from .models import (
    ChampionPlayStat,
    LiveGameParticipantSummary,
    LiveGamePlayerDetails,
    LiveGameSummary,
    MatchSummary,
    PlayerSummary,
    RankedEntry,
    RolePlayStat,
    SpectatorSession,
)


class RiotApiError(Exception):
    pass


MATCH_PAGE_SIZE = 10
MAX_RECENT_MATCHES = 10

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
PLATFORM_TO_POROFESSOR_REGION = {
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
PLATFORM_TO_LEAGUEOFGRAPHS_REGION = {
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
PLATFORM_TO_RIOT_REGION = {
    "BR1": "americas",
    "EUN1": "europe",
    "EUW1": "europe",
    "KR": "asia",
    "LA1": "americas",
    "LA2": "americas",
    "ME1": "europe",
    "NA1": "americas",
    "OC1": "sea",
    "RU": "europe",
    "TR1": "europe",
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
    "TOPLANE": "TOP",
    "TOP LANE": "TOP",
    "JUNGLE": "JUNGLE",
    "JGL": "JUNGLE",
    "JG": "JUNGLE",
    "MID": "MIDDLE",
    "MIDLANE": "MIDDLE",
    "MID LANE": "MIDDLE",
    "MIDDLE": "MIDDLE",
    "MIDDLE LANE": "MIDDLE",
    "ADC": "BOTTOM",
    "DUO": "BOTTOM",
    "DUO_CARRY": "BOTTOM",
    "CARRY": "BOTTOM",
    "BOTTOM": "BOTTOM",
    "BOTTOM LANE": "BOTTOM",
    "BOT": "BOTTOM",
    "BOTLANE": "BOTTOM",
    "BOT LANE": "BOTTOM",
    "SUPPORT": "UTILITY",
    "SUP": "UTILITY",
    "UTILITY": "UTILITY",
    "DUO_SUPPORT": "UTILITY",
    "ADCARRY": "BOTTOM",
    "AD CARRY": "BOTTOM",
}
LEAGUEOFGRAPHS_ROLE_SLUGS = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "middle",
    "BOTTOM": "adc",
    "UTILITY": "support",
}
SOLOQUEUE_LABELS = (
    "ranked solo",
    "ranked solo/duo",
    "solo/duo",
    "soloq",
    "solo queue",
    "soloqueue",
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


@dataclass
class ExternalProfile:
    game_name: str
    tag_line: str
    summoner_level: int = 0
    profile_icon_id: int = 0
    matches: list[MatchSummary] = field(default_factory=list)


@dataclass
class RiotApiClient:
    api_key: str
    timeout: int = 20
    progress_callback: Callable[[str], None] | None = None
    session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()

    def _emit_progress(self, message: str) -> None:
        if self.progress_callback is not None:
            self.progress_callback(message)

    def _get_text(self, url: str, context: str, headers: dict[str, str] | None = None) -> str:
        request_headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if headers:
            request_headers.update(headers)

        try:
            response = self.session.get(url, headers=request_headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RiotApiError(f"{context}: no se pudo conectar: {exc}") from exc

        if response.status_code == 404:
            raise RiotApiError(f"{context}: jugador no encontrado.")
        if response.status_code >= 400:
            raise RiotApiError(f"{context}: error HTTP ({response.status_code}).")

        return response.text

    def _riot_headers(self) -> dict[str, str]:
        token = self.api_key.strip()
        if not token:
            raise RiotApiError("Riot API: falta API Key.")
        return {"X-Riot-Token": token, "User-Agent": "Mozilla/5.0"}

    def _get_json(self, url: str, context: str) -> dict | list:
        try:
            response = self.session.get(url, headers=self._riot_headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise RiotApiError(f"{context}: no se pudo conectar con Riot: {exc}") from exc

        if response.status_code == 404:
            raise RiotApiError(f"{context}: no encontrado.")
        if response.status_code == 401:
            raise RiotApiError(f"{context}: API Key invalida o caducada.")
        if response.status_code == 403:
            raise RiotApiError(f"{context}: acceso denegado.")
        if response.status_code == 429:
            raise RiotApiError(f"{context}: limite de peticiones alcanzado.")
        if response.status_code >= 400:
            raise RiotApiError(f"{context}: error Riot API ({response.status_code}).")

        try:
            return response.json()
        except ValueError as exc:
            raise RiotApiError(f"{context}: respuesta JSON invalida.") from exc

    def _get_json_or_none_on_404(self, url: str, context: str) -> dict | list | None:
        try:
            return self._get_json(url, context)
        except RiotApiError as exc:
            if "no encontrado" in str(exc).lower():
                return None
            raise

    @staticmethod
    def _normalize_lookup_name(value: str) -> str:
        return re.sub(r"\s+", " ", value.strip()).casefold()

    @staticmethod
    def _clean_html_text(value: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    @staticmethod
    def _normalize_champion_lookup(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", html.unescape(value))
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^a-z0-9]+", "", normalized.casefold())
        return normalized

    @staticmethod
    def _normalize_role_text(value: str) -> str:
        cleaned = re.sub(r"[_\-/]+", " ", html.unescape(value)).strip().upper()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned:
            return "UNKNOWN"

        direct = ROLE_ALIASES.get(cleaned)
        if direct:
            return direct

        compact = cleaned.replace(" ", "")
        direct = ROLE_ALIASES.get(compact)
        if direct:
            return direct

        token_map = (
            ("JUNGLE", "JUNGLE"),
            ("JGL", "JUNGLE"),
            ("JG", "JUNGLE"),
            ("MIDDLE", "MIDDLE"),
            ("MID", "MIDDLE"),
            ("BOTTOM", "BOTTOM"),
            ("BOT", "BOTTOM"),
            ("ADC", "BOTTOM"),
            ("SUPPORT", "UTILITY"),
            ("SUP", "UTILITY"),
            ("UTILITY", "UTILITY"),
            ("TOP", "TOP"),
        )
        tokens = set(cleaned.split())
        for token, normalized in token_map:
            if token in tokens:
                return normalized

        return "UNKNOWN"

    def _extract_live_role_from_porofessor(self, body: str) -> str:
        strong_role_patterns = (
            r'class="role-([a-z]+)-\d+',
            r'<div class="position">\s*([^<]+)\s*</div>',
            r'<div[^>]+class="[^"]*\bposition\b[^"]*"[^>]*>\s*([^<]+)\s*</div>',
            r'(?:data-role|data-position|data-lane)="([^"]+)"',
            r'icon-position-(top|jungle|middle|bottom|utility)',
        )

        for pattern in strong_role_patterns:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                for group in match.groups():
                    if not group:
                        continue
                    normalized = self._normalize_role_text(group)
                    if normalized != "UNKNOWN":
                        return normalized

        scoped_role_patterns = (
            r'\b(?:position|role|lane)\b[^>]{0,80}>\s*([^<]*(?:top|jungle|mid|middle|bottom|bot|adc|support|utility)[^<]*)<',
        )
        for pattern in scoped_role_patterns:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                for group in match.groups():
                    if not group:
                        continue
                    normalized = self._normalize_role_text(group)
                    if normalized != "UNKNOWN":
                        return normalized

        return "UNKNOWN"

    def _load_spectator_session(self, platform: str, game_name: str, tag_line: str) -> SpectatorSession | None:
        regional_route = PLATFORM_TO_RIOT_REGION.get(platform)
        if not regional_route or not self.api_key.strip():
            return None

        account = self._get_json_or_none_on_404(
            f"https://{regional_route}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
            f"{quote(game_name)}/{quote(tag_line)}",
            context="Riot Account",
        )
        if not isinstance(account, dict):
            return None

        puuid = str(account.get("puuid", "")).strip()
        if not puuid:
            return None

        summoner = self._get_json_or_none_on_404(
            f"https://{platform.lower()}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{quote(puuid)}",
            context="Riot Summoner",
        )
        if not isinstance(summoner, dict):
            return None

        summoner_id = str(summoner.get("id", "")).strip()
        if not summoner_id:
            return None

        active_game = self._get_json_or_none_on_404(
            f"https://{platform.lower()}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{quote(summoner_id)}",
            context="Riot Spectator",
        )
        if not isinstance(active_game, dict):
            return None

        observers = active_game.get("observers")
        if not isinstance(observers, dict):
            return None

        encryption_key = str(observers.get("encryptionKey", "")).strip()
        if not encryption_key:
            return None

        try:
            game_id = int(active_game.get("gameId", 0) or 0)
        except (TypeError, ValueError):
            return None
        if game_id <= 0:
            return None

        platform_id = str(active_game.get("platformId", platform) or platform).strip() or platform
        return SpectatorSession(platform_id=platform_id, game_id=game_id, encryption_key=encryption_key)

    @staticmethod
    def _slug(game_name: str, tag_line: str) -> str:
        return quote_plus(f"{game_name}-{tag_line}")

    @staticmethod
    def _ugg_slug_candidates(game_name: str, tag_line: str) -> list[str]:
        compact_game_name = re.sub(r"\s+", "-", game_name.strip())
        compact_tag_line = re.sub(r"\s+", "-", tag_line.strip())
        return [
            quote_plus(f"{game_name}-{tag_line}").lower(),
            quote(f"{compact_game_name}-{compact_tag_line}", safe="-").lower(),
        ]

    @classmethod
    def build_opgg_profile_url(cls, platform: str, game_name: str, tag_line: str) -> str | None:
        opgg_region = PLATFORM_TO_OPGG_REGION.get(platform)
        if not opgg_region:
            return None
        return f"https://op.gg/lol/summoners/{opgg_region}/{cls._slug(game_name, tag_line)}"

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
    def _parse_opgg_action_payload(payload: str) -> dict | None:
        result: dict | None = None
        for line in payload.splitlines():
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            prefix, raw_json = stripped.split(":", 1)
            if not prefix.isdigit():
                continue
            raw_json = raw_json.strip()
            if not raw_json or raw_json.startswith("E{"):
                continue
            try:
                parsed = json.loads(raw_json)
            except ValueError:
                continue
            if isinstance(parsed, dict) and "status" in parsed:
                result = parsed
        return result

    def _post_opgg_action(
        self,
        url: str,
        action_id: str,
        params: dict[str, object],
        context: str,
    ) -> dict | None:
        try:
            response = self.session.post(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "text/x-component",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Content-Type": "text/plain;charset=UTF-8",
                    "next-action": action_id,
                    "Origin": "https://op.gg",
                    "Referer": url,
                },
                data=json.dumps([params]),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RiotApiError(f"{context}: no se pudo conectar con OP.GG.") from exc

        if response.status_code >= 400:
            raise RiotApiError(f"{context}: error HTTP ({response.status_code}).")

        return self._parse_opgg_action_payload(response.text)

    @staticmethod
    def _extract_opgg_refresh_context(page: str) -> tuple[str, str, str] | None:
        puuid_match = re.search(r'"puuid":"([^"]+)"', page)
        updated_at_match = re.search(r'"updatedAt":"([^"]+)"', page)
        renewable_at_match = re.search(r'"initRenewableAt":"([^"]+)"', page)
        if not puuid_match or not updated_at_match or not renewable_at_match:
            return None
        return puuid_match.group(1), updated_at_match.group(1), renewable_at_match.group(1)

    @staticmethod
    def _is_iso_datetime_due(value: str) -> bool:
        try:
            due_at = datetime.fromisoformat(value)
        except ValueError:
            return True
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        return due_at <= datetime.now(tz=due_at.tzinfo)

    def _refresh_opgg_profile(self, url: str, region: str, page: str) -> str:
        context = self._extract_opgg_refresh_context(page)
        if context is None:
            return page

        puuid, _, renewable_at = context
        if not self._is_iso_datetime_due(renewable_at):
            return page

        renew_data = self._post_opgg_action(
            url,
            "405a04669583947dc03eb8c7f367adf28c8f714e86",
            {"region": region, "puuid": puuid, "isPremiumPrimary": False},
            "OP.GG refresh",
        )
        if not renew_data:
            return page

        status = str(renew_data.get("status", "")).upper()
        deadline = datetime.now(timezone.utc).timestamp() + min(8, self.timeout)
        while status == "RENEWING" and datetime.now(timezone.utc).timestamp() < deadline:
            delay_ms = int(renew_data.get("delay", 1000) or 1000)
            time.sleep(max(0.25, min(delay_ms / 1000.0, 2.0)))
            renew_data = self._post_opgg_action(
                url,
                "400c02bdfd8c90756a329b312a7455e73880ad43ec",
                {"region": region, "puuid": puuid},
                "OP.GG refresh",
            )
            if not renew_data:
                break
            status = str(renew_data.get("status", "")).upper()

        if status not in {"RENEWAL_FINISH", "TOO_MANY_RENEWALS"}:
            return page
        return self._get_text(url, context="OP.GG perfil")

    def _load_ranked_from_opgg(self, platform: str, game_name: str, tag_line: str) -> list[dict]:
        opgg_region = PLATFORM_TO_OPGG_REGION.get(platform)
        if not opgg_region:
            return []

        url = f"https://op.gg/lol/summoners/{opgg_region}/{self._slug(game_name, tag_line)}"
        page = self._get_text(url, context="OP.GG perfil")
        try:
            page = self._refresh_opgg_profile(url, opgg_region, page)
        except RiotApiError:
            pass
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

        for slug in self._ugg_slug_candidates(game_name, tag_line):
            try:
                page = self._get_text(f"https://u.gg/lol/profile/{ugg_region}/{slug}/overview", context="U.GG perfil")
            except RiotApiError:
                continue

            text = html.unescape(re.sub(r"<[^>]+>", " ", page))
            normalized_text = " ".join(text.split())
            for pattern in (
                r"Ranked Solo(?:/Duo)?\s+.*?\b(\d+(?:\.\d+)?)%\s+Win Rate\b",
                r"Ranked Solo(?:/Duo)?\s+.*?\b(\d+(?:\.\d+)?)%\b",
            ):
                match = re.search(pattern, normalized_text, re.IGNORECASE)
                if match:
                    return float(match.group(1))
        return None

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

        for slug in self._ugg_slug_candidates(game_name, tag_line):
            try:
                page = self._get_text(f"https://u.gg/lol/profile/{ugg_region}/{slug}/overview", context="U.GG perfil")
            except RiotApiError:
                continue

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

            total_games = self._extract_total_games(normalized_text)
            if total_games is not None:
                return total_games
        return None

    def _load_profile_from_ugg(self, platform: str, game_name: str, tag_line: str) -> ExternalProfile | None:
        ugg_region = PLATFORM_TO_UGG_REGION.get(platform)
        if not ugg_region:
            return None

        for slug in self._ugg_slug_candidates(game_name, tag_line):
            try:
                page = self._get_text(f"https://u.gg/lol/profile/{ugg_region}/{slug}/overview", context="U.GG perfil")
            except RiotApiError:
                continue

            canonical_game_name = game_name
            canonical_tag_line = tag_line
            summoner_level = 0
            profile_icon_id = 0

            state_match = re.search(
                r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\})\s*</script>",
                page,
                re.IGNORECASE | re.DOTALL,
            )
            if state_match:
                try:
                    state = json.loads(state_match.group(1))
                except json.JSONDecodeError:
                    state = None

                if isinstance(state, dict):
                    for key, value in state.items():
                        if not isinstance(key, str) or not key.startswith("profileInitSimple("):
                            continue
                        if not isinstance(value, dict):
                            continue
                        player_info = value.get("playerInfo")
                        if not isinstance(player_info, dict):
                            continue
                        summoner_level = int(player_info.get("summonerLevel", 0) or 0)
                        profile_icon_id = int(player_info.get("iconId", 0) or 0)
                        canonical_game_name = self._clean_html_text(
                            str(player_info.get("riotUserName") or canonical_game_name)
                        )
                        canonical_tag_line = self._clean_html_text(
                            str(player_info.get("riotTagLine") or canonical_tag_line)
                        )
                        break

            if summoner_level <= 0:
                level_match = re.search(
                    r'>\s*(\d+)\s*</div>\s*<div class="relative w-full h-full.*?Summoner profile icon',
                    page,
                    re.IGNORECASE | re.DOTALL,
                )
                if level_match:
                    summoner_level = int(level_match.group(1))

            if profile_icon_id <= 0:
                icon_match = re.search(r"/profileicon/(\d+)\.png", page, re.IGNORECASE)
                if icon_match:
                    profile_icon_id = int(icon_match.group(1))

            if summoner_level > 0 or profile_icon_id > 0:
                return ExternalProfile(
                    game_name=canonical_game_name,
                    tag_line=canonical_tag_line,
                    summoner_level=summoner_level,
                    profile_icon_id=profile_icon_id,
                    matches=[],
                )
        return None

    def _load_profile_from_leagueofgraphs(self, platform: str, game_name: str, tag_line: str) -> ExternalProfile:
        region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
        if not region:
            raise RiotApiError("LeagueOfGraphs: plataforma no soportada.")

        url = f"https://www.leagueofgraphs.com/summoner/{region}/{self._slug(game_name, tag_line)}"
        page = self._get_text(url, context="LeagueOfGraphs perfil")

        title_match = re.search(r"<title>([^#<]+)#([^<(]+)\s*\(", page, re.IGNORECASE)
        canonical_game_name = self._clean_html_text(title_match.group(1)) if title_match else game_name
        canonical_tag_line = self._clean_html_text(title_match.group(2)) if title_match else tag_line

        level_match = re.search(
            r"\bbannerSubtitle\b[^>]*>\s*Level\s+(\d+)\b",
            page,
            re.IGNORECASE | re.DOTALL,
        )
        if not level_match:
            level_match = re.search(
                r">\s*Level\s+(\d+)\b",
                page,
                re.IGNORECASE,
            )
        icon_match = re.search(
            r'Summoner profile icon"\s*/?>|Summoner profile icon',
            page,
            re.IGNORECASE,
        )
        profile_icon_id = 0
        summoner_level = int(level_match.group(1)) if level_match else 0
        if icon_match:
            around_icon = page[max(0, icon_match.start() - 600):icon_match.end() + 600]
        else:
            around_icon = page
        icon_id_match = re.search(r"/profileicon/(\d+)\.png|/summonerIcons/[^/]+/\d+/(\d+)\.png", around_icon, re.IGNORECASE)
        if icon_id_match:
            profile_icon_id = int(icon_id_match.group(1) or icon_id_match.group(2) or 0)

        if summoner_level <= 0 or profile_icon_id <= 0:
            ugg_profile = self._load_profile_from_ugg(platform, canonical_game_name, canonical_tag_line)
            if ugg_profile is not None:
                if summoner_level <= 0:
                    summoner_level = ugg_profile.summoner_level
                if profile_icon_id <= 0:
                    profile_icon_id = ugg_profile.profile_icon_id
                if not title_match:
                    canonical_game_name = ugg_profile.game_name
                    canonical_tag_line = ugg_profile.tag_line

        matches = self._load_recent_matches_from_leagueofgraphs(page)
        return ExternalProfile(
            game_name=canonical_game_name,
            tag_line=canonical_tag_line,
            summoner_level=summoner_level,
            profile_icon_id=profile_icon_id,
            matches=matches,
        )

    def _load_recent_matches_from_leagueofgraphs(self, page: str) -> list[MatchSummary]:
        row_pattern = re.compile(
            r'<td class="championCellLight">\s*<a href="/match/[^/]+/(?P<match_id>\d+)#participant\d+">.*?'
            r'class="champion-(?P<champion_id>\d+)-48\s+"[^>]*alt="(?P<champion>[^"]+)".*?'
            r'<div class="victoryDefeatText (?P<result>victory|defeat|remade)">(?P<result_text>[^<]+)</div>.*?'
            r'<div class="gameMode[^"]*"[^>]*tooltip-vertical-offset="0" tooltip="(?P<queue>[^"]+)">.*?</div>.*?'
            r'<div class="gameDuration">\s*(?P<duration>\d+)min\s*(?P<seconds>\d+)s\s*</div>.*?'
            r'<div class="kda">\s*<span class="kills">(?P<kills>\d+)</span>.*?'
            r'<span class="deaths">(?P<deaths>\d+)</span>.*?'
            r'<span class="assists">(?P<assists>\d+)</span>.*?'
            r'<div class="cs">\s*<span class="number">(?P<cs>\d+)</span>\s*CS',
            re.IGNORECASE | re.DOTALL,
        )

        matches: list[MatchSummary] = []
        for match in row_pattern.finditer(page):
            kills = int(match.group("kills"))
            deaths = int(match.group("deaths"))
            assists = int(match.group("assists"))
            duration_min = max(1, int(match.group("duration")))
            matches.append(
                MatchSummary(
                    match_id=match.group("match_id"),
                    champion=self._clean_html_text(match.group("champion")),
                    champion_id=int(match.group("champion_id")),
                    role="UNKNOWN",
                    queue_name=self._clean_html_text(match.group("queue")),
                    won=match.group("result") == "victory",
                    kills=kills,
                    deaths=deaths,
                    assists=assists,
                    cs=int(match.group("cs")),
                    duration_min=duration_min,
                    damage=0,
                    gold=0,
                    kda=round((kills + assists) / max(1, deaths), 2),
                )
            )
            if len(matches) >= MATCH_PAGE_SIZE:
                break
        return matches[:MAX_RECENT_MATCHES]

    def _load_leagueofgraphs_ranked(self, platform: str, game_name: str, tag_line: str) -> list[dict]:
        region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
        if not region:
            return []

        url = f"https://www.leagueofgraphs.com/summoner/{region}/{self._slug(game_name, tag_line)}"
        page = self._get_text(url, context="LeagueOfGraphs perfil")
        entries: list[dict] = []
        patterns = (
            ("Ranked Solo/Duo", "RANKED_SOLO_5x5", r"Ranked Solo/Duo"),
            ("Ranked Flex", "RANKED_FLEX_SR", r"Ranked Flex"),
        )
        for label, queue_type, tooltip_label in patterns:
            pattern = re.compile(
                rf"<highlight>{tooltip_label}</highlight><br/>.*?player reached\s+([A-Za-z]+)\s+([IV]+)"
                rf".*?At the end of the season, this player was\s+([A-Za-z]+)\s+([IV]+)",
                re.IGNORECASE | re.DOTALL,
            )
            match = pattern.search(page)
            if match:
                tier = TIER_ALIASES.get(match.group(3).lower())
                rank = DIVISION_ALIASES.get(match.group(4).upper(), match.group(4).upper())
                if tier:
                    entries.append(
                        {
                            "queueType": queue_type,
                            "tier": tier,
                            "rank": rank,
                            "leaguePoints": 0,
                            "wins": 0,
                            "losses": 0,
                        }
                    )
                    continue

            summary_pattern = re.compile(
                rf"{tooltip_label}.*?([A-Za-z]+)\s+([IV]+).*?Wins:\s*(\d+)\s*\(([\d.]+)%\)",
                re.IGNORECASE | re.DOTALL,
            )
            summary_match = summary_pattern.search(page)
            if not summary_match:
                continue
            tier = TIER_ALIASES.get(summary_match.group(1).lower())
            rank = DIVISION_ALIASES.get(summary_match.group(2).upper(), summary_match.group(2).upper())
            wins = int(summary_match.group(3))
            winrate = float(summary_match.group(4))
            total_games = max(wins, round(wins / max(0.01, winrate / 100.0)))
            losses = max(0, total_games - wins)
            if tier:
                entries.append(
                    {
                        "queueType": queue_type,
                        "tier": tier,
                        "rank": rank,
                        "leaguePoints": 0,
                        "wins": wins,
                        "losses": losses,
                        "winrate": winrate,
                    }
                )
        return entries

    def _parse_leagueofgraphs_champion_table(self, page: str, limit: int | None = None) -> list[ChampionPlayStat]:
        table_match = re.search(
            r'<table class="data_table summoner_champions_details_table sortable_table">(.*?)</table>',
            page,
            re.IGNORECASE | re.DOTALL,
        )
        if not table_match:
            return []

        champions: list[ChampionPlayStat] = []
        row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
        for row in row_pattern.findall(table_match.group(1)):
            champion_id_match = re.search(r'class="champion-(?P<champion_id>\d+)-[\d-]*"', row, re.IGNORECASE)
            champion_name_match = re.search(r'alt="(?P<champion>[^"]+)"', row, re.IGNORECASE)
            played_match = re.search(r'<td[^>]+data-sort-value="(?P<played>\d+)"', row, re.IGNORECASE)
            if not champion_id_match or not champion_name_match or not played_match:
                continue
            champions.append(
                ChampionPlayStat(
                    champion=self._clean_html_text(champion_name_match.group("champion")),
                    champion_id=int(champion_id_match.group("champion_id")),
                    games=int(played_match.group("played")),
                )
            )
            if limit is not None and len(champions) >= limit:
                break
        return champions

    def _load_ranked_preferences_from_leagueofgraphs(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
    ) -> tuple[list[ChampionPlayStat], list[RolePlayStat]]:
        region = PLATFORM_TO_LEAGUEOFGRAPHS_REGION.get(platform)
        if not region:
            return [], []

        base_url = f"https://www.leagueofgraphs.com/summoner/champions/{region}/{self._slug(game_name, tag_line)}"
        champions_page = self._get_text(f"{base_url}/soloqueue", context="LeagueOfGraphs campeones SoloQ")
        leagueofgraphs_champions = self._parse_leagueofgraphs_champion_table(champions_page, limit=5)
        leagueofgraphs_icon_map = {
            self._normalize_champion_lookup(champion.champion): champion.champion_id
            for champion in self._parse_leagueofgraphs_champion_table(champions_page)
            if champion.champion_id > 0
        }

        opgg_champions = self._load_ranked_preferences_from_opgg(platform, game_name, tag_line)
        if opgg_champions:
            merged: list[ChampionPlayStat] = []
            for champion in opgg_champions:
                merged.append(
                    ChampionPlayStat(
                        champion=champion.champion,
                        champion_id=leagueofgraphs_icon_map.get(
                            self._normalize_champion_lookup(champion.champion),
                            champion.champion_id,
                        ),
                        games=champion.games,
                    )
                )
            return merged[:5], []

        return leagueofgraphs_champions, []

    def _load_ranked_preferences_from_opgg(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
    ) -> list[ChampionPlayStat]:
        opgg_region = PLATFORM_TO_OPGG_REGION.get(platform)
        if not opgg_region:
            return []

        url = f"https://op.gg/lol/summoners/{opgg_region}/{self._slug(game_name, tag_line)}?queue_type=SOLORANKED"
        page = self._get_text(url, context="OP.GG campeones SoloQ")
        description_match = re.search(
            r'<meta name="description" content="([^"]+)"',
            page,
            re.IGNORECASE,
        )
        if not description_match:
            return []

        description = html.unescape(description_match.group(1))
        entries = re.findall(r"([A-Za-z0-9' .:-]+?)\s*-\s*(\d+)Win\s+(\d+)Lose", description, re.IGNORECASE)
        champions: list[ChampionPlayStat] = []
        for champion_name, wins, losses in entries[:5]:
            champions.append(
                ChampionPlayStat(
                    champion=self._clean_html_text(champion_name),
                    champion_id=0,
                    games=int(wins) + int(losses),
                )
            )
        return champions

    @staticmethod
    def _fallback_most_played_champions(matches: list[MatchSummary]) -> list[ChampionPlayStat]:
        champion_counts: dict[tuple[str, int], int] = {}
        for match in matches:
            queue_name = match.queue_name.casefold()
            if not any(label in queue_name for label in SOLOQUEUE_LABELS):
                continue
            key = (match.champion, match.champion_id)
            champion_counts[key] = champion_counts.get(key, 0) + 1
        ordered = sorted(champion_counts.items(), key=lambda item: (-item[1], item[0][0].casefold()))
        return [
            ChampionPlayStat(champion=champion, champion_id=champion_id, games=games)
            for (champion, champion_id), games in ordered[:5]
        ]

    @staticmethod
    def _fallback_most_played_roles(matches: list[MatchSummary]) -> list[RolePlayStat]:
        role_counts: dict[str, int] = {}
        for match in matches:
            role = match.role
            if role == "UNKNOWN":
                continue
            role_counts[role] = role_counts.get(role, 0) + 1
        ordered = sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))
        return [RolePlayStat(role=role, games=games) for role, games in ordered[:3]]

    @staticmethod
    def _parse_porofessor_duration_minutes(source: str) -> int:
        duration_match = re.search(r'id="gameDuration"[^>]*>\((\d+):(\d+)\)', source)
        if not duration_match:
            return 0
        minutes = int(duration_match.group(1))
        seconds = int(duration_match.group(2))
        return minutes + (1 if seconds >= 30 else 0)

    @staticmethod
    def _infer_map_name_from_queue(queue_name: str) -> str:
        normalized = queue_name.lower()
        if "aram" in normalized:
            return "Howling Abyss"
        if "arena" in normalized:
            return "Arena"
        if "swarm" in normalized:
            return "Swarm"
        return "Summoner's Rift"

    def _load_live_game_from_porofessor(
        self,
        platform: str,
        game_name: str,
        tag_line: str,
    ) -> LiveGameParticipantSummary | None:
        porofessor_region = PLATFORM_TO_POROFESSOR_REGION.get(platform)
        if not porofessor_region:
            return None

        slug = quote(f"{game_name}-{tag_line}", safe="-")
        url = f"https://porofessor.gg/partial/live-partial/{porofessor_region}/{slug}"
        headers = {"X-Requested-With": "XMLHttpRequest"}
        try:
            source = self._get_text(url, context="Porofessor partida en vivo", headers=headers)
        except RiotApiError:
            return None

        lowered = source.lower()
        canonical_game_name = game_name
        canonical_tag_line = tag_line
        if "the summoner is not in-game" in lowered:
            return LiveGameParticipantSummary(
                game_name=canonical_game_name,
                tag_line=canonical_tag_line,
                platform=platform,
                in_game=False,
                status_text="Fuera de partida",
            )
        if "summoner not found" in lowered:
            return LiveGameParticipantSummary(
                game_name=canonical_game_name,
                tag_line=canonical_tag_line,
                platform=platform,
                in_game=False,
                status_text="No se pudo consultar la fuente externa de partida en vivo",
            )

        queue_match = re.search(
            r'<h2[^>]*class="left relative"[^>]*>\s*(.*?)\s*<span[^>]*id="gameDuration"',
            source,
            re.IGNORECASE | re.DOTALL,
        )
        queue_name = self._clean_html_text(queue_match.group(1)) if queue_match else "Partida activa"
        duration_min = self._parse_porofessor_duration_minutes(source)

        target_key = self._normalize_lookup_name(f"{game_name}#{tag_line}")
        card_start_pattern = re.compile(
            r'<div class="card card-\d+" data-summonername="(?P<name>[^"]+)"[^>]*>',
            re.IGNORECASE,
        )
        card_starts = list(card_start_pattern.finditer(source))
        participants = self._parse_live_game_players_from_porofessor(source, card_starts)
        if not participants:
            return None

        selected_player = next(
            (
                participant
                for participant in participants
                if self._normalize_lookup_name(f"{participant.game_name}#{participant.tag_line}") == target_key
            ),
            None,
        )
        if selected_player is None:
            return LiveGameParticipantSummary(
                game_name=canonical_game_name,
                tag_line=canonical_tag_line,
                platform=platform,
                in_game=False,
                status_text="La fuente externa no encontro al jugador dentro de la partida",
            )

        canonical_game_name = selected_player.game_name
        canonical_tag_line = selected_player.tag_line
        team_size = sum(1 for participant in participants if participant.team_color == selected_player.team_color)
        enemy_team_size = sum(1 for participant in participants if participant.team_color != selected_player.team_color)
        queue_name = queue_name or "Partida activa"
        game = LiveGameSummary(
            queue_name=queue_name,
            game_mode=queue_name,
            map_name=self._infer_map_name_from_queue(queue_name),
            duration_min=duration_min,
            team_size=team_size,
            enemy_team_size=enemy_team_size,
        )
        status_parts = [
            game.queue_name,
            f"{game.duration_min} min" if game.duration_min > 0 else "Duracion N/D",
            game.map_name,
        ]

        return LiveGameParticipantSummary(
            game_name=canonical_game_name,
            tag_line=canonical_tag_line,
            platform=platform,
            in_game=True,
            champion=selected_player.champion or "Campeon desconocido",
            champion_id=selected_player.champion_id,
            role=selected_player.role,
            game=game,
            status_text=" - ".join(status_parts),
            participants=copy.deepcopy(participants),
        )

    def _parse_live_game_players_from_porofessor(
        self,
        source: str,
        card_starts: list[re.Match[str]],
    ) -> list[LiveGamePlayerDetails]:
        participants: list[LiveGamePlayerDetails] = []
        for index, match in enumerate(card_starts):
            body_start = match.end()
            body_end = card_starts[index + 1].start() if index + 1 < len(card_starts) else len(source)
            body = source[body_start:body_end]

            raw_name = html.unescape(match.group("name")).strip()
            if "#" in raw_name:
                parsed_game_name, parsed_tag_line = [segment.strip() for segment in raw_name.split("#", 1)]
            else:
                parsed_game_name, parsed_tag_line = raw_name, ""

            team_match = re.search(r'<div class="cardHeader\s+(blue|red)"', body, re.IGNORECASE)
            team_color = team_match.group(1).lower() if team_match else "blue"
            champion_match = re.search(r'<img[^>]+class="champion[^"]*"[^>]+alt="([^"]+)"', body, re.IGNORECASE)
            champion_id_match = re.search(r'class="champion-(\d+)-', body, re.IGNORECASE)
            role = self._extract_live_role_from_porofessor(body)
            level_match = re.search(r"Summoner Level:\s*(\d+)", body, re.IGNORECASE)
            mastery_match = re.search(r"Mastery Level\s+(\d+)", body, re.IGNORECASE)

            title_match = re.search(
                r'<div class="title oneLiner">\s*(\d+(?:\.\d+)?)%\s*Win.*?<span class="subtitle">\((\d+)\s*Played\)</span>',
                body,
                re.IGNORECASE | re.DOTALL,
            )
            recent_winrate = float(title_match.group(1)) if title_match else None
            recent_games = int(title_match.group(2)) if title_match else None

            kda_match = re.search(
                r'<span class="kills">([\d.]+)</span>\s*/\s*<span class="deaths">([\d.]+)</span>\s*/\s*<span class="assists">([\d.]+)</span>',
                body,
                re.IGNORECASE | re.DOTALL,
            )
            avg_kda = ""
            if kda_match:
                avg_kda = f"{kda_match.group(1)} / {kda_match.group(2)} / {kda_match.group(3)}"

            champion_rank_match = re.search(r"Rank:\s*<a[^>]*>\s*(#[\d,]+)\s*</a>", body, re.IGNORECASE | re.DOTALL)
            spell_names = [
                self._clean_html_text(spell_name)
                for spell_name in re.findall(
                    r'<img[^>]+alt="([^"]+)"[^>]+class="[^"]*\bspell-\d+-16\b[^"]*"',
                    body,
                    re.IGNORECASE,
                )
            ]
            spell_ids = [
                int(spell_id)
                for spell_id in re.findall(
                    r'class="[^"]*\bspell-(\d+)-16\b[^"]*"',
                    body,
                    re.IGNORECASE,
                )
            ]
            tag_titles = [
                self._clean_html_text(tag_title)
                for tag_title in re.findall(
                    r"<itemname class='tagTitle [^']+'>([^<]+)</itemname>",
                    body,
                    re.IGNORECASE,
                )
            ]

            participants.append(
                LiveGamePlayerDetails(
                    game_name=parsed_game_name,
                    tag_line=parsed_tag_line,
                    team_color=team_color,
                    champion=self._clean_html_text(champion_match.group(1)) if champion_match else "Campeon desconocido",
                    champion_id=int(champion_id_match.group(1)) if champion_id_match else 0,
                    role=role,
                    summoner_level=int(level_match.group(1)) if level_match else 0,
                    recent_winrate=recent_winrate,
                    recent_games=recent_games,
                    avg_kda=avg_kda,
                    champion_rank=champion_rank_match.group(1) if champion_rank_match else None,
                    mastery_level=int(mastery_match.group(1)) if mastery_match else None,
                    spell_ids=spell_ids[:2],
                    spell_names=spell_names[:2],
                    tags=tag_titles[:5],
                )
            )
        return participants

    def _load_ranked_entries(self, platform: str, game_name: str, tag_line: str) -> tuple[list[dict], bool]:
        entries = self._load_ranked_from_opgg(platform, game_name, tag_line)
        if entries:
            return entries, True

        entries = self._load_leagueofgraphs_ranked(platform, game_name, tag_line)
        if entries:
            return entries, True

        return [], False

    def _parse_ranked_entries(
        self,
        league_entries: list[dict],
    ) -> tuple[RankedEntry | None, RankedEntry | None, float | None, float | None]:
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
        profile: ExternalProfile,
        platform: str,
        league_entries: list[dict],
        ranked_available: bool,
        recent_winrate: float,
        include_matches: bool,
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
        else:
            ugg_winrate = self._load_winrate_from_ugg(platform, profile.game_name, profile.tag_line)
            if ugg_winrate is not None:
                global_winrate = round(ugg_winrate, 1)

        if ranked_games is None:
            ranked_games = self._load_games_from_opgg(platform, profile.game_name, profile.tag_line)
        if ranked_games is None:
            ranked_games = self._load_games_from_ugg(platform, profile.game_name, profile.tag_line)

        matches = profile.matches if include_matches else []
        most_played_champions: list[ChampionPlayStat] = []
        most_played_roles: list[RolePlayStat] = []
        if include_matches:
            try:
                most_played_champions, most_played_roles = self._load_ranked_preferences_from_leagueofgraphs(
                    platform,
                    profile.game_name,
                    profile.tag_line,
                )
            except RiotApiError:
                most_played_champions, most_played_roles = [], []

            if not most_played_champions:
                most_played_champions = self._fallback_most_played_champions(matches)

        return PlayerSummary(
            game_name=profile.game_name,
            tag_line=profile.tag_line,
            summoner_level=profile.summoner_level,
            profile_icon_id=profile.profile_icon_id,
            platform=platform,
            opgg_url=self.build_opgg_profile_url(platform, profile.game_name, profile.tag_line),
            soloq=soloq,
            flex=flex,
            estimated_mmr=estimated_mmr,
            global_winrate=global_winrate,
            ranked_games=ranked_games,
            recent_winrate=recent_winrate,
            matches=copy.deepcopy(matches),
            most_played_champions=copy.deepcopy(most_played_champions),
            most_played_roles=copy.deepcopy(most_played_roles),
            ranked_available=ranked_available,
        )

    def fetch_player_overview(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
    ) -> PlayerSummary:
        profile = self._load_profile_from_leagueofgraphs(platform, game_name, tag_line)
        league_entries, ranked_available = self._load_ranked_entries(platform, profile.game_name, profile.tag_line)
        return self._build_summary(
            profile=profile,
            platform=platform,
            league_entries=league_entries,
            ranked_available=ranked_available,
            recent_winrate=50.0,
            include_matches=False,
        )

    def fetch_player_summary(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
    ) -> PlayerSummary:
        self._emit_progress("Cargando perfil externo...")
        profile = self._load_profile_from_leagueofgraphs(platform, game_name, tag_line)
        self._emit_progress("Cargando ranked desde fuentes externas...")
        league_entries, ranked_available = self._load_ranked_entries(platform, profile.game_name, profile.tag_line)

        match_count = len(profile.matches)
        if match_count:
            self._emit_progress(f"Procesadas {match_count} partidas recientes.")
        else:
            self._emit_progress("No se encontraron partidas recientes en la fuente externa.")

        wins = sum(1 for match in profile.matches if match.won)
        recent_winrate = round((wins / max(1, len(profile.matches))) * 100, 1) if profile.matches else 0.0
        return self._build_summary(
            profile=profile,
            platform=platform,
            league_entries=league_entries,
            ranked_available=ranked_available,
            recent_winrate=recent_winrate,
            include_matches=True,
        )

    def fetch_live_game_summary(
        self,
        game_name: str,
        tag_line: str,
        platform: str,
        fast_mode: bool = False,
    ) -> LiveGameParticipantSummary:
        del fast_mode
        profile = self._load_profile_from_leagueofgraphs(platform, game_name, tag_line)
        spectator = None
        try:
            spectator = self._load_spectator_session(platform, profile.game_name, profile.tag_line)
        except RiotApiError:
            spectator = None
        fallback = self._load_live_game_from_porofessor(
            platform=platform,
            game_name=profile.game_name,
            tag_line=profile.tag_line,
        )
        if fallback is not None:
            fallback.spectate_url = f"{self.build_opgg_profile_url(platform, profile.game_name, profile.tag_line)}/ingame"
            fallback.spectator = spectator
            return fallback

        if spectator is not None:
            return LiveGameParticipantSummary(
                game_name=profile.game_name,
                tag_line=profile.tag_line,
                platform=platform,
                in_game=True,
                champion="N/D",
                champion_id=0,
                role="UNKNOWN",
                game=LiveGameSummary(
                    queue_name="Partida activa",
                    game_mode="Partida activa",
                    map_name="Summoner's Rift",
                    duration_min=0,
                    team_size=0,
                    enemy_team_size=0,
                ),
                status_text="Partida activa detectada por Riot API",
                spectate_url=f"{self.build_opgg_profile_url(platform, profile.game_name, profile.tag_line)}/ingame",
                spectator=spectator,
            )

        return LiveGameParticipantSummary(
            game_name=profile.game_name,
            tag_line=profile.tag_line,
            platform=platform,
            in_game=False,
            status_text="No se pudo confirmar la partida con las fuentes externas",
            spectate_url=f"{self.build_opgg_profile_url(platform, profile.game_name, profile.tag_line)}/ingame",
            spectator=spectator,
        )


def estimate_mmr(entry: RankedEntry | None, recent_winrate: float) -> int | None:
    if not entry or not entry.tier:
        return None

    base = TIER_BASE.get(entry.tier.upper(), 1000)
    division = RANK_OFFSET.get(entry.rank, 0)
    lp_factor = int(entry.league_points * 0.8)
    form_factor = int((recent_winrate - 50) * 6)
    return base + division + lp_factor + form_factor
