"""Public-feed loaders with disk caching + ID lookup helpers."""

from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path

import httpx

from . import config
from .models import Player, Round, Squad


def _cache_path(name: str) -> Path:
    config.ensure_dirs()
    return config.CACHE_DIR / f"{name}.json"


def _fetch_cached(url: str, name: str, ttl: int = config.CACHE_TTL_SECONDS) -> list | dict:
    path = _cache_path(name)
    if path.exists() and (time.time() - path.stat().st_mtime) < ttl:
        return json.loads(path.read_text())
    resp = httpx.get(url, headers={"User-Agent": config.USER_AGENT}, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    path.write_text(json.dumps(data))
    return data


def load_players(refresh: bool = False) -> list[Player]:
    ttl = 0 if refresh else config.CACHE_TTL_SECONDS
    raw = _fetch_cached(config.URL_PLAYERS, "players", ttl)
    return [Player.model_validate(p) for p in raw]


def load_squads(refresh: bool = False) -> list[Squad]:
    ttl = 0 if refresh else 3600  # squads rarely change
    raw = _fetch_cached(config.URL_SQUADS, "squads", ttl)
    return [Squad.model_validate(s) for s in raw]


def load_rounds(refresh: bool = False) -> list[Round]:
    ttl = 0 if refresh else config.CACHE_TTL_SECONDS
    raw = _fetch_cached(config.URL_ROUNDS, "rounds", ttl)
    return [Round.model_validate(r) for r in raw]


def server_time() -> str:
    resp = httpx.get(config.URL_TIME, headers={"User-Agent": config.USER_AGENT}, timeout=15.0)
    resp.raise_for_status()
    return resp.json().get("time", "")


class PlayerNotFound(Exception):
    """No player matched the query."""


class AmbiguousPlayer(Exception):
    """Multiple players matched the query."""

    def __init__(self, query: str, candidates: list):
        self.query = query
        self.candidates = candidates
        names = ", ".join(f"{p.name} (#{p.id})" for p in candidates[:8])
        super().__init__(f"'{query}' matches {len(candidates)} players: {names}")


# --- lookups ---
def player_map() -> dict[int, Player]:
    return {p.id: p for p in load_players()}


def resolve_player(query) -> Player:
    """Resolve an ID or (fuzzy) name to a single Player.

    Raises PlayerNotFound / AmbiguousPlayer so callers can report cleanly.
    """
    players = load_players()
    q = str(query).strip()
    if q.isdigit():
        pid = int(q)
        for p in players:
            if p.id == pid:
                return p
        raise PlayerNotFound(f"no player with id {pid}")

    ql = q.lower()
    exact = [p for p in players if p.name.lower() == ql
             or (p.lastName or "").lower() == ql or (p.knownName or "").lower() == ql]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise AmbiguousPlayer(q, exact)

    subs = [p for p in players if ql in p.name.lower()]
    if len(subs) == 1:
        return subs[0]
    if len(subs) > 1:
        raise AmbiguousPlayer(q, subs)
    raise PlayerNotFound(f"no player matching '{q}'")


def squad_map() -> dict[int, Squad]:
    return {s.id: s for s in load_squads()}


def squad_by_abbr(abbr: str) -> Squad | None:
    abbr = abbr.upper()
    for s in load_squads():
        if s.abbr.upper() == abbr or s.name.upper() == abbr:
            return s
    return None
