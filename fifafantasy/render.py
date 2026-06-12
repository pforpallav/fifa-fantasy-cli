"""Shared rich rendering helpers."""

from __future__ import annotations

from datetime import datetime

from dateutil import parser as dateparser
from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from . import config

console = Console()

POSITION_STYLE = {
    "GK": "yellow",
    "DEF": "cyan",
    "MID": "green",
    "FWD": "magenta",
}


def pos_label(pos: str) -> str:
    return f"[{POSITION_STYLE.get(pos, 'white')}]{pos}[/]"


def fmt_dt(iso: str | None, fmt: str = "%a %d %b %H:%M") -> str:
    if not iso:
        return "-"
    try:
        return dateparser.parse(iso).strftime(fmt)
    except (ValueError, TypeError):
        return iso


def player_table(players, squads: dict, *, title: str = "Players", show_value: bool = False) -> Table:
    t = Table(title=title, header_style="bold white on blue", expand=False)
    t.add_column("#", justify="right", style="dim")
    t.add_column("Player", style="bold")
    t.add_column("Team")
    t.add_column("Pos", justify="center")
    t.add_column("£m", justify="right")
    t.add_column("Pts", justify="right")
    t.add_column("Form", justify="right")
    t.add_column("Sel%", justify="right", style="dim")
    if show_value:
        t.add_column("PPM", justify="right", style="bold green")
    for p in players:
        sq = squads.get(p.squadId)
        row = [
            str(p.id),
            p.name,
            sq.abbr if sq else str(p.squadId),
            pos_label(p.position),
            f"{p.price:.1f}",
            f"{p.stats.totalPoints:g}",
            f"{p.stats.form:g}",
            f"{p.percentSelected:g}",
        ]
        if show_value:
            row.append(f"{p.ppm:g}")
        t.add_row(*row)
    return t


_POS_ORDER = ("GK", "DEF", "MID", "FWD")


def _num(v) -> str:
    """Render a possibly-null numeric field (rankings are null pre-tournament)."""
    return "-" if v is None else f"{v:g}" if isinstance(v, (int, float)) else str(v)


def team_view(team: dict, players: dict, squads: dict):
    """Resolve a team payload (bare player IDs) into a readable squad view.

    `players` / `squads` are id->object maps loaded once from the bulk public
    feeds — no per-player network calls.
    """
    lineup = team.get("lineup") or {}
    bench = team.get("bench") or {}
    captain, vice = team.get("captain"), team.get("vice")

    def row_for(pid: int):
        p = players.get(pid)
        if not p:
            return (f"[dim]?[/]", f"[dim]Player {pid}[/]", "[dim]?[/]", "-", "")
        sq = squads.get(p.squadId)
        tag = "[bold yellow]C[/]" if pid == captain else "[cyan]V[/]" if pid == vice else ""
        return (pos_label(p.position), p.name, sq.abbr if sq else str(p.squadId),
                f"{p.price:.1f}", tag)

    def make_table(ids):
        t = Table(box=box.SIMPLE_HEAD, expand=False, pad_edge=False)
        t.add_column("Pos", justify="center")
        t.add_column("Player", style="bold")
        t.add_column("Team")
        t.add_column("£m", justify="right")
        t.add_column("", justify="center")  # captain/vice marker
        for pid in ids:
            t.add_row(*row_for(pid))
        return t

    start_ids = [pid for pos in _POS_ORDER for pid in lineup.get(pos, [])]
    bench_ids = team.get("benchOrder") or [pid for pos in _POS_ORDER for pid in bench.get(pos, [])]

    formation = "-".join(str(len(lineup.get(p, []))) for p in ("DEF", "MID", "FWD"))
    value = sum(players[i].price for i in (start_ids + bench_ids) if i in players)
    cap_name = players[captain].name if captain in players else "-"
    vice_name = players[vice].name if vice in players else "-"

    chip_fields = [("wildCard", "Wildcard"), ("twelfthMan", "12th Man"),
                   ("maxCaptain", "Max Captain"), ("cleanSheet", "Clean Sheet"),
                   ("qualification", "Qualification")]
    used = [label for key, label in chip_fields if team.get(key)]
    ft = team.get("freeTransfers")

    summary = (
        f"Formation [bold]{formation}[/]   ·   Squad value [bold]£{value:.1f}m[/]\n"
        f"Captain [bold yellow]{cap_name}[/]   ·   Vice [cyan]{vice_name}[/]\n"
        f"Free transfers: {_num(ft)}   ·   Chips used: {', '.join(used) or 'none'}"
    )

    body = Group(
        make_table(start_ids),
        "[dim]── Bench ──[/]",
        make_table(bench_ids),
        "",
        summary,
    )
    return Panel(body, title=f"My Team · #{team.get('id')}", border_style="green")


_PITCH_WIDTH = 70
_CHIP_WIDTH = 15
_ICON = "◉"  # simple, single-width player token


def _short_name(p) -> str:
    """Jersey-style short name for a pitch chip."""
    name = getattr(p, "knownName", None) or getattr(p, "lastName", None) or p.name
    return name if len(name) <= _CHIP_WIDTH else name[:_CHIP_WIDTH - 1] + "…"


def _chip(p, squads: dict, captain, vice) -> str:
    """A uniform three-line player token: icon / name / 'TEAM £price' (+ C·V badge)."""
    sq = squads.get(p.squadId)
    abbr = sq.abbr if sq else str(p.squadId)
    color = POSITION_STYLE.get(p.position, "white")
    if p.id == captain:
        icon_color, badge = "yellow", " [bold yellow](C)[/]"
    elif p.id == vice:
        icon_color, badge = "cyan", " [bold cyan](V)[/]"
    else:
        icon_color, badge = color, ""
    return (f"[{icon_color}]{_ICON}[/]\n"
            f"[bold {color}]{_short_name(p)}[/]\n"
            f"[dim]{abbr} £{p.price:.1f}[/]{badge}")


def _pitch_row(ids, players: dict, squads: dict, captain, vice):
    """A horizontally-centered row of fixed-width player chips."""
    cells = []
    for pid in ids:
        p = players.get(pid)
        cells.append(_chip(p, squads, captain, vice) if p
                     else f"[dim]{_ICON}[/]\n[dim]Player {pid}[/]\n[dim]?[/]")
    t = Table(box=None, show_header=False, show_edge=False, pad_edge=False, padding=(0, 1))
    for _ in cells:
        t.add_column(justify="center", width=_CHIP_WIDTH, no_wrap=True, overflow="ellipsis")
    t.add_row(*cells)
    return Align.center(t)


def team_pitch(team: dict, players: dict, squads: dict, owner: str | None = None):
    """Render the squad as a formation: one uniform panel — pitch, bench, summary.

    Everything lives in a single fixed-width panel so the rows, dividers and the
    summary all align. IDs are resolved from the passed-in feeds — no extra calls.
    `owner` titles the panel for someone else's team (default: "My Team").
    """
    lineup = team.get("lineup") or {}
    bench = team.get("bench") or {}
    captain, vice = team.get("captain"), team.get("vice")
    bench_ids = team.get("benchOrder") or [pid for pos in _POS_ORDER for pid in bench.get(pos, [])]
    start_ids = [pid for pos in _POS_ORDER for pid in lineup.get(pos, [])]

    body = []
    for pos in _POS_ORDER:  # GK at the top, FWD at the bottom (FPL-style pitch)
        ids = lineup.get(pos, [])
        if ids:
            if body:
                body.append("")  # even spacing between lines of the pitch
            body.append(_pitch_row(ids, players, squads, captain, vice))
    body.append(Rule("Bench", style="green dim"))
    body.append(_pitch_row(bench_ids, players, squads, captain, vice))

    formation = "-".join(str(len(lineup.get(p, []))) for p in ("DEF", "MID", "FWD"))
    value = sum(players[i].price for i in (start_ids + bench_ids) if i in players)
    cap_name = players[captain].name if captain in players else "-"
    vice_name = players[vice].name if vice in players else "-"
    chip_fields = [("wildCard", "Wildcard"), ("twelfthMan", "12th Man"),
                   ("maxCaptain", "Max Captain"), ("cleanSheet", "Clean Sheet"),
                   ("qualification", "Qualification")]
    used = [label for key, label in chip_fields if team.get(key)]
    body.append(Rule(style="green dim"))
    body.append(Text.from_markup(
        f"Squad value [bold]£{value:.1f}m[/] / £{int(config.BUDGET)}m\n"
        f"[yellow]{_ICON}[/] (C) [bold]{cap_name}[/]       "
        f"[cyan]{_ICON}[/] (V) [bold]{vice_name}[/]\n"
        f"[dim]Free transfers: {_num(team.get('freeTransfers'))}   ·   "
        f"Chips used: {', '.join(used) or 'none'}[/]",
        justify="center",
    ))

    return Panel(Group(*body), title=f"⚽  {owner or 'My Team'} · {formation}",
                 border_style="green", width=_PITCH_WIDTH, padding=(1, 1))


def leagues_table(leagues: list) -> Table:
    t = Table(title="My Leagues", header_style="bold white on blue", expand=False)
    t.add_column("ID", justify="right", style="dim")
    t.add_column("League", style="bold")
    t.add_column("Members", justify="right")
    t.add_column("Privacy")
    t.add_column("Manager")
    t.add_column("Pts", justify="right")
    t.add_column("Rank", justify="right")
    for lg in leagues:
        mgr = (lg.get("leagueManager") or {}).get("userName", "-")
        t.add_row(
            str(lg.get("id", "")), lg.get("name", "-"), str(lg.get("numTeams", "-")),
            lg.get("privacy", "-"), mgr,
            _num(lg.get("overallPoints")), _num(lg.get("overallRank")),
        )
    return t


def ranking_table(ranks: list, me_id: int | None = None) -> Table:
    t = Table(title="Overall Ranking", header_style="bold white on blue", expand=False)
    t.add_column("Rank", justify="right")
    t.add_column("User", style="bold")
    t.add_column("Pts", justify="right")
    t.add_column("Lvl", justify="right", style="dim")
    for r in ranks:
        name = r.get("userName", "-")
        if me_id is not None and r.get("userId") == me_id:
            name = f"[bold green]{name} (you)[/]"
        t.add_row(_num(r.get("overallRank")), name,
                  _num(r.get("overallPoints")), str(r.get("level", "")))
    return t


def league_standings_table(ranks: list, title: str = "League", me_id: int | None = None) -> Table:
    t = Table(title=title, header_style="bold white on blue", expand=False)
    t.add_column("#", justify="right")
    t.add_column("Manager", style="bold")
    t.add_column("Round", justify="right")
    t.add_column("Total", justify="right")
    t.add_column("Lvl", justify="right", style="dim")
    for r in ranks:
        name = r.get("userName", "-")
        if me_id is not None and r.get("userId") == me_id:
            name = f"[bold green]{name} (you)[/]"
        t.add_row(_num(r.get("overallRank")), name,
                  _num(r.get("roundPoints")), _num(r.get("overallPoints")),
                  str(r.get("level", "")))
    return t


def user_panel(user: dict):
    u = ((user or {}).get("success") or {}).get("user") or user or {}
    rows = [
        ("Username", u.get("username", "-")),
        ("Email", u.get("email", "-")),
        ("Country", u.get("country", "-")),
        ("Member since", fmt_dt(u.get("createdAt"), "%d %b %Y")),
        ("User ID", str(u.get("id", "-"))),
    ]
    body = "\n".join(f"[dim]{k}:[/] {v}" for k, v in rows)
    return Panel(body, title="Current user", border_style="blue")
