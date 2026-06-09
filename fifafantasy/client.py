"""HTTP client: cookie-jar persistence, error parsing, public + auth calls."""

from __future__ import annotations

from typing import Any

import httpx

from . import config


class FifaError(Exception):
    """API returned a structured error."""


class AuthError(FifaError):
    """403 / invalid credentials — session missing or expired."""


def _parse_errors(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        errs = data.get("errors")
        if errs:
            return "; ".join(e.get("message", str(e)) for e in errs)
    except Exception:
        pass
    return f"HTTP {resp.status_code}"


class FifaClient:
    """Wraps httpx with the FIFA Fantasy base URLs and a persistent cookie jar."""

    def __init__(self) -> None:
        cookies = config.load_cookies()
        self._http = httpx.Client(
            headers={
                "User-Agent": config.USER_AGENT,
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": config.SITE,
                "Referer": f"{config.SITE}/fantasy/",
                # Mirror the web app's XHR so requests are indistinguishable from
                # the browser (and reuse its Akamai cookies) — avoids bot flags.
                "X-Requested-With": "XMLHttpRequest",
            },
            cookies=cookies,
            timeout=20.0,
            follow_redirects=True,
        )

    # --- low level ---
    def get_json(self, url: str, *, params: dict | None = None, auth: bool = False) -> Any:
        resp = self._http.get(url, params=params)
        return self._handle(resp, auth)

    def post_json(self, url: str, *, json_body: dict | None = None, auth: bool = False) -> Any:
        resp = self._http.post(url, json=json_body)
        return self._handle(resp, auth)

    def _handle(self, resp: httpx.Response, auth: bool) -> Any:
        if resp.status_code == 403:
            raise AuthError(
                _parse_errors(resp)
                + "  (run `fifa login` — your session is missing or expired)"
            )
        if resp.status_code >= 400:
            raise FifaError(_parse_errors(resp))
        if resp.headers.get("content-type", "").startswith("application/json") or resp.text:
            try:
                return resp.json()
            except Exception:
                return resp.text
        return None

    # --- cookie management ---
    def persist_cookies(self) -> None:
        config.save_cookies({c.name: c.value for c in self._http.cookies.jar})

    def set_cookie_string(self, cookie_str: str) -> None:
        """Accept a raw `name=value; name2=value2` string pasted from DevTools."""
        for part in cookie_str.split(";"):
            if "=" in part:
                name, _, value = part.strip().partition("=")
                self._http.cookies.set(name.strip(), value.strip(), domain="play.fifa.com")
        self.persist_cookies()

    @property
    def has_session(self) -> bool:
        return len(list(self._http.cookies.jar)) > 0

    def close(self) -> None:
        self._http.close()
