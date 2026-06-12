"""Paths, base URLs, and shared constants."""

from __future__ import annotations

import json
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir

APP_NAME = "fifa-fantasy-cli"

# --- Base URLs (confirmed via live inspection of play.fifa.com) ---
SITE = "https://play.fifa.com"
LANG = "en"
PUBLIC_JSON = f"{SITE}/json/fantasy"          # static, no auth
API = f"{SITE}/api/{LANG}"                     # cookie-session auth proxy
API_FANTASY = f"{API}/fantasy"

# Public feeds
URL_PLAYERS = f"{PUBLIC_JSON}/players.json"
URL_SQUADS = f"{PUBLIC_JSON}/squads.json"
URL_ROUNDS = f"{PUBLIC_JSON}/rounds.json"
URL_TIME = f"{API}/time/current"               # public

# Auth + user
URL_SSO_LOGIN = f"{API}/auth/sso/login"
URL_LOGOUT = f"{API}/auth/logout"
URL_USER = f"{API}/user"

# Game (authenticated) — reads
URL_TEAM = f"{API_FANTASY}/team"
URL_PROFILE = f"{API_FANTASY}/profile"
URL_RANKING = f"{API_FANTASY}/ranking/overall"
URL_LEAGUES = f"{API_FANTASY}/leagues"
URL_LEAGUE = f"{API_FANTASY}/league"
URL_LEAGUE_STANDINGS = f"{API_FANTASY}/ranking/league/{{lid}}"   # GET league standings
URL_LEAGUE_USERS = f"{API_FANTASY}/league/{{lid}}/league-users"  # GET league members
URL_MEMBER_TEAM = f"{API_FANTASY}/team/{{uid}}"                  # GET any member's squad

# Game (authenticated) — writes (discovered from the FANTASY_CLASSIC JS chunk)
URL_TEAM_CAPTAIN = f"{API_FANTASY}/team/captain/{{pid}}"   # POST, no body
URL_TEAM_VICE = f"{API_FANTASY}/team/vice/{{pid}}"         # POST, no body
URL_SUBSTITUTION = f"{API_FANTASY}/substitution/make"      # POST {roundId, subs:[{out,in}]}
URL_TRANSFERS = f"{API_FANTASY}/transfers/make/{{round}}"  # POST {transfers:[{out,in}]}
URL_BOOSTER = f"{API_FANTASY}/booster/{{name}}"            # POST, no body (twelfth-man: name="twelfth-man/{pid}")
URL_BOOSTER_REVERT = f"{API_FANTASY}/booster/revert"       # POST, no body

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# --- Game rules (confirmed empirically from a live valid squad) ---
SQUAD_COMPOSITION = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}  # 15 players
SQUAD_SIZE = 15
STARTING_SIZE = 11
# Legal starting-XI bounds per position (1 GK always; outfield within these).
FORMATION_LIMITS = {"GK": (1, 1), "DEF": (3, 5), "MID": (2, 5), "FWD": (1, 3)}
BUDGET = 100.0
MAX_PER_SQUAD = 3  # max players from a single national team

# --- Local storage ---
CONFIG_DIR = Path(user_config_dir(APP_NAME))
CACHE_DIR = Path(user_cache_dir(APP_NAME))
COOKIE_FILE = CONFIG_DIR / "cookies.json"
BACKUP_FILE = CONFIG_DIR / "team-backup.json"
CACHE_TTL_SECONDS = 60  # static feeds change slowly; live scores poll faster


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def load_cookies() -> dict[str, str]:
    if COOKIE_FILE.exists():
        try:
            return json.loads(COOKIE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_cookies(cookies: dict[str, str]) -> None:
    ensure_dirs()
    COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
    try:
        COOKIE_FILE.chmod(0o600)  # session secret — restrict perms
    except OSError:
        pass


def clear_cookies() -> None:
    if COOKIE_FILE.exists():
        COOKIE_FILE.unlink()
