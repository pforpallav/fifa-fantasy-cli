# fifa-fantasy-cli

A pure-terminal **rich CLI** for [FIFA World Cup Fantasy](https://play.fifa.com/fantasy/). No browser, ever — just `httpx` + `typer` + `rich`.

> **Disclaimer.** Unofficial, fan-made, and **not affiliated with or endorsed by FIFA**.
> It talks to an undocumented, private API using *your own* logged-in session. Use it
> only with your own account, for personal and educational purposes, at a polite
> request rate, and in line with FIFA's Terms of Service. Provided as-is, no warranty.

## Install

```bash
pip install -e .
```

This installs a `fifa` command.

## Read-only commands (no login)

These hit the public static feeds — work immediately.

```bash
fifa status                              # counts + next deadline
fifa players list --pos FWD --max-price 8 --sort form --limit 20
fifa players show 1                      # detail card for one player
fifa players search "messi"
fifa players value --pos MID --top 20    # best points-per-million
fifa players differentials --max-owned 5 --min-form 3
fifa fixtures --round 1                  # fixtures for a round (default: next)
fifa fixtures --live                     # only in-progress matches
fifa rounds                              # all matchdays + deadlines
fifa deadlines                           # next deadline vs server time
fifa squads --group a                    # the 48 national teams
fifa refresh                             # force-refresh cached feeds
```

## Authenticated commands (pure-CLI login)

The game uses **cookie-session auth** (session cookies `X-SID` / `ST` / `ST-NO-SS`),
behind FIFA's browser SSO flow and Akamai bot protection. There is **no headless
credentials endpoint** — so `fifa login --email`/password does *not* work. Log in
with a browser once, then import that session into the CLI.

### 1. Import from a logged-in browser (recommended)
Log into <https://play.fifa.com/fantasy/> in your browser, then:
```bash
pip install -e '.[browser]'          # one-time: adds browser-cookie3
fifa login --from-browser chrome     # or: brave | edge | firefox | safari | opera
```
Reads the `*.fifa.com` cookies (session **+** Akamai `_abck`/`bm_sz`) straight from
the browser store and verifies them. On macOS, Chromium browsers trigger a one-time
**Keychain** prompt — click *Allow*.

> Gotcha: Chrome flushes freshly-set cookies to its on-disk store lazily. If the
> import 403s right after logging in, reload the FIFA tab and retry — or the session
> cookies (`X-SID`/`ST`) won't have landed on disk yet. Akamai cookies also rotate,
> so re-run the import if authed calls start failing later.

### 2. Cookie paste (no extra dependency)
In a logged-in tab: **DevTools → Application → Cookies → play.fifa.com**, copy *all*
the cookies as `name=value; name2=value2` (you need `X-SID` and `ST`, not just one), then:
```bash
fifa login --cookie 'X-SID=...; ST=...; _abck=...'
```

Then:
```bash
fifa whoami
fifa team        # your squad, budget, captain, chips
fifa leagues     # leagues you belong to
fifa rank        # your overall ranking
```

```bash
fifa logout      # clears the local session
```

The session cookie is stored at your platform config dir with `0600` perms.

## Managing your team

All mutations are **dry-run by default** — they compute, validate against the
game rules, and print the planned result without touching the network. Add
`--commit` to actually save. Inputs accept a player **id or name**.

```bash
fifa team                          # your squad as a pitch formation
fifa team --list                   # ...or as a table
fifa team validate                 # check squad+formation vs the rules
fifa team swap "De Bruyne" Pulisic # bench a starter, promote a sub (dry-run)
fifa team captain Haaland          # set captain (must be in the XI)
fifa team vice Yamal               # set vice
fifa team backup                   # snapshot current team to disk
fifa team restore --commit         # roll back to the snapshot

fifa transfers plan Isak Arnautovic         # cost + budget + rule check
fifa transfers make Son Mbappe --commit     # one or more OUT IN pairs
fifa chips play wildcard                     # play a chip / booster
```

Rules enforced locally (so invalid asks never hit the API): squad of
**2 GK / 5 DEF / 5 MID / 3 FWD = 15**, **£100m** budget, **max 3 per nation**,
legal starting XI (1 GK + a valid outfield shape).

## Write operations (status)

The squad-save route is confirmed: `POST /api/en/fantasy/team` with body
`{lineup, bench}`. While a team already exists this returns
`creating_the_second_team`, and the **captain / vice / transfer / chip** writes
use a separate route that's loaded from a lazy JS chunk we haven't captured yet.
So `--commit` currently reports a clear "endpoint pending capture" error rather
than guessing. To finish the write path: in the browser, perform the action with
**DevTools → Network** open, right-click the request → **Copy as cURL**, scrub
cookies, and share it — that pins the exact route/payload, after which only
`manage._save_squad` / the gated `_gated` calls need updating.

## Agent / scripting usage

Put `--json` **before** the command to get machine-readable output on stdout and
structured errors (`{"error": ...}`) with exit codes: `0` ok, `1` API/validation
error, `2` auth required/expired.

```bash
fifa --json status
fifa --json players list --pos FWD --max-price 8 --sort form
fifa --json team validate
fifa --json transfers plan Isak Arnautovic      # {moves, netCost, squadValue, committed}
```

Calls stay minimal: authed commands make a single request; player/team IDs are
resolved from the cached bulk feeds (no per-player calls), and requests reuse the
browser's session + Akamai cookies with matching XHR headers to avoid bot flags.

## Architecture

| Layer | Source | Auth |
|---|---|---|
| players / squads / rounds | `play.fifa.com/json/fantasy/*.json` | none (public) |
| server time | `play.fifa.com/api/en/time/current` | none |
| team / leagues / ranking / profile | `play.fifa.com/api/en/fantasy/...` | session cookie |
| login | `play.fifa.com/api/en/auth/sso/login` | — |

```
fifafantasy/
  config.py     # URLs, paths, cookie jar persistence
  client.py     # httpx wrapper, error parsing, 403 -> AuthError
  models.py     # pydantic Player / Squad / Round / Fixture
  data.py       # public feed loaders + disk cache + ID lookups
  auth.py       # SSO login + cookie-paste (no browser)
  render.py     # rich tables/panels
  commands/
    players.py  fixtures.py  account.py
  cli.py        # typer app
```

## Notes

- The tournament starts **June 11, 2026** — until then player points/form are zero and the analytics commands will populate once matches begin.
- Caching: feeds cache to your platform cache dir (60s TTL for players/rounds, 1h for squads). `fifa refresh` busts it.
- Be polite: this targets a geo-gated, ToS-bound service. Personal use against your own account only; the client sends a real User-Agent and you should avoid hammering it.
