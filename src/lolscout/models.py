from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RankedEntry:
    queue_type: str
    tier: str
    rank: str
    league_points: int
    wins: int
    losses: int

    @property
    def total_games(self) -> int:
        return self.wins + self.losses

    @property
    def winrate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return (self.wins / self.total_games) * 100

    @property
    def display_rank(self) -> str:
        if not self.tier:
            return "Unranked"
        return f"{self.tier.title()} {self.rank} - {self.league_points} LP"


@dataclass
class MatchSummary:
    match_id: str
    champion: str
    champion_id: int
    role: str
    queue_name: str
    won: bool
    kills: int
    deaths: int
    assists: int
    cs: int
    duration_min: int
    damage: int
    gold: int
    kda: float
    played_at_iso: str | None = None
    played_at_text: str = ""


@dataclass
class ChampionPlayStat:
    champion: str
    champion_id: int
    games: int


@dataclass
class RolePlayStat:
    role: str
    games: int


@dataclass
class PlayerSummary:
    game_name: str
    tag_line: str
    summoner_level: int
    profile_icon_id: int
    platform: str
    opgg_url: str | None = None
    soloq: RankedEntry | None = None
    flex: RankedEntry | None = None
    estimated_mmr: int | None = None
    global_winrate: float | None = None
    ranked_games: int | None = None
    recent_winrate: float = 0.0
    matches: list[MatchSummary] = field(default_factory=list)
    most_played_champions: list[ChampionPlayStat] = field(default_factory=list)
    most_played_roles: list[RolePlayStat] = field(default_factory=list)
    ranked_available: bool = True
    top_mastery_champion_id: int = 0
    top_mastery_level: int | None = None
    top_mastery_points: int | None = None


@dataclass
class TodayLpSummary:
    player: PlayerSummary
    lp_change: int | None = None
    current_lp_score: int | None = None
    baseline_lp_score: int | None = None
    current_rank_text: str = ""
    baseline_rank_text: str = ""
    baseline_local_time: str | None = None
    baseline_source: str = ""
    baseline_note: str = ""
    today_matches: list[MatchSummary] = field(default_factory=list)

    @property
    def riot_id(self) -> str:
        if self.player.tag_line:
            return f"{self.player.game_name}#{self.player.tag_line}"
        return self.player.game_name

    @property
    def change_text(self) -> str:
        if self.lp_change is None:
            return "--"
        if self.lp_change > 0:
            return f"+{self.lp_change} LP"
        return f"{self.lp_change} LP"

    @property
    def is_positive(self) -> bool:
        return self.lp_change is not None and self.lp_change > 0

    @property
    def is_negative(self) -> bool:
        return self.lp_change is not None and self.lp_change < 0


@dataclass
class LiveGameSummary:
    queue_name: str
    game_mode: str
    map_name: str
    duration_min: int
    team_size: int
    enemy_team_size: int


@dataclass
class LiveGamePlayerDetails:
    game_name: str
    tag_line: str
    team_color: str
    champion: str
    champion_id: int
    role: str = "UNKNOWN"
    summoner_level: int = 0
    recent_winrate: float | None = None
    recent_games: int | None = None
    avg_kda: str = ""
    champion_rank: str | None = None
    mastery_level: int | None = None
    spell_ids: list[int] = field(default_factory=list)
    spell_names: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class SpectatorSession:
    platform_id: str
    game_id: int
    encryption_key: str

    @property
    def observer_host(self) -> str:
        return f"spectator.{self.platform_id.lower()}.lol.riotgames.com:80"


@dataclass
class LiveGameParticipantSummary:
    game_name: str
    tag_line: str
    platform: str
    in_game: bool
    champion: str | None = None
    champion_id: int = 0
    mastery_level: int | None = None
    role: str = "UNKNOWN"
    game: LiveGameSummary | None = None
    status_text: str = ""
    spectate_url: str | None = None
    spectator: SpectatorSession | None = None
    participants: list[LiveGamePlayerDetails] = field(default_factory=list)


@dataclass
class LolalyticsChampion:
    slug: str
    name: str
    icon_url: str | None = None


@dataclass
class LolalyticsAsset:
    name: str
    icon_url: str | None = None
    label: str | None = None


@dataclass
class LolalyticsBuildSection:
    title: str
    items: list[LolalyticsAsset] = field(default_factory=list)
    win_rate: float | None = None
    games: int | None = None


@dataclass
class LolalyticsSkillOrderRow:
    skill: LolalyticsAsset
    levels: list[int] = field(default_factory=list)


@dataclass
class LolalyticsMatchup:
    slug: str
    champion: str
    win_rate: float
    delta_1: float
    delta_2: float
    games: int


@dataclass
class LolalyticsBuildDetail:
    slug: str
    champion: str
    role: str
    patch: str | None = None
    icon_url: str | None = None
    summary: str = ""
    tier: str | None = None
    rank_label: str | None = None
    win_rate: float | None = None
    win_rate_delta: float | None = None
    game_avg_win_rate: float | None = None
    pick_rate: float | None = None
    ban_rate: float | None = None
    games: int | None = None
    best_player_win_rate: float | None = None
    best_player_rank: str | None = None
    strong_against: list[str] = field(default_factory=list)
    weak_against: list[str] = field(default_factory=list)
    skill_priority: list[LolalyticsAsset] = field(default_factory=list)
    skill_order: list[LolalyticsSkillOrderRow] = field(default_factory=list)
    skill_order_win_rate: float | None = None
    skill_order_games: int | None = None
    summoner_spells: list[LolalyticsAsset] = field(default_factory=list)
    primary_runes: list[LolalyticsAsset] = field(default_factory=list)
    secondary_runes: list[LolalyticsAsset] = field(default_factory=list)
    starting_items: LolalyticsBuildSection | None = None
    core_build: LolalyticsBuildSection | None = None
    item_four: list[LolalyticsBuildSection] = field(default_factory=list)
    item_five: list[LolalyticsBuildSection] = field(default_factory=list)
    item_six: list[LolalyticsBuildSection] = field(default_factory=list)
    best_matchups: list[LolalyticsMatchup] = field(default_factory=list)
    worst_matchups: list[LolalyticsMatchup] = field(default_factory=list)
    build_url: str | None = None
    counters_url: str | None = None
