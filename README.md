# fifa-fantasy-cli

A fast, **browser-free terminal CLI** for [FIFA World Cup Fantasy](https://play.fifa.com/fantasy/).
Browse players, view your squad as a formation on the pitch, plan transfers with
built-in rule validation, and drive it all from scripts or agents with `--json`.
Built on `httpx` + `typer` + `rich`.

> **Disclaimer.** Unofficial, fan-made, and **not affiliated with or endorsed by FIFA**.
> It talks to an undocumented, private API using *your own* logged-in session. Use it
> only with your own account, for personal and educational purposes, at a polite
> request rate, and in line with FIFA's Terms of Service. Provided as-is, no warranty.

## Features

- ⚽ **Pitch view** — your starting XI rendered as a formation, with captain/vice and squad value
- 🔁 **Team management** — swaps, captain/vice, transfers and chips, all **dry-run by default**
- ✅ **Local rule validation** — budget, squad composition, formation and per-nation limits are checked *before* anything hits the network
- 🔎 **Player analytics** — search, filter, best value (points-per-million), differentials
- 🔐 **Browser-free login** — import your existing session; no password, no headless browser
- 🤖 **Agent-ready** — `--json` on every command, structured errors, meaningful exit codes
- 🪶 **Polite footprint** — disk caching, single requests per command, browser-matching headers

## Requirements

- Python **3.9+**
- A FIFA account (only for the authenticated commands; browsing works without one)

## Install

```bash
git clone https://github.com/pforpallav/fifa-fantasy-cli.git
cd fifa-fantasy-cli
pip install -e .              # installs the `fifa` command
pip install -e '.[browser]'   # optional: enables `fifa login --from-browser`
```

## Quick start

```bash
fifa status                          # player/squad/round counts + next deadline
fifa players list --pos FWD --sort form
fifa login --from-browser chrome     # import your session (see "Logging in")
fifa team                            # your squad on the pitch
```

## Browsing (no login required)

These hit the public static feeds and work immediately:

```bash
fifa status                              # counts + next deadline
fifa players list --pos FWD --max-price 8 --sort form --limit 20
fifa players show "Messi"                # detail card (by name or id)
fifa players search messi
fifa players value --pos MID --top 20    # best points-per-million
fifa players differentials --max-owned 5 --min-form 3
fifa fixtures --round 1                  # fixtures for a round (default: next)
fifa fixtures --live                     # only in-progress matches
fifa rounds                              # all matchdays + deadlines
fifa deadlines                           # next deadline vs server time
fifa squads --group a                    # the 48 national teams
fifa refresh                             # force-refresh cached feeds
```

## Your team

`fifa team` resolves the bare player IDs in your squad against the public feed and
renders the lot as a formation — no per-player API calls:

```
╭─────────────────────── ⚽  My Team · 4-4-2 ────────────────────────╮
│                                 ◉                                  │
│                             Courtois                               │
│                             BEL £4.9                               │
│                                                                    │
│        ◉                ◉                ◉                ◉        │
│    Cucurella         Kimmich         De Cuyper       van de Ven    │
│    ESP £5.1         GER £5.5         BEL £4.7         NED £5.1     │
│                                                                    │
│        ◉                ◉                ◉                ◉        │
│  Lamine Yamal       Raphinha           Olmo           De Bruyne    │
│  ESP £10.0 (V)      BRA £8.2         ESP £7.7         BEL £7.5     │
│                                                                    │
│                         ◉                ◉                         │
│                      Haaland       Son Heung-Min                   │
│                   NOR £10.5 (C)      KOR £7.4                      │
│ ───────────────────────────── Bench ────────────────────────────── │
│        ◉                ◉                ◉                ◉        │
│     Rochet           Olivera          Pulisic           Isak       │
│    URU £4.1         URU £4.3         USA £7.0         SWE £8.0     │
│ ────────────────────────────────────────────────────────────────── │
│                    Squad value £100.0m / £100m                     │
│           ◉ (C) Erling Haaland       ◉ (V) Lamine Yamal            │
│              Free transfers: -   ·   Chips used: none              │
╰────────────────────────────────────────────────────────────────────╯
```

### Making changes

Every mutation is **dry-run by default**: it computes the result, validates it
against the game rules, and shows you the plan *without saving*. Add `--commit` to
write. Inputs accept a player **id or name**.

```bash
fifa team --list                     # table view instead of the pitch
fifa team validate                   # check current squad + formation vs the rules
fifa team swap "De Bruyne" Pulisic   # bench a starter, promote a sub
fifa team captain Haaland            # set captain (must be in the XI)
fifa team vice Yamal                 # set vice
fifa team backup                     # snapshot current team to disk
fifa team restore --commit           # roll back to the snapshot

fifa transfers plan Isak Arnautovic       # cost + budget + rule check
fifa transfers make Son Mbappe --commit   # one or more OUT IN pairs
fifa chips play wildcard                  # play a chip / booster
```

Rules enforced locally (so invalid asks never reach the API): a squad of
**2 GK / 5 DEF / 5 MID / 3 FWD = 15**, a **£100m** budget, **max 3 players per
nation**, and a legal starting XI (1 GK + a valid outfield shape).

## Logging in

The game uses **cookie-session auth** (`X-SID` / `ST` / `ST-NO-SS`) behind FIFA's
browser SSO flow and Akamai bot protection. There is **no headless password
endpoint** — so you log in with a browser once and import that session.

### Import from a logged-in browser (recommended)

Log into <https://play.fifa.com/fantasy/> in your browser, then:

```bash
pip install -e '.[browser]'          # one-time
fifa login --from-browser chrome     # or: brave | edge | firefox | safari | opera
```

This reads the `*.fifa.com` cookies (session **+** Akamai `_abck`/`bm_sz`) straight
from the browser's cookie store and verifies them. On macOS, Chromium browsers
trigger a one-time **Keychain** prompt — click *Allow*.

> **Heads-up:** Chrome flushes freshly-set cookies to disk lazily. If the import
> fails with a 403 right after logging in, reload the FIFA tab and retry. Akamai
> cookies also rotate over time, so re-run the import if authed calls start failing.

### Paste cookies (no extra dependency)

In a logged-in tab open **DevTools → Application → Cookies → play.fifa.com**, copy
*all* the cookies as `name=value; name2=value2` (you need at least `X-SID` and `ST`):

```bash
fifa login --cookie 'X-SID=...; ST=...; _abck=...'
```

Then:

```bash
fifa whoami      # who you're logged in as
fifa team        # your squad
fifa leagues     # leagues you belong to
fifa rank        # overall ranking
fifa logout      # clear the local session
```

The session is stored in your platform config dir with `0600` permissions and is
never written into the repo.

## Agent / scripting usage

Put `--json` **before** the command for machine-readable output on stdout and
structured errors (`{"error": ...}`). Exit codes: `0` ok, `1` API/validation error,
`2` auth required or expired.

```bash
fifa --json status
fifa --json players list --pos FWD --max-price 8 --sort form
fifa --json team validate
fifa --json transfers plan Isak Arnautovic    # -> {moves, netCost, squadValue, committed, ...}
```

Calls stay minimal: each authed command makes a single request, player/team IDs are
resolved from the cached bulk feeds (no per-player calls), and requests reuse the
browser's session and Akamai cookies with matching XHR headers.

## How it works

| Layer | Source | Auth |
|---|---|---|
| players / squads / rounds | `play.fifa.com/json/fantasy/*.json` | none (public) |
| server time | `play.fifa.com/api/en/time/current` | none |
| team / leagues / ranking / profile | `play.fifa.com/api/en/fantasy/...` | session cookie |
| login | browser SSO + Akamai (no password API) | import session cookies |

```
fifafantasy/
  cli.py          # typer app: global --json flag, command wiring
  config.py       # URLs, game rules, paths, cookie persistence
  client.py       # httpx wrapper, error parsing, auth headers
  auth.py         # browser-session import + cookie paste
  data.py         # public-feed loaders, disk cache, name→id resolution
  models.py       # pydantic Player / Squad / Round / Fixture
  rules.py        # squad / formation / budget validation (pure, no I/O)
  render.py       # rich tables, panels, and the pitch view
  output.py       # --json vs rich switch, structured errors + exit codes
  commands/
    players.py    # browse / search / value / differentials
    fixtures.py   # fixtures / rounds / deadlines / squads
    account.py    # login / logout / whoami / leagues / rank
    manage.py     # team view + swap / captain / transfers / chips / backup
```

## Status & limitations

- **Reading, analytics, and dry-run planning are fully working.**
- **Live writes are partial.** The squad-save route (`POST /api/en/fantasy/team`
  with `{lineup, bench}`) is confirmed, but the **captain / vice / transfer / chip**
  saves use a separate route that isn't wired up yet. Until it is, `--commit` on
  those reports a clear "endpoint pending" error instead of guessing — dry-run plans
  still work. (Contributions welcome — see below.)
- The tournament starts **June 11, 2026**; until matches begin, player points and
  form read as zero and the analytics populate once games are played.

## Contributing

Issues and PRs welcome. The most useful contribution right now is **capturing the
real write endpoints**: with DevTools → Network open on play.fifa.com, perform a
captain change / transfer / chip play, copy the request, and open an issue with the
route + payload shape (cookies scrubbed). Wiring those into `commands/manage.py`
is then a small change.

## License

[MIT](LICENSE).
