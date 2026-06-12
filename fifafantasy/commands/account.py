"""Authenticated commands: login, team, league, rank. Pure terminal — no browser."""

from __future__ import annotations

from typing import Optional

import typer

from .. import auth, config, data, output
from ..client import AuthError, FifaClient, FifaError
from ..render import console, ranking_table, user_panel

app = typer.Typer(help="Account, team, leagues and ranking (requires login).")


@app.command("login")
def login(
    email: Optional[str] = typer.Option(None, "--email", "-e", help="FIFA ID email"),
    cookie: Optional[str] = typer.Option(
        None, "--cookie",
        help="Paste a 'name=value; ...' session cookie from DevTools (no browser needed)",
    ),
    from_browser: Optional[str] = typer.Option(
        None, "--from-browser", "-b",
        help="Import the session from a logged-in local browser: "
             "chrome|chromium|brave|edge|firefox|opera|safari",
    ),
):
    """Log in. Best path: --from-browser to import an existing browser session.

    FIFA login is a browser SSO flow behind bot protection, so headless
    credential login does not work. Recommended:

      fifa login --from-browser chrome   # auto-import from a logged-in browser

    Or paste cookies yourself (DevTools → Application → Cookies → play.fifa.com):

      fifa login --cookie 'name=value; name2=value2'
    """
    try:
        if from_browser:
            user = auth.login_from_browser(from_browser)
        elif cookie:
            user = auth.login_cookie(cookie)
        else:
            if not email:
                email = typer.prompt("FIFA ID email")
            password = typer.prompt("Password", hide_input=True)
            user = auth.login_sso(email, password)
    except AuthError as e:
        console.print(f"[red]Login failed:[/] {e}")
        console.print(
            "[dim]Tip: SSO may require MFA/CAPTCHA. Use the cookie route instead:\n"
            "  fifa login --cookie 'name=value; name2=value2'[/]"
        )
        raise typer.Exit(1)
    except FifaError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)
    name = (user or {}).get("success", user) if isinstance(user, dict) else user
    console.print("[green]✓ Logged in.[/] Session stored.")


@app.command("logout")
def logout():
    """Clear the local session."""
    auth.logout()
    console.print("[green]✓ Logged out.[/]")


@app.command("whoami")
def whoami():
    """Show the current logged-in user."""
    user = auth.whoami()
    if not user:
        output.fail("Not logged in. Run `fifa login`.", code=output.EXIT_AUTH)
    u = ((user or {}).get("success") or {}).get("user") or user
    output.emit(u, lambda: user_panel(user))


def _authed_get(url: str):
    """GET an authed endpoint, mapping errors to structured exits."""
    client = FifaClient()
    try:
        return (client.get_json(url, auth=True) or {}).get("success") or {}
    except AuthError as e:
        output.fail(str(e), code=output.EXIT_AUTH)
    except FifaError as e:
        output.fail(str(e), code=output.EXIT_ERROR)
    finally:
        client.close()


@app.command("rank")
def rank():
    """Show the overall ranking leaderboard."""
    ranks = _authed_get(config.URL_RANKING).get("ranks") or []
    output.emit({"ranks": ranks},
                lambda: ranking_table(ranks) if ranks
                else "[yellow]No ranking data yet[/] — populates once matches begin.")
