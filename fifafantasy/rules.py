"""Pure squad/lineup rule validation — no I/O, no network.

All checks run locally against the bulk player feed so invalid asks never reach
the API. Rules confirmed empirically from a live valid squad:
  squad 2GK/5DEF/5MID/3FWD = 15, budget £100m, max 3 players per nation,
  starting XI of 11 with exactly 1 GK and a legal outfield shape.
"""

from __future__ import annotations

from collections import Counter

from . import config

_POS_ORDER = ("GK", "DEF", "MID", "FWD")


def lineup_ids(lineup: dict) -> list[int]:
    return [pid for pos in _POS_ORDER for pid in (lineup.get(pos) or [])]


def bench_ids(bench: dict) -> list[int]:
    return [pid for pos in _POS_ORDER for pid in (bench.get(pos) or [])]


def squad_ids(team: dict) -> list[int]:
    return lineup_ids(team.get("lineup") or {}) + bench_ids(team.get("bench") or {})


def formation_str(lineup: dict) -> str:
    """e.g. '4-4-2' (DEF-MID-FWD)."""
    return "-".join(str(len(lineup.get(p) or [])) for p in ("DEF", "MID", "FWD"))


def validate_lineup(lineup: dict) -> list[str]:
    """Return a list of rule violations for a proposed starting XI ({} = legal)."""
    errs = []
    counts = {p: len(lineup.get(p) or []) for p in _POS_ORDER}
    total = sum(counts.values())
    if total != config.STARTING_SIZE:
        errs.append(f"starting XI has {total} players, must be {config.STARTING_SIZE}")
    for pos, (lo, hi) in config.FORMATION_LIMITS.items():
        if not (lo <= counts[pos] <= hi):
            errs.append(f"{pos}: {counts[pos]} in XI, must be {lo}-{hi}")
    return errs


def validate_squad(players: list) -> list[str]:
    """Return rule violations for a full 15-player squad ({} = legal).

    `players` is a list of Player objects (need .position, .squadId, .price).
    """
    errs = []
    if len(players) != config.SQUAD_SIZE:
        errs.append(f"squad has {len(players)} players, must be {config.SQUAD_SIZE}")
    by_pos = Counter(p.position for p in players)
    for pos, need in config.SQUAD_COMPOSITION.items():
        if by_pos.get(pos, 0) != need:
            errs.append(f"{pos}: {by_pos.get(pos, 0)} in squad, must be {need}")
    cost = sum(p.price for p in players)
    if cost > config.BUDGET + 1e-9:
        errs.append(f"squad costs £{cost:.1f}m, over the £{config.BUDGET:.0f}m budget")
    by_nation = Counter(p.squadId for p in players)
    over = [sq for sq, n in by_nation.items() if n > config.MAX_PER_SQUAD]
    for sq in over:
        errs.append(f"{by_nation[sq]} players from nation {sq}, max {config.MAX_PER_SQUAD}")
    return errs


def squad_summary(players: list) -> dict:
    """Structured snapshot used by `fifa team validate --json`."""
    return {
        "size": len(players),
        "byPosition": dict(Counter(p.position for p in players)),
        "value": round(sum(p.price for p in players), 1),
        "budget": config.BUDGET,
        "byNation": dict(Counter(p.squadId for p in players)),
    }
