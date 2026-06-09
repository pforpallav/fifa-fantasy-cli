"""Fixtures, rounds, squads, and deadline commands."""

from __future__ import annotations

from typing import Optional

import typer
from dateutil import parser as dateparser
from rich.table import Table

from .. import data, output
from ..render import console, fmt_dt

app = typer.Typer(help="Fixtures, rounds, squads and deadlines.")


def _fixture_table(fixtures, title: str) -> Table:
    t = Table(title=title, header_style="bold white on blue")
    t.add_column("Kickoff")
    t.add_column("Home", justify="right")
    t.add_column("", justify="center")
    t.add_column("Away")
    t.add_column("Venue", style="dim")
    t.add_column("Status", justify="center", style="dim")
    for fx in fixtures:
        if fx.homeScore is not None and fx.awayScore is not None:
            score = f"[bold]{fx.homeScore}-{fx.awayScore}[/]"
        else:
            score = "vs"
        venue = " · ".join(x for x in (fx.venueName, fx.venueCity) if x)
        t.add_row(
            fmt_dt(fx.date),
            f"{fx.homeSquadName or '?'} ({fx.homeSquadAbbr or ''})",
            score,
            f"({fx.awaySquadAbbr or ''}) {fx.awaySquadName or '?'}",
            venue or "-",
            fx.status or "-",
        )
    return t


@app.command("fixtures")
def fixtures(
    round_id: Optional[int] = typer.Option(None, "--round", "-r", help="Round/matchday id"),
    live: bool = typer.Option(False, help="Only live matches"),
):
    """Show fixtures for a round (default: next scheduled round)."""
    rounds = data.load_rounds()
    if round_id is None:
        # pick the earliest non-complete round
        target = next((r for r in rounds if r.status != "complete"), rounds[0])
    else:
        target = next((r for r in rounds if r.id == round_id), None)
        if not target:
            console.print(f"[red]No round {round_id}[/]")
            raise typer.Exit(1)
    fx = target.tournaments
    if live:
        fx = [f for f in fx if (f.period or "") not in ("pre_match", "complete", None)]
    title = f"Round {target.id} · {target.stage or ''} · {target.status}"
    output.emit(
        {"round": target.id, "stage": target.stage, "status": target.status,
         "fixtures": [f.model_dump() for f in fx]},
        lambda: _fixture_table(fx, title),
    )


@app.command("rounds")
def rounds():
    """Overview of all rounds with their windows and deadlines."""
    rs = data.load_rounds()

    def render():
        t = Table(title="Rounds / Matchdays", header_style="bold white on blue")
        t.add_column("Round", justify="right")
        t.add_column("Stage")
        t.add_column("Status")
        t.add_column("Deadline (start)")
        t.add_column("Ends")
        t.add_column("Fixtures", justify="right")
        for r in rs:
            t.add_row(str(r.id), r.stage or "-", r.status,
                      fmt_dt(r.startDate), fmt_dt(r.endDate), str(len(r.tournaments)))
        return t

    output.emit(
        [{"id": r.id, "stage": r.stage, "status": r.status,
          "startDate": r.startDate, "endDate": r.endDate, "fixtures": len(r.tournaments)}
         for r in rs],
        render,
    )


@app.command("deadlines")
def deadlines():
    """Next transfer deadline (round start) vs current server time."""
    rounds = data.load_rounds()
    now_iso = data.server_time()
    now = dateparser.parse(now_iso) if now_iso else None
    nxt = None
    for r in rounds:
        start = dateparser.parse(r.startDate)
        if now is None or start > now:
            nxt = (r, start)
            break

    result = {"serverTime": now_iso, "next": None}
    if nxt:
        r, start = nxt
        delta = (start - now) if now else None
        result["next"] = {
            "round": r.id, "stage": r.stage, "deadline": r.startDate,
            "daysAway": delta.days if delta else None,
            "hoursAway": (delta.seconds // 3600) if delta else None,
        }

    def render():
        from rich.console import Group
        lines = [f"[dim]Server time:[/] {fmt_dt(now_iso, '%a %d %b %Y %H:%M %Z')}"]
        if nxt:
            r, start = nxt
            delta = (start - now) if now else None
            extra = f"  ([bold]{delta.days}d {delta.seconds//3600}h[/] away)" if delta else ""
            lines.append(f"[bold]Next deadline:[/] Round {r.id} ({r.stage}) — "
                         f"{fmt_dt(r.startDate, '%a %d %b %Y %H:%M')}{extra}")
        else:
            lines.append("[yellow]No upcoming deadlines (tournament may be complete).[/]")
        return Group(*lines)

    output.emit(result, render)


@app.command("squads")
def squads(group: Optional[str] = typer.Option(None, help="Filter by group letter")):
    """List the 48 national teams."""
    t = Table(title="Squads", header_style="bold white on blue")
    t.add_column("Id", justify="right", style="dim")
    t.add_column("Team")
    t.add_column("Abbr")
    t.add_column("Group", justify="center")
    t.add_column("Status")
    rows = data.load_squads()
    if group:
        rows = [s for s in rows if (s.group or "").lower() == group.lower()]
    rows.sort(key=lambda s: ((s.group or "z"), s.name))

    def render():
        for s in rows:
            status = "[red]eliminated[/]" if s.isEliminated else "[green]active[/]"
            t.add_row(str(s.id), s.name, s.abbr, (s.group or "-").upper(), status)
        return t

    output.emit([s.model_dump() for s in rows], render)
