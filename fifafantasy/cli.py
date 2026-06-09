"""Entry point: wires command groups into the `fifa` CLI."""

from __future__ import annotations

import typer
from rich.panel import Panel

from . import __version__, data, output
from .commands import account, fixtures, manage, players
from .render import console

app = typer.Typer(
    name="fifa",
    help="A rich terminal CLI for FIFA World Cup Fantasy.",
    no_args_is_help=True,
    add_completion=True,
)


@app.callback()
def main(
    json_out: bool = typer.Option(
        False, "--json", help="Emit machine-readable JSON (for agents/scripts)."
    ),
):
    """Global options. Put --json before the command: `fifa --json team`."""
    output.set_json(json_out)


# Read-only groups
app.add_typer(players.app, name="players")
# fixtures module exposes several top-level commands — mount them directly
app.command("fixtures")(fixtures.fixtures)
app.command("rounds")(fixtures.rounds)
app.command("deadlines")(fixtures.deadlines)
app.command("squads")(fixtures.squads)

# Authenticated read commands
app.command("login")(account.login)
app.command("logout")(account.logout)
app.command("whoami")(account.whoami)
app.command("leagues")(account.leagues)
app.command("rank")(account.rank)

# Team management (view + writes), transfers, chips
app.add_typer(manage.team_app, name="team")
app.add_typer(manage.transfers_app, name="transfers")
app.add_typer(manage.chips_app, name="chips")


@app.command()
def version():
    """Show version."""
    output.emit({"version": __version__},
                lambda: f"fifa-fantasy-cli [bold]{__version__}[/]")


@app.command()
def refresh():
    """Force-refresh cached public feeds (players, squads, rounds)."""
    data.load_players(refresh=True)
    data.load_squads(refresh=True)
    data.load_rounds(refresh=True)
    output.emit({"refreshed": ["players", "squads", "rounds"]},
                lambda: "[green]✓ Caches refreshed.[/]")


@app.command()
def status():
    """Quick overview: player/squad/round counts and next deadline."""
    players_ = data.load_players()
    squads_ = data.load_squads()
    rounds_ = data.load_rounds()
    nxt = next((r for r in rounds_ if r.status != "complete"), None)
    result = {
        "players": len(players_), "squads": len(squads_), "rounds": len(rounds_),
        "nextRound": ({"id": nxt.id, "stage": nxt.stage, "startDate": nxt.startDate}
                      if nxt else None),
    }

    def render():
        body = (f"Players: [bold]{len(players_)}[/]   "
                f"Squads: [bold]{len(squads_)}[/]   "
                f"Rounds: [bold]{len(rounds_)}[/]\n")
        if nxt:
            body += (f"Next round: [bold]{nxt.id}[/] ({nxt.stage}) — "
                     f"starts {nxt.startDate[:16].replace('T', ' ')}")
        return Panel(body, title="FIFA World Cup Fantasy", border_style="blue")

    output.emit(result, render)


if __name__ == "__main__":
    app()
