"""League commands: list your leagues, view standings, members, and squads.

  fifa leagues                       # leagues you belong to (default)
  fifa leagues standings <id>        # the league table
  fifa leagues members <id>          # who's in it
  fifa leagues squad <id> <member>   # a member's squad as a formation
"""

from __future__ import annotations

import typer
from rich.table import Table

from .. import config, data, output, rules
from ..render import league_standings_table, leagues_table, team_pitch
from .account import _authed_get

leagues_app = typer.Typer(help="Your leagues: standings, members and squads.",
                          invoke_without_command=True)


@leagues_app.callback(invoke_without_command=True)
def leagues_main(ctx: typer.Context):
    """List the leagues you belong to (default)."""
    if ctx.invoked_subcommand is not None:
        return
    rows = _authed_get(config.URL_LEAGUES).get("leagues") or []
    output.emit({"leagues": rows},
                lambda: leagues_table(rows) if rows else "[yellow]You're not in any leagues yet.[/]")


@leagues_app.command("standings")
def standings(league_id: int = typer.Argument(..., help="League id (from `fifa leagues`)")):
    """Show a league's standings table."""
    ranks = _authed_get(config.URL_LEAGUE_STANDINGS.format(lid=league_id)).get("ranks") or []
    output.emit({"leagueId": league_id, "ranks": ranks},
                lambda: league_standings_table(ranks, title=f"League #{league_id}") if ranks
                else "[yellow]No standings yet for this league.[/]")


@leagues_app.command("members")
def members(league_id: int = typer.Argument(..., help="League id")):
    """List a league's members."""
    users = _authed_get(config.URL_LEAGUE_USERS.format(lid=league_id)).get("users") or []

    def render():
        t = Table(title=f"League #{league_id} · members", header_style="bold white on blue")
        t.add_column("Manager", style="bold")
        t.add_column("User ID", justify="right", style="dim")
        for u in users:
            t.add_row(u.get("userName", "-"), str(u.get("userId", "")))
        return t

    output.emit({"leagueId": league_id, "users": users}, render)


@leagues_app.command("squad")
def squad(
    league_id: int = typer.Argument(..., help="League id"),
    member: str = typer.Argument(..., help="Member username or userId"),
):
    """Show a league member's squad as a formation."""
    q = member.strip()
    if q.isdigit():
        uid, uname = int(q), f"#{q}"
    else:
        users = _authed_get(config.URL_LEAGUE_USERS.format(lid=league_id)).get("users") or []
        uid, uname = _resolve_member(q, users)

    team = _authed_get(config.URL_MEMBER_TEAM.format(uid=uid))
    if not team.get("lineup"):
        output.fail(f"No squad found for {uname}.", code=output.EXIT_ERROR)

    players, squads = data.player_map(), data.squad_map()
    if output.is_json():
        sq = [players[i] for i in rules.squad_ids(team) if i in players]
        output.emit({
            "leagueId": league_id, "userId": uid, "userName": uname,
            "formation": rules.formation_str(team["lineup"]),
            "captain": team.get("captain"), "vice": team.get("vice"),
            "players": [{"id": p.id, "name": p.name, "pos": p.position,
                         "team": (squads.get(p.squadId).abbr if squads.get(p.squadId) else None),
                         "price": p.price} for p in sq],
        })
    else:
        output.emit(None, lambda: team_pitch(team, players, squads, owner=uname))


def _resolve_member(query: str, users: list):
    """Map a username (substring, case-insensitive) to (userId, userName)."""
    ql = query.lower()
    matches = [u for u in users if ql in (u.get("userName") or "").lower()]
    if len(matches) == 1:
        return matches[0]["userId"], matches[0]["userName"]
    if not matches:
        output.fail(f"No member matching '{query}' in this league.", code=output.EXIT_ERROR,
                    members=[u.get("userName") for u in users])
    output.fail(f"'{query}' matches multiple members.", code=output.EXIT_ERROR,
                candidates=[u.get("userName") for u in matches])
