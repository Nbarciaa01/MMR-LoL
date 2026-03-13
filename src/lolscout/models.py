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
    role: str = "UNKNOWN"
    game: LiveGameSummary | None = None
    status_text: str = ""
    spectate_url: str | None = None
    spectator: SpectatorSession | None = None
    participants: list[LiveGamePlayerDetails] = field(default_factory=list)
