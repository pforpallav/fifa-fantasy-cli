"""Player browsing, search, value & differential analytics."""

from __future__ import annotations

from typing import Optional

import typer
from rich.panel import Panel

from .. import data, output
from ..render import console, fmt_dt, player_table, pos_label

app = typer.Typer(help="Browse, search and analyse players.")

VALID_POS = {"GK", "DEF", "MID", "FWD"}


def _pdict(p, sm) -> dict:
    sq = sm.get(p.squadId)
    return {
        "id": p.id, "name": p.name, "pos": p.position,
        "team": sq.abbr if sq else None, "teamId": p.squadId,
        "price": p.price, "points": p.stats.totalPoints, "form": p.stats.form,
        "selectedBy": p.percentSelected, "ppm": p.ppm, "status": p.status,
        "oneToWatch": p.oneToWatch,
    }


def _filter_sort(players, pos, squad, max_price, min_price, sort, only_available):
    sm = data.squad_map()
    if pos:
        pos = pos.upper()
        players = [p for p in players if p.position == pos]
    if squad:
        sq = data.squad_by_abbr(squad)
        if sq:
            players = [p for p in players if p.squadId == sq.id]
    if max_price is not None:
        players = [p for p in players if p.price <= max_price]
    if min_price is not None:
        players = [p for p in players if p.price >= min_price]
    if only_available:
        players = [p for p in players if p.status == "playing"]
    keys = {
        "points": lambda p: -p.stats.totalPoints,
        "form": lambda p: -p.stats.form,
        "price": lambda p: -p.price,
        "value": lambda p: -p.ppm,
        "selected": lambda p: -p.percentSelected,
        "name": lambda p: p.name.lower(),
    }
    players.sort(key=keys.get(sort, keys["points"]))
    return players, sm


@app.command("list")
def list_players(
    pos: Optional[str] = typer.Option(None, help="GK | DEF | MID | FWD"),
    squad: Optional[str] = typer.Option(None, help="Team abbr or name, e.g. BRA"),
    max_price: Optional[float] = typer.Option(None, "--max-price"),
    min_price: Optional[float] = typer.Option(None, "--min-price"),
    sort: str = typer.Option("points", help="points|form|price|value|selected|name"),
    limit: int = typer.Option(25, help="Rows to show"),
    only_available: bool = typer.Option(True, help="Hide transferred-out players"),
):
    """List players with filters and sorting."""
    players = data.load_players()
    players, sm = _filter_sort(players, pos, squad, max_price, min_price, sort, only_available)
    show_value = sort == "value"
    rows = players[:limit]
    output.emit([_pdict(p, sm) for p in rows],
                lambda: player_table(rows, sm, title=f"Players · sort={sort}", show_value=show_value))


@app.command("show")
def show_player(player: str = typer.Argument(..., help="Player id or name")):
    """Show detailed info for one player (by id or name)."""
    try:
        p = data.resolve_player(player)
    except data.AmbiguousPlayer as e:
        output.fail(str(e), candidates=[{"id": c.id, "name": c.name} for c in e.candidates])
    except data.PlayerNotFound as e:
        output.fail(str(e))
    sm = data.squad_map()
    sq = sm.get(p.squadId)
    if output.is_json():
        output.emit(_pdict(p, sm))
        return
    body = (
        f"[bold]{p.name}[/]   {pos_label(p.position)}\n"
        f"Team: {sq.name if sq else p.squadId}  ·  Price: £{p.price:.1f}m\n"
        f"Selected by: {p.percentSelected:g}%   ·   Status: {p.status}\n\n"
        f"Total points: [bold]{p.stats.totalPoints:g}[/]   Form: {p.stats.form:g}   "
        f"Last round: {p.stats.lastRoundPoints:g}\n"
        f"Avg points: {p.stats.avgPoints:g}   ·   Value (PPM): [green]{p.ppm:g}[/]"
    )
    if p.oneToWatch:
        body += "\n\n[yellow]★ One to watch[/]"
    console.print(Panel(body, title=f"#{p.id}", border_style="blue"))


@app.command("search")
def search(query: str, limit: int = 15):
    """Search players by name."""
    q = query.lower()
    players = [p for p in data.load_players() if q in p.name.lower()]
    players.sort(key=lambda p: -p.stats.totalPoints)
    sm = data.squad_map()
    rows = players[:limit]
    output.emit([_pdict(p, sm) for p in rows],
                lambda: player_table(rows, sm, title=f"Search: {query}"))


@app.command("value")
def value(
    pos: Optional[str] = typer.Option(None, help="Restrict to a position"),
    top: int = typer.Option(20, help="Top N by points-per-million"),
):
    """Best value picks (points per £m)."""
    players = [p for p in data.load_players() if p.status == "playing" and p.price > 0]
    if pos:
        players = [p for p in players if p.position == pos.upper()]
    players.sort(key=lambda p: -p.ppm)
    sm = data.squad_map()
    rows = players[:top]
    output.emit([_pdict(p, sm) for p in rows],
                lambda: player_table(rows, sm, title="Best value (PPM)", show_value=True))


@app.command("differentials")
def differentials(
    max_owned: float = typer.Option(5.0, "--max-owned", help="Max ownership %"),
    min_form: float = typer.Option(0.0, "--min-form", help="Min form"),
    top: int = typer.Option(20),
):
    """Low-ownership, in-form differential picks."""
    players = [
        p for p in data.load_players()
        if p.status == "playing"
        and p.percentSelected <= max_owned
        and p.stats.form >= min_form
    ]
    players.sort(key=lambda p: (-p.stats.form, -p.stats.totalPoints))
    sm = data.squad_map()
    rows = players[:top]
    output.emit([_pdict(p, sm) for p in rows],
                lambda: player_table(rows, sm, title=f"Differentials (<= {max_owned:g}% owned)"))
