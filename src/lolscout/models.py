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
class PlayerSummary:
    game_name: str
    tag_line: str
    summoner_level: int
    profile_icon_id: int
    platform: str
    soloq: RankedEntry | None = None
    flex: RankedEntry | None = None
    estimated_mmr: int | None = None
    global_winrate: float | None = None
    ranked_games: int | None = None
    recent_winrate: float = 0.0
    matches: list[MatchSummary] = field(default_factory=list)
    ranked_available: bool = True
