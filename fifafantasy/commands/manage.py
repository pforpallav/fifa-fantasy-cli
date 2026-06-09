"""Team management: view, swaps, captain/vice, transfers, chips, backup/restore.

Design for agents:
  * Every mutation is DRY-RUN by default — it computes + validates + reports the
    planned result without touching the network. Pass --commit to actually save.
  * All rule checks run locally (rules.py) so invalid asks never hit the API.
  * Inputs accept player IDs or (fuzzy) names.
  * The single network write lives in `_save_squad`; the squad-save route
    (POST /team {lineup,bench}) is confirmed. Captain/vice/transfer/chip writes
    use a route still pending a DevTools capture and are gated with a clear error.
"""

from __future__ import annotations

import copy
import json
from contextlib import contextmanager
from typing import Optional

import typer

from .. import config, data, output, rules
from ..client import AuthError, FifaClient, FifaError
from ..render import console, team_pitch, team_view

_POS = ("GK", "DEF", "MID", "FWD")

team_app = typer.Typer(help="Your squad: view, swaps, captain, validate, backup.",
                       invoke_without_command=True)
transfers_app = typer.Typer(help="Transfers: plan (dry-run) and make.")
chips_app = typer.Typer(help="Chips / boosters.")

CHIPS = {  # cli name -> save field
    "wildcard": "wildCard",
    "twelfth-man": "twelfthMan",
    "max-captain": "maxCaptain",
    "clean-sheet": "cleanSheet",
    "qualification": "qualification",
}


# ---------- network helpers ----------
@contextmanager
def _session():
    client = FifaClient()
    try:
        yield client
    finally:
        client.close()


def _get_team(client) -> dict:
    try:
        team = (client.get_json(config.URL_TEAM, auth=True) or {}).get("success") or {}
    except AuthError as e:
        raise output.fail(str(e), code=output.EXIT_AUTH)
    except FifaError as e:
        raise output.fail(str(e), code=output.EXIT_ERROR)
    if not team.get("lineup"):
        raise output.fail("No team found for this account yet.", code=output.EXIT_ERROR)
    return team


def _save_squad(client, lineup: dict, bench: dict) -> dict:
    """The one real write: POST /team {lineup, bench}. Maps known failures."""
    try:
        return client.post_json(
            config.URL_TEAM, json_body={"lineup": lineup, "bench": bench}, auth=True
        )
    except (AuthError, FifaError) as e:
        msg = str(e)
        if "second_team" in msg:
            raise output.fail(
                "Save rejected: in-season team edits aren't open via POST /team (it only "
                "creates a team, and one exists). This route needs a one-time DevTools "
                "capture — see README › Write operations.",
                code=output.EXIT_ERROR, serverMessage=msg)
        raise output.fail(f"Save failed: {msg}", code=output.EXIT_ERROR)


def _gated(action: str):
    raise output.fail(
        f"'{action}' uses a write route not yet confirmed. Capture it once from the browser "
        "(DevTools → Network → do the action → Copy as cURL) and share it; "
        "see README › Write operations.",
        code=output.EXIT_ERROR, pending=action)


# ---------- shared helpers ----------
def _resolve(query) -> "data.Player":
    try:
        return data.resolve_player(query)
    except data.AmbiguousPlayer as e:
        raise output.fail(str(e), code=output.EXIT_ERROR,
                          candidates=[{"id": p.id, "name": p.name} for p in e.candidates])
    except data.PlayerNotFound as e:
        raise output.fail(str(e), code=output.EXIT_ERROR)


def _locate(team: dict, pid: int):
    """Return ('lineup'|'bench', position) for a player id in the squad, else (None, None)."""
    for where in ("lineup", "bench"):
        for pos in _POS:
            if pid in (team.get(where, {}).get(pos) or []):
                return where, pos
    return None, None


def _emit_plan(action: str, detail: dict, team_after: dict, players: dict,
               squads: dict, committed: bool):
    sq = [players[i] for i in rules.squad_ids(team_after) if i in players]
    plan = {
        "action": action,
        **detail,
        "formation": rules.formation_str(team_after["lineup"]),
        "squadValue": round(sum(p.price for p in sq), 1),
        "captain": team_after.get("captain"),
        "vice": team_after.get("vice"),
        "committed": committed,
    }

    def render():
        from rich.console import Group
        tag = "[green]✓ committed[/]" if committed else "[yellow]dry-run[/] (use --commit to save)"
        head = f"{tag}  ·  {action}: {detail.get('summary', '')}"
        return Group(head, "", team_pitch(team_after, players, squads))

    output.emit(plan, render)


# ---------- view (default when `fifa team` has no subcommand) ----------
@team_app.callback(invoke_without_command=True)
def team_main(
    ctx: typer.Context,
    as_list: bool = typer.Option(False, "--list", "-l",
                                 help="Table view instead of the pitch formation"),
):
    """Show your squad as a formation on the pitch (or --list as a table)."""
    if ctx.invoked_subcommand is not None:
        return
    with _session() as client:
        team = _get_team(client)
    players = data.player_map()
    squads = data.squad_map()
    if output.is_json():
        sq = [players[i] for i in rules.squad_ids(team) if i in players]
        output.emit({
            "id": team.get("id"),
            "formation": rules.formation_str(team["lineup"]),
            "captain": team.get("captain"),
            "vice": team.get("vice"),
            "squadValue": round(sum(p.price for p in sq), 1),
            "lineup": team["lineup"],
            "bench": team.get("bench"),
            "benchOrder": team.get("benchOrder"),
            "players": [{"id": p.id, "name": p.name, "pos": p.position,
                         "team": (squads.get(p.squadId).abbr if squads.get(p.squadId) else None),
                         "price": p.price} for p in sq],
        })
    else:
        output.emit(None, lambda: (team_view if as_list else team_pitch)(team, players, squads))


# ---------- swap (lineup <-> bench) ----------
@team_app.command("swap")
def swap(
    out_player: str = typer.Argument(..., metavar="OUT", help="Player leaving the XI (id or name)"),
    in_player: str = typer.Argument(..., metavar="IN", help="Player entering the XI (id or name)"),
    commit: bool = typer.Option(False, "--commit", help="Actually save (default: dry-run)"),
):
    """Swap a starter for a bench player (keeps a legal formation)."""
    out_p, in_p = _resolve(out_player), _resolve(in_player)
    with _session() as client:
        team = _get_team(client)
        out_where, out_pos = _locate(team, out_p.id)
        in_where, in_pos = _locate(team, in_p.id)
        if out_where != "lineup":
            _ = output.fail(f"{out_p.name} is not in the starting XI.", code=output.EXIT_ERROR)
        if in_where != "bench":
            _ = output.fail(f"{in_p.name} is not on the bench.", code=output.EXIT_ERROR)

        after = copy.deepcopy(team)
        after["lineup"][out_pos].remove(out_p.id)
        after["lineup"][in_pos].append(in_p.id)
        after["bench"][in_pos].remove(in_p.id)
        after["bench"][out_pos].append(out_p.id)
        after["benchOrder"] = [out_p.id if x == in_p.id else x for x in (team.get("benchOrder") or [])]

        errs = rules.validate_lineup(after["lineup"])
        if errs:
            _ = output.fail("Illegal formation after swap.", code=output.EXIT_ERROR, violations=errs)

        committed = False
        if commit:
            _save_squad(client, after["lineup"], after["bench"])
            committed = True
    detail = {"out": {"id": out_p.id, "name": out_p.name},
              "in": {"id": in_p.id, "name": in_p.name},
              "summary": f"{out_p.name} → bench, {in_p.name} → XI"}
    _emit_plan("swap", detail, after, data.player_map(), data.squad_map(), committed)


# ---------- captain / vice ----------
def _set_armband(field: str, other: str, target_query: str, commit: bool, label: str):
    target = _resolve(target_query)
    with _session() as client:
        team = _get_team(client)
        if target.id not in rules.lineup_ids(team["lineup"]):
            _ = output.fail(f"{target.name} is not in the starting XI — can't be {label}.",
                            code=output.EXIT_ERROR)
        after = copy.deepcopy(team)
        # If target currently holds the other armband, swap them.
        if team.get(other) == target.id:
            after[other] = team.get(field)
        after[field] = target.id
        committed = False
        if commit:
            _gated(label)  # captain/vice route pending capture
            committed = True
    detail = {label: {"id": target.id, "name": target.name},
              "summary": f"{label} → {target.name}"}
    _emit_plan(label, detail, after, data.player_map(), data.squad_map(), committed)


@team_app.command("captain")
def captain(player: str = typer.Argument(..., help="New captain (id or name)"),
            commit: bool = typer.Option(False, "--commit")):
    """Set your captain (must be in the starting XI)."""
    _set_armband("captain", "vice", player, commit, "captain")


@team_app.command("vice")
def vice(player: str = typer.Argument(..., help="New vice-captain (id or name)"),
         commit: bool = typer.Option(False, "--commit")):
    """Set your vice-captain (must be in the starting XI)."""
    _set_armband("vice", "captain", player, commit, "vice")


# ---------- validate ----------
@team_app.command("validate")
def validate():
    """Check your current squad and formation against the game rules."""
    with _session() as client:
        team = _get_team(client)
    players = data.player_map()
    sq = [players[i] for i in rules.squad_ids(team) if i in players]
    squad_errs = rules.validate_squad(sq)
    lineup_errs = rules.validate_lineup(team["lineup"])
    violations = squad_errs + lineup_errs
    result = {"valid": not violations, "violations": violations,
              "summary": rules.squad_summary(sq),
              "formation": rules.formation_str(team["lineup"])}

    def render():
        from rich.panel import Panel
        if not violations:
            return Panel(f"[green]✓ Squad is legal[/]  ·  formation {result['formation']}  ·  "
                         f"value £{result['summary']['value']}m / £{config.BUDGET:.0f}m",
                         border_style="green", title="Validate")
        body = "\n".join(f"[red]•[/] {v}" for v in violations)
        return Panel(body, border_style="red", title="Rule violations")

    output.emit(result, render)


# ---------- backup / restore ----------
@team_app.command("backup")
def backup():
    """Snapshot your current team to disk (for instant rollback)."""
    with _session() as client:
        team = _get_team(client)
    config.ensure_dirs()
    config.BACKUP_FILE.write_text(json.dumps(team, indent=2))
    output.emit({"backedUp": True, "path": str(config.BACKUP_FILE),
                 "formation": rules.formation_str(team["lineup"])},
                lambda: f"[green]✓ Backed up[/] to {config.BACKUP_FILE}")


@team_app.command("restore")
def restore(commit: bool = typer.Option(False, "--commit", help="Actually save the backup")):
    """Restore the squad from the last backup (dry-run unless --commit)."""
    if not config.BACKUP_FILE.exists():
        _ = output.fail("No backup found. Run `fifa team backup` first.", code=output.EXIT_ERROR)
    saved = json.loads(config.BACKUP_FILE.read_text())
    committed = False
    with _session() as client:
        if commit:
            _save_squad(client, saved["lineup"], saved["bench"])
            committed = True
    _emit_plan("restore", {"summary": f"restore backup ({config.BACKUP_FILE.name})"},
               saved, data.player_map(), data.squad_map(), committed)


# ---------- transfers ----------
def _plan_transfers(team: dict, pairs: list[tuple]) -> tuple[dict, dict, list[str]]:
    """Apply OUT→IN pairs to a squad copy. Returns (after, detail, violations)."""
    after = copy.deepcopy(team)
    squad = set(rules.squad_ids(team))
    moves, spent = [], 0.0
    errs = []
    for out_q, in_q in pairs:
        out_p, in_p = _resolve(out_q), _resolve(in_q)
        where, pos = _locate(after, out_p.id)
        if where is None:
            errs.append(f"{out_p.name} is not in your squad")
            continue
        if in_p.id in squad:
            errs.append(f"{in_p.name} is already in your squad")
            continue
        if in_p.position != out_p.position:
            errs.append(f"position mismatch: {out_p.name} ({out_p.position}) → "
                        f"{in_p.name} ({in_p.position})")
            continue
        after[where][pos] = [in_p.id if x == out_p.id else x for x in after[where][pos]]
        if after.get("benchOrder"):
            after["benchOrder"] = [in_p.id if x == out_p.id else x for x in after["benchOrder"]]
        squad.discard(out_p.id)
        squad.add(in_p.id)
        spent += in_p.price - out_p.price
        moves.append({"out": {"id": out_p.id, "name": out_p.name, "price": out_p.price},
                      "in": {"id": in_p.id, "name": in_p.name, "price": in_p.price},
                      "cost": round(in_p.price - out_p.price, 1)})
    players = data.player_map()
    sq_players = [players[i] for i in squad if i in players]
    errs += rules.validate_squad(sq_players)
    detail = {"moves": moves, "netCost": round(spent, 1),
              "summary": ", ".join(f"{m['out']['name']}→{m['in']['name']}" for m in moves)}
    return after, detail, errs


def _run_transfers(pairs: list[tuple], commit: bool):
    with _session() as client:
        team = _get_team(client)
        after, detail, errs = _plan_transfers(team, pairs)
        if errs:
            _ = output.fail("Transfer breaks the rules.", code=output.EXIT_ERROR,
                            violations=errs, moves=detail["moves"])
        committed = False
        if commit:
            _save_squad(client, after["lineup"], after["bench"])
            committed = True
    _emit_plan("transfer", detail, after, data.player_map(), data.squad_map(), committed)


@transfers_app.command("plan")
def transfers_plan(pairs: list[str] = typer.Argument(..., metavar="OUT IN [OUT IN ...]",
                                                     help="One or more OUT IN player pairs")):
    """Dry-run one or more transfers: show cost, budget impact and rule check."""
    if len(pairs) % 2 != 0:
        _ = output.fail("Provide OUT IN pairs (an even number of players).", code=output.EXIT_ERROR)
    _run_transfers(list(zip(pairs[::2], pairs[1::2])), commit=False)


@transfers_app.command("make")
def transfers_make(
    pairs: list[str] = typer.Argument(..., metavar="OUT IN [OUT IN ...]"),
    commit: bool = typer.Option(False, "--commit", help="Actually save (default: dry-run)"),
):
    """Make one or more transfers (dry-run unless --commit)."""
    if len(pairs) % 2 != 0:
        _ = output.fail("Provide OUT IN pairs (an even number of players).", code=output.EXIT_ERROR)
    _run_transfers(list(zip(pairs[::2], pairs[1::2])), commit=commit)


# ---------- chips ----------
@chips_app.command("play")
def chips_play(
    name: str = typer.Argument(..., help="Chip: " + " | ".join(CHIPS)),
    commit: bool = typer.Option(False, "--commit"),
):
    """Play a chip / booster (dry-run unless --commit)."""
    key = name.lower()
    if key not in CHIPS:
        _ = output.fail(f"Unknown chip '{name}'.", code=output.EXIT_ERROR,
                        valid=list(CHIPS.keys()))
    committed = False
    with _session() as client:
        team = _get_team(client)
        if commit:
            _gated(f"chip:{key}")
            committed = True
    output.emit({"action": "chip", "chip": key, "field": CHIPS[key], "committed": committed},
                lambda: f"[yellow]dry-run[/] would play chip [bold]{key}[/] "
                        "(commit pending endpoint capture)")
