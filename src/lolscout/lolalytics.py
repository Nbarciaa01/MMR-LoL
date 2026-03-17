from __future__ import annotations

import copy
from dataclasses import dataclass, field
import html
import json
from pathlib import Path
import re
import time

import requests

from .models import (
    LolalyticsAsset,
    LolalyticsBuildDetail,
    LolalyticsBuildSection,
    LolalyticsChampion,
    LolalyticsMatchup,
    LolalyticsSkillOrderRow,
)


LOLALYTICS_BASE_URL = "https://lolalytics.com/es"
LOLALYTICS_CACHE_DIR = Path.cwd() / ".lolscout_cache"
LOLALYTICS_INDEX_TTL_SECONDS = 21600
LOLALYTICS_DETAIL_TTL_SECONDS = 1800
CDRAGON_BASE_URL = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1"
CDRAGON_TTL_SECONDS = 86400
_CHAMPION_SKILL_NAME_CACHE: dict[str, dict[str, str]] = {}
_CDRAGON_SUMMARY_CACHE: list[dict] | None = None
_CHAMPION_INDEX_OBJECT_CACHE: list[LolalyticsChampion] | None = None
_BUILD_DETAIL_OBJECT_CACHE: dict[str, LolalyticsBuildDetail] = {}
LOLALYTICS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

SPECIAL_CHAMPION_NAMES = {
    "aurelionsol": "Aurelion Sol",
    "belveth": "Bel'Veth",
    "chogath": "Cho'Gath",
    "drmundo": "Dr. Mundo",
    "jarvaniv": "Jarvan IV",
    "kaisa": "Kai'Sa",
    "khazix": "Kha'Zix",
    "kogmaw": "Kog'Maw",
    "ksante": "K'Sante",
    "leesin": "Lee Sin",
    "masteryi": "Master Yi",
    "missfortune": "Miss Fortune",
    "nunu": "Nunu & Willump",
    "nunuwillump": "Nunu & Willump",
    "reksai": "Rek'Sai",
    "renataglasc": "Renata Glasc",
    "tahmkench": "Tahm Kench",
    "twistedfate": "Twisted Fate",
    "velkoz": "Vel'Koz",
    "xinzhao": "Xin Zhao",
}


class LolalyticsError(Exception):
    pass


def _normalise_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return _normalise_space(html.unescape(text))


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = value.replace(",", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        return None


def _slug_to_name(slug: str) -> str:
    if slug in SPECIAL_CHAMPION_NAMES:
        return SPECIAL_CHAMPION_NAMES[slug]
    parts = re.split(r"[_-]+", slug)
    return " ".join(part.capitalize() for part in parts if part)


def _normalise_lookup(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _extract_attr(tag_html: str, attr_name: str) -> str | None:
    match = re.search(rf'{attr_name}=\"([^\"]+)\"', tag_html)
    if match is None:
        return None
    return _normalise_space(html.unescape(match.group(1)))


def _extract_image_src(tag_html: str) -> str | None:
    src = _extract_attr(tag_html, "src")
    if src:
        return src

    srcset = _extract_attr(tag_html, "srcset")
    if not srcset:
        return None
    return srcset.split(",")[0].strip().split()[0]


def _extract_image_assets(section_html: str, asset_marker: str, selected_only: bool = False) -> list[LolalyticsAsset]:
    assets: list[LolalyticsAsset] = []
    for match in re.finditer(r"<img[^>]+>", section_html):
        tag_html = match.group(0)
        if f"/{asset_marker}" not in tag_html:
            continue

        alt_text = _extract_attr(tag_html, "alt") or ""
        class_name = _extract_attr(tag_html, "class") or ""
        if not alt_text or alt_text.casefold() == "statmod":
            continue
        if selected_only and "grayscale" in class_name:
            continue

        assets.append(
            LolalyticsAsset(
                name=alt_text,
                icon_url=_extract_image_src(tag_html),
            )
        )
    return assets


def _extract_skill_assets(section_html: str) -> list[LolalyticsAsset]:
    assets: list[LolalyticsAsset] = []
    for match in re.finditer(r"<img[^>]+>", section_html):
        tag_html = match.group(0)
        if "/skill68/" not in tag_html:
            continue

        alt_text = _extract_attr(tag_html, "alt") or ""
        letter_match = re.search(r"\b([QWER])\s+Skill\b", alt_text)
        if letter_match is None:
            continue

        letter = letter_match.group(1).upper()
        assets.append(
            LolalyticsAsset(
                name=alt_text,
                icon_url=_extract_image_src(tag_html),
                label=letter,
            )
        )
    return assets[:3]


def _extract_skill_order_rows(section_html: str) -> list[LolalyticsSkillOrderRow]:
    rows: list[LolalyticsSkillOrderRow] = []
    row_pattern = re.compile(
        r'(<div class=\"m-auto mb-\[2px\] flex w-\[317px\]\" q:key=\"\d+\">.*?)(?=<div class=\"m-auto mb-\[2px\] flex w-\[317px\]\" q:key=\"\d+\">|<div class=\"pt-\[6px\] text-center text-\[12px\]\"|$)',
        re.S,
    )
    for row_html in row_pattern.findall(section_html):
        assets = _extract_skill_assets(row_html)
        if not assets:
            continue
        levels = [int(level) for level in re.findall(r">(\d{1,2})<", row_html)]
        rows.append(LolalyticsSkillOrderRow(skill=assets[0], levels=levels))
    return rows


def _extract_section_bounds(page_html: str, labels: list[str]) -> dict[str, tuple[int, int]]:
    positions: dict[str, int] = {}
    cursor = 0
    for label in labels:
        position = page_html.find(label, cursor)
        if position == -1:
            continue
        positions[label] = position
        cursor = position + len(label)

    bounds: dict[str, tuple[int, int]] = {}
    ordered = sorted(positions.items(), key=lambda item: item[1])
    for index, (label, start) in enumerate(ordered):
        end = len(page_html)
        if index + 1 < len(ordered):
            end = ordered[index + 1][1]
        bounds[label] = (start, end)
    return bounds


def _build_section(
    title: str,
    items: list[LolalyticsAsset],
    win_rate: float | None,
    games: int | None,
) -> LolalyticsBuildSection:
    return LolalyticsBuildSection(title=title, items=items, win_rate=win_rate, games=games)


@dataclass
class LolalyticsClient:
    timeout: int = 16
    session: requests.Session = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()
        LOLALYTICS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _cache_path(cache_key: str) -> Path:
        safe_key = re.sub(r"[^a-z0-9_-]+", "_", cache_key.casefold())
        return LOLALYTICS_CACHE_DIR / f"lolalytics_{safe_key}.json"

    def _load_cache(self, cache_key: str) -> dict | None:
        cache_path = self._cache_path(cache_key)
        if not cache_path.exists():
            return None
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _store_cache(self, cache_key: str, text: str) -> None:
        cache_path = self._cache_path(cache_key)
        payload = {"cached_at": time.time(), "text": text}
        try:
            cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            return

    def _fetch_text(self, url: str, cache_key: str, ttl_seconds: int, force_refresh: bool = False) -> str:
        cached = self._load_cache(cache_key)
        if not force_refresh and cached:
            cached_at = float(cached.get("cached_at", 0) or 0)
            cached_text = str(cached.get("text", "") or "")
            if cached_text and cached_at > 0 and time.time() - cached_at <= ttl_seconds:
                return cached_text

        try:
            response = self.session.get(url, headers=LOLALYTICS_HEADERS, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            if cached and cached.get("text"):
                return str(cached["text"])
            raise LolalyticsError(f"No se pudo cargar {url}: {exc}") from exc

        text = response.text
        self._store_cache(cache_key, text)
        return text

    def _fetch_json(
        self,
        url: str,
        cache_key: str,
        ttl_seconds: int,
        force_refresh: bool = False,
    ) -> object:
        payload = self._fetch_text(url, cache_key, ttl_seconds=ttl_seconds, force_refresh=force_refresh)
        try:
            return json.loads(payload)
        except ValueError as exc:
            raise LolalyticsError(f"No se pudo interpretar la respuesta JSON de {url}.") from exc

    def _fetch_champion_skill_names(
        self,
        slug: str,
        champion_name: str,
        force_refresh: bool = False,
    ) -> dict[str, str]:
        cache_key = _normalise_lookup(slug) or _normalise_lookup(champion_name)
        if not force_refresh and cache_key in _CHAMPION_SKILL_NAME_CACHE:
            return dict(_CHAMPION_SKILL_NAME_CACHE[cache_key])

        global _CDRAGON_SUMMARY_CACHE
        if force_refresh or _CDRAGON_SUMMARY_CACHE is None:
            summary_payload = self._fetch_json(
                f"{CDRAGON_BASE_URL}/champion-summary.json",
                "cdragon_champion_summary",
                ttl_seconds=CDRAGON_TTL_SECONDS,
                force_refresh=force_refresh,
            )
            if not isinstance(summary_payload, list):
                return {}
            _CDRAGON_SUMMARY_CACHE = [entry for entry in summary_payload if isinstance(entry, dict)]

        summary_payload = _CDRAGON_SUMMARY_CACHE
        if not isinstance(summary_payload, list):
            return {}

        targets = {
            _normalise_lookup(slug),
            _normalise_lookup(_slug_to_name(slug)),
            _normalise_lookup(champion_name),
        }
        champion_id = 0
        for entry in summary_payload:
            if not isinstance(entry, dict):
                continue
            alias = _normalise_lookup(str(entry.get("alias", "")))
            name = _normalise_lookup(str(entry.get("name", "")))
            if alias in targets or name in targets:
                champion_id = int(entry.get("id", 0) or 0)
                break

        if champion_id <= 0:
            return {}

        champion_payload = self._fetch_json(
            f"{CDRAGON_BASE_URL}/champions/{champion_id}.json",
            f"cdragon_champion_{champion_id}",
            ttl_seconds=CDRAGON_TTL_SECONDS,
            force_refresh=force_refresh,
        )
        if not isinstance(champion_payload, dict):
            return {}

        skills: dict[str, str] = {}
        for spell in champion_payload.get("spells", []):
            if not isinstance(spell, dict):
                continue
            key = str(spell.get("spellKey", "")).upper().strip()
            name = _normalise_space(str(spell.get("name", "")))
            if key and name:
                skills[key] = name
        if cache_key:
            _CHAMPION_SKILL_NAME_CACHE[cache_key] = dict(skills)
        return skills

    def fetch_champion_index(self, force_refresh: bool = False) -> list[LolalyticsChampion]:
        global _CHAMPION_INDEX_OBJECT_CACHE
        if not force_refresh and _CHAMPION_INDEX_OBJECT_CACHE is not None:
            return copy.deepcopy(_CHAMPION_INDEX_OBJECT_CACHE)

        home_html = self._fetch_text(
            f"{LOLALYTICS_BASE_URL}/",
            "index_home",
            ttl_seconds=LOLALYTICS_INDEX_TTL_SECONDS,
            force_refresh=force_refresh,
        )
        slugs = sorted(set(re.findall(r"/es/lol/([a-z0-9_]+)/(?:(?:build|counters|leaderboard)/)", home_html)))
        if not slugs:
            raise LolalyticsError("No se pudo obtener el catalogo de campeones desde Lolalytics.")

        champions = [
            LolalyticsChampion(
                slug=slug,
                name=_slug_to_name(slug),
                icon_url=f"https://cdn5.lolalytics.com/champx46/{slug}.webp",
            )
            for slug in slugs
        ]
        ordered = sorted(champions, key=lambda champion: champion.name.casefold())
        _CHAMPION_INDEX_OBJECT_CACHE = copy.deepcopy(ordered)
        return ordered

    def fetch_build_detail(self, slug: str, force_refresh: bool = False) -> LolalyticsBuildDetail:
        if not force_refresh and slug in _BUILD_DETAIL_OBJECT_CACHE:
            return copy.deepcopy(_BUILD_DETAIL_OBJECT_CACHE[slug])

        build_url = f"{LOLALYTICS_BASE_URL}/lol/{slug}/build/"
        counters_url = f"{LOLALYTICS_BASE_URL}/lol/{slug}/counters/"
        build_html = self._fetch_text(
            build_url,
            f"build_{slug}",
            ttl_seconds=LOLALYTICS_DETAIL_TTL_SECONDS,
            force_refresh=force_refresh,
        )
        counters_html = self._fetch_text(
            counters_url,
            f"counters_{slug}",
            ttl_seconds=LOLALYTICS_DETAIL_TTL_SECONDS,
            force_refresh=force_refresh,
        )
        detail = self._parse_build_page(slug, build_html)
        try:
            skill_names = self._fetch_champion_skill_names(slug, detail.champion, force_refresh=force_refresh)
        except LolalyticsError:
            skill_names = {}
        for asset in detail.skill_priority:
            if asset.label:
                asset.name = skill_names.get(asset.label, asset.name)
        for row in detail.skill_order:
            if row.skill.label:
                row.skill.name = skill_names.get(row.skill.label, row.skill.name)
        detail.best_matchups, detail.worst_matchups = self._parse_matchups(slug, counters_html)
        detail.build_url = build_url
        detail.counters_url = counters_url
        _BUILD_DETAIL_OBJECT_CACHE[slug] = copy.deepcopy(detail)
        return detail

    def _parse_build_page(self, slug: str, page_html: str) -> LolalyticsBuildDetail:
        detail = LolalyticsBuildDetail(
            slug=slug,
            champion=_slug_to_name(slug),
            role="Desconocido",
        )

        icon_match = re.search(
            r'src=\"(https://cdn5\.lolalytics\.com/champ140/[^"]+\.webp)\"[^>]+alt=\"([^\"]+)\"',
            page_html,
        )
        if icon_match:
            detail.icon_url = icon_match.group(1)
            detail.champion = _normalise_space(html.unescape(icon_match.group(2)))

        summary_match = re.search(r"<p class=\"lolx-links[^\"]*\"[^>]*>(.*?)</p>", page_html, re.S)
        summary_html = summary_match.group(1) if summary_match else ""
        summary_text = _strip_tags(summary_html)
        detail.summary = summary_text

        summary_header_match = re.search(
            rf"{re.escape(detail.champion)}\s+([a-z]+)\s+has a\s+([\d.]+)%\s+win rate.*?Patch\s+([\d.]+)",
            summary_text,
            re.I,
        )
        if summary_header_match:
            detail.role = summary_header_match.group(1).upper()
            detail.patch = summary_header_match.group(3)
            detail.win_rate = _parse_float(summary_header_match.group(2))

        rank_tier_match = re.search(r"rank\s+(\d+)\s+of\s+(\d+)\s+and graded\s+([A-Z+]+)\s+Tier", summary_text, re.I)
        if rank_tier_match:
            detail.rank_label = f"{rank_tier_match.group(1)} / {rank_tier_match.group(2)}"
            detail.tier = rank_tier_match.group(3).upper()

        strong_match = re.search(
            r"strong counter to\s+(.+?)\s+while\s+.+?countered most by\s+(.+?)\.",
            summary_text,
            re.I,
        )
        if strong_match:
            detail.strong_against = [
                _normalise_space(part.strip(" ."))
                for part in re.split(r",|&", strong_match.group(1))
                if _normalise_space(part.strip(" ."))
            ]
            detail.weak_against = [
                _normalise_space(part.strip(" ."))
                for part in re.split(r",|&", strong_match.group(2))
                if _normalise_space(part.strip(" ."))
            ]

        best_player_match = re.search(
            rf"best\s+{re.escape(detail.champion)}\s+players have a\s+([\d.]+)%\s+win rate with an average rank of\s+([A-Za-z]+)",
            summary_text,
            re.I,
        )
        if best_player_match:
            detail.best_player_win_rate = _parse_float(best_player_match.group(1))
            detail.best_player_rank = best_player_match.group(2)

        stats_region_start = summary_match.end() if summary_match else 0
        stats_region = _strip_tags(page_html[stats_region_start : stats_region_start + 9000])
        detail.win_rate = detail.win_rate or _parse_float(_first_group(stats_region, r"([\d.]+)\s*%\s*Win Rate"))
        detail.win_rate_delta = _parse_float(_first_group(stats_region, r"([\d.]+)\s*%\s*WR Delta"))
        detail.game_avg_win_rate = _parse_float(_first_group(stats_region, r"([\d.]+)\s*%\s*Game Avg WR"))
        detail.pick_rate = _parse_float(_first_group(stats_region, r"([\d.]+)\s*%\s*Pick Rate"))
        if detail.tier is None:
            detail.tier = _first_group(stats_region, r"\b([A-Z][A-Z+]?)\b\s*Tier")
        if detail.rank_label is None:
            rank_value = _first_group(stats_region, r"(\d+\s*/\s*\d+)\s*Rank")
            if rank_value:
                detail.rank_label = rank_value
        detail.ban_rate = _parse_float(_first_group(stats_region, r"([\d.]+)\s*%\s*Ban Rate"))
        detail.games = _parse_int(_first_group(stats_region, r"([\d,]+)\s*Games"))

        section_labels = [
            "Skill Priority",
            "Summoner Spells",
            "Skill Order",
            "Primary Runes",
            "Secondary",
            "Stat Mods",
            "Starting Items",
            "Core Build",
            "Item 4",
            "Item 5",
            "Item 6",
        ]
        bounds = _extract_section_bounds(page_html, section_labels)

        skill_priority_chunk = _slice_bounds(page_html, bounds.get("Skill Priority"))
        detail.skill_priority = _extract_skill_assets(skill_priority_chunk)

        skill_order_chunk = _slice_bounds(page_html, bounds.get("Skill Order"))
        detail.skill_order = _extract_skill_order_rows(skill_order_chunk)
        detail.skill_order_win_rate = _parse_float(_first_group(skill_order_chunk, r"([\d.]+)<!---->%\s*Win Rate"))
        detail.skill_order_games = _parse_int(_first_group(skill_order_chunk, r"([\d,]+)\s*Games"))

        summoner_spells_chunk = _slice_bounds(page_html, bounds.get("Summoner Spells"))
        detail.summoner_spells = _extract_image_assets(summoner_spells_chunk, "spell64/")

        primary_runes_chunk = _slice_bounds(page_html, bounds.get("Primary Runes"))
        detail.primary_runes = _extract_image_assets(primary_runes_chunk, "rune68/", selected_only=True)
        if not detail.primary_runes:
            detail.primary_runes = _extract_image_assets(primary_runes_chunk, "rune68/")

        secondary_chunk = _slice_bounds(page_html, bounds.get("Secondary"))
        detail.secondary_runes = _extract_image_assets(secondary_chunk, "rune68/", selected_only=True)
        if not detail.secondary_runes:
            detail.secondary_runes = _extract_image_assets(secondary_chunk, "rune68/")

        starting_items_chunk = _slice_bounds(page_html, bounds.get("Starting Items"))
        detail.starting_items = _build_section(
            "Inicio",
            _extract_image_assets(starting_items_chunk, "item64/"),
            _parse_float(_first_group(starting_items_chunk, r"([\d.]+)<!---->%\s*Win Rate")),
            _parse_int(_first_group(starting_items_chunk, r"([\d,]+)\s*Games")),
        )

        core_build_chunk = _slice_bounds(page_html, bounds.get("Core Build"))
        detail.core_build = _build_section(
            "Core",
            _extract_image_assets(core_build_chunk, "item64/"),
            _parse_float(_first_group(core_build_chunk, r"([\d.]+)<!---->%</span><br><span class=\"text-center text-\[12px\] text-gray-400\"")),
            _parse_int(_first_group(core_build_chunk, r"text-gray-400\" q:key=\"60_3\">([\d,]+)</span>")),
        )

        detail.item_four = self._parse_item_options(_slice_bounds(page_html, bounds.get("Item 4")), "Item 4")
        detail.item_five = self._parse_item_options(_slice_bounds(page_html, bounds.get("Item 5")), "Item 5")
        detail.item_six = self._parse_item_options(_slice_bounds(page_html, bounds.get("Item 6")), "Item 6")
        return detail

    @staticmethod
    def _parse_item_options(section_html: str, title: str) -> list[LolalyticsBuildSection]:
        options: list[LolalyticsBuildSection] = []
        pattern = re.compile(
            r"(<img[^>]+/item64/\d+\.webp[^>]+alt=\"[^\"]+\"[^>]*>).*?"
            r"(?:<!--t=[^>]+-->)?([\d.]+)(?:<!---->)?%</span><br><span[^>]*>([\d,]+)</span>",
            re.S,
        )
        for match in pattern.finditer(section_html):
            tag_html = match.group(1)
            item_name = _extract_attr(tag_html, "alt") or ""
            if not item_name:
                continue
            options.append(
                _build_section(
                    title=title,
                    items=[
                        LolalyticsAsset(
                            name=item_name,
                            icon_url=_extract_image_src(tag_html),
                        )
                    ],
                    win_rate=_parse_float(match.group(2)),
                    games=_parse_int(match.group(3)),
                )
            )
        return options

    @staticmethod
    def _parse_matchups(slug: str, counters_html: str) -> tuple[list[LolalyticsMatchup], list[LolalyticsMatchup]]:
        blocks = re.findall(rf"<a href=\"/es/lol/{slug}/vs/([^/]+)/build/\">(.*?)</a></div>", counters_html, flags=re.S)
        entries: list[LolalyticsMatchup] = []
        seen: set[str] = set()
        for opponent_slug, block in blocks:
            if opponent_slug in seen:
                continue
            seen.add(opponent_slug)
            name_match = re.search(r'text-\[15px\]\">(?:<!--t=[^>]+-->)?([^<]+)', block)
            wr_match = re.search(
                r'text-center text-xs text-green-300\">(?:<!--t=[^>]+-->)?([\d.]+)(?:<!---->)?%<div class=\"text-cyan-200\">VS',
                block,
            )
            delta_match = re.search(r"<sub>1</sub>\s*([-\d.]+)</span>.*?<sub>2</sub>\s*([-\d.]+)</span>", block, re.S)
            games_match = re.search(r'text-gray-500\">(?:<!--t=[^>]+-->)?([\d,]+)(?:<!---->)? Games', block)
            if not all((name_match, wr_match, delta_match, games_match)):
                continue
            entries.append(
                LolalyticsMatchup(
                    slug=opponent_slug,
                    champion=_normalise_space(html.unescape(name_match.group(1))),
                    win_rate=float(wr_match.group(1)),
                    delta_1=float(delta_match.group(1)),
                    delta_2=float(delta_match.group(2)),
                    games=int(games_match.group(1).replace(",", "")),
                )
            )

        best = sorted(entries, key=lambda item: (item.delta_2, item.win_rate, item.games), reverse=True)[:6]
        worst = sorted(entries, key=lambda item: (item.delta_2, item.win_rate, -item.games))[:6]
        return best, worst


def _first_group(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.S)
    if match is None:
        return None
    return _normalise_space(html.unescape(match.group(1)))


def _slice_bounds(page_html: str, bounds: tuple[int, int] | None) -> str:
    if bounds is None:
        return ""
    start, end = bounds
    return page_html[start:end]
