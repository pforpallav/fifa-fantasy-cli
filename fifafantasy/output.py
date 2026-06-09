"""Output layer: switch between rich (human) and JSON (agent) rendering.

Every command computes plain data, then either prints it as JSON (when the
global --json flag is set) or prints a rich renderable. Errors are structured
in JSON mode and carry meaningful exit codes:

    0  success
    1  API / validation error
    2  auth required or expired
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import typer

from .render import console

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_AUTH = 2

_state = {"json": False}


def set_json(on: bool) -> None:
    _state["json"] = on


def is_json() -> bool:
    return _state["json"]


def emit(data: Any, renderable: Optional[Callable[[], Any]] = None) -> None:
    """Print `data` as JSON, or call `renderable()` for the rich view.

    `renderable` is a thunk so we never build rich objects in JSON mode.
    """
    if _state["json"]:
        console.print_json(data=data, default=str)
    elif renderable is not None:
        console.print(renderable())


def fail(message: str, code: int = EXIT_ERROR, **extra: Any) -> "typer.Exit":
    """Report an error (structured in JSON mode) and exit with `code`."""
    if _state["json"]:
        console.print_json(data={"error": message, **extra}, default=str)
    else:
        console.print(f"[red]{message}[/]")
        for k, v in extra.items():
            console.print(f"[dim]{k}: {v}[/]")
    raise typer.Exit(code)
