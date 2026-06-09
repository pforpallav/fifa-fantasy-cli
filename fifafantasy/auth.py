"""Pure-terminal authentication. No browser.

Two paths, both 100% CLI:
  1. SSO login  — POST credentials to /api/en/auth/sso/login, capture session cookie.
  2. Cookie paste — user supplies a `name=value; ...` string copied from DevTools once.

If FIFA ID layers in CAPTCHA/MFA, path 1 may fail; path 2 always works.
"""

from __future__ import annotations

from . import config
from .client import AuthError, FifaClient, FifaError


def login_sso(email: str, password: str) -> dict:
    """Attempt headless SSO login. Returns the user payload on success."""
    client = FifaClient()
    try:
        # The SSO endpoint accepts the identity payload; field names mirror the web app.
        payload = {"email": email, "password": password}
        client.post_json(config.URL_SSO_LOGIN, json_body=payload, auth=True)
        client.persist_cookies()
        # Verify the session actually works
        user = client.get_json(config.URL_USER, auth=True)
        return user
    finally:
        client.close()


def login_cookie(cookie_str: str) -> dict:
    """Store a pasted cookie string and verify it grants a session."""
    client = FifaClient()
    try:
        client.set_cookie_string(cookie_str)
        user = client.get_json(config.URL_USER, auth=True)  # raises AuthError if invalid
        return user
    finally:
        client.close()


# Browsers browser_cookie3 can read cookie stores from.
_BROWSER_LOADERS = ("chrome", "chromium", "brave", "edge", "firefox", "opera", "safari")


def login_from_browser(browser: str = "chrome") -> dict:
    """Import the FIFA session from a logged-in local browser — no manual copy.

    FIFA login is a browser SSO flow behind Akamai bot protection, so there is
    no headless credentials endpoint. Instead we read the play.fifa.com cookies
    (FIFA session + Akamai `_abck`/`bm_sz`) directly out of a browser you've
    already logged in with, then verify they grant a session.
    """
    try:
        import browser_cookie3 as bc3
    except ImportError as e:
        raise FifaError(
            "browser import support is not installed. "
            "Install it with:  pip install 'fifa-fantasy-cli[browser]'"
        ) from e

    key = browser.lower()
    loader = getattr(bc3, key, None)
    if key not in _BROWSER_LOADERS or loader is None:
        raise FifaError(
            f"Unknown browser '{browser}'. Choose one of: {', '.join(_BROWSER_LOADERS)}"
        )

    try:
        # domain_name filters to *.fifa.com cookies (play.fifa.com + Akamai on .fifa.com)
        jar = loader(domain_name="fifa.com")
    except Exception as e:  # browser_cookie3 raises various store/keychain errors
        raise FifaError(
            f"Could not read cookies from {browser}: {e}\n"
            "On macOS, Chrome cookies require a Keychain access prompt — allow it and retry."
        ) from e

    cookies = {c.name: c.value for c in jar}
    if not cookies:
        raise AuthError(
            f"No fifa.com cookies found in {browser}. "
            "Log into https://play.fifa.com/fantasy/ in that browser first, then retry."
        )

    config.save_cookies(cookies)
    client = FifaClient()  # reloads the cookies we just saved
    try:
        user = client.get_json(config.URL_USER, auth=True)  # raises AuthError if invalid
        return user
    finally:
        client.close()


def logout() -> None:
    client = FifaClient()
    try:
        try:
            client.post_json(config.URL_LOGOUT, auth=False)
        except (FifaError, AuthError):
            pass  # best-effort server-side logout
    finally:
        client.close()
    config.clear_cookies()


def whoami() -> dict | None:
    client = FifaClient()
    try:
        if not client.has_session:
            return None
        return client.get_json(config.URL_USER, auth=True)
    except AuthError:
        return None
    finally:
        client.close()
