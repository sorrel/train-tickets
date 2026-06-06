# CLAUDE.md

## Project Overview

A Python CLI tool for looking up UK train advance ticket prices on a commuter route the user configures (morning peak).

**Main purpose:** Query a train pricing API and present journey options and fares clearly in the terminal. Given any date, find that week's cheapest advance fares on the configured travel days.

## Running Commands

```bash
uv run python tickets.py <command>

# Examples
uv run python tickets.py status
uv run python tickets.py search 2026-08-15            # one week, saved as it goes
uv run python tickets.py view                          # browse saved fares by week
uv run python tickets.py refresh-price-data            # slow bulk walk, all future weeks
```

## Architecture

```
tickets.py                  CLI entry point — registers all commands
core/
  config.py                 Load config.local.json → JourneyConfig dataclass
  dates.py                  Week calculation (Mon–Sun for a given date)
  fares.py                  Parse raw API responses into fare summaries
  client.py                 TrainClient — all HTTP requests, token caching
  storage.py                Read/write local JSON price record
commands/
  setup.py                  ColouredGroup and status command
  search.py                 search command + gather_week (shared per-week gathering)
  view.py                   view command (browse saved fares, cheap markers, horizon note)
  refresh.py                refresh-price-data command (slow bulk walk over future weeks)
config.example.json         Committed generic template (copy to config.local.json)
config.local.json           Personal route config — gitignored, never committed
tests/                      all HTTP mocked, no live API calls
```

`search` and `refresh-price-data` share `gather_week` (in search.py) for the
actual lookup/persist/horizon work — refresh is just a careful loop around it,
not a second copy of the gathering logic.

## API

- **Journey plan:** `POST https://api.southeasternrailway.co.uk/jp/journey-plan` — returns a list of journeys. Envelope: `{result, links}`. Cheapest fare per journey: `result.outward[i].fares.cheapest.totalPrice` (pence).
- **Journey detail:** `GET {API_BASE}{journey_ref}` — returns times for one journey. Envelope: `{result, links}`. Times: `result.origin.time.scheduledTime` and `result.destination.time.scheduledTime` (ISO format).
- **Auth:** single header `x-access-token`. The value is a public token scraped from the booking-page HTML (`"apiAccessToken":"..."` regex). Cached in memory; dropped and re-scraped on 401/403. The token-page URL uses a date ~30 days ahead so it never goes stale.
- **Advance vs Anytime:** prices are in pence. A journey with more than one single fare has an Advance fare below the £24.90 Anytime ceiling; a journey with a single lone fare is Anytime-only. Detection: `is_advance = len(fares["singles"]) > 1`. (Mornings are peak so off-peak fares never apply.)

## Politeness

**Critical — read before adding any API calls.**

This is a free public endpoint for ordinary customers; we are not owed extra service. **Never burst.**

- The client sleeps between every API call (`request_pause_seconds` from config).
- The token is cached in memory and reused across calls.
- Budget: a full week lookup is roughly 27 spaced requests (3 days × (1 plan + ~8 detail fetches)). The plan carries no departure times, so we must fetch the detail of every journey it returns to sort by departure and pick the earliest few. A morning window returns only a handful of journeys, so this stays modest — but it is one detail call per journey, not per displayed train.
- `refresh-price-data` walks every future week (~12, the advance-booking horizon), so a full run is a few hundred requests. This is acceptable *only because* it is deliberately slow: the per-call pause still applies, **and** a randomised pause (`refresh_pause_min_seconds`–`refresh_pause_max_seconds`) sits between each week. It is the opposite of a burst. Keep it that way — do not parallelise it or shorten the pauses to "speed it up".
- Never run load-style request floods, even during development or testing.
- Tests mock all HTTP and never hit the live API.

## Style Rules

- **Always British English** in code, comments, output, and documentation
- **Small files** — keep modules focused; split when a file grows beyond ~150 lines
- **Reuse helpers** — add shared logic to `core/` rather than duplicating across commands
- **No third-party scraping libraries** — use `requests` directly

## Git Workflow

Always work on a feature branch — `main` is protected and requires a PR to merge.

```bash
git checkout -b feature/description
# ... make changes, commit ...
gh pr create
```

Squash merge only. Branch is deleted automatically after merge.

## Dependencies

- `click>=8.0.0` — CLI framework
- `requests>=2.28.0` — HTTP client
