"""Typed models for the public feeds (validated subset of the real schema)."""

from __future__ import annotations

from typing import Optional, Union

from pydantic import BaseModel, Field


class PlayerStats(BaseModel):
    totalPoints: float = 0
    avgPoints: float = 0
    form: float = 0
    lastRoundPoints: float = 0
    # Empty/[] before the tournament; becomes a {roundId: points} dict once
    # matches are played — accept either shape.
    roundPoints: Optional[Union[dict, list]] = None
    nextFixtureFromActiveRound: Optional[int] = None
    nextFixtureFromScheduledRound: Optional[int] = None


class Player(BaseModel):
    id: int
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    knownName: Optional[str] = None
    squadId: int
    position: str  # GK | DEF | MID | FWD
    price: float
    status: str  # playing | transferred
    percentSelected: float = 0
    oneToWatch: bool = False
    stats: PlayerStats = Field(default_factory=PlayerStats)

    @property
    def name(self) -> str:
        if self.knownName:
            return self.knownName
        parts = [p for p in (self.firstName, self.lastName) if p]
        return " ".join(parts) or f"Player {self.id}"

    @property
    def ppm(self) -> float:
        """Points per million — value metric."""
        return round(self.stats.totalPoints / self.price, 2) if self.price else 0.0


class Squad(BaseModel):
    id: int
    name: str
    group: Optional[str] = None
    abbr: str
    isEliminated: bool = False


class Fixture(BaseModel):
    id: int
    period: Optional[str] = None
    status: Optional[str] = None
    date: Optional[str] = None
    venueName: Optional[str] = None
    venueCity: Optional[str] = None
    homeSquadId: Optional[int] = None
    awaySquadId: Optional[int] = None
    homeSquadName: Optional[str] = None
    awaySquadName: Optional[str] = None
    homeSquadAbbr: Optional[str] = None
    awaySquadAbbr: Optional[str] = None
    homeScore: Optional[int] = None
    awayScore: Optional[int] = None


class Round(BaseModel):
    id: int
    status: str
    startDate: str
    endDate: str
    stage: Optional[str] = None
    tournaments: list[Fixture] = Field(default_factory=list)
