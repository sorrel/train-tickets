# CLAUDE.md

## Project Overview

A Python CLI tool for looking up UK train advance ticket prices on a fixed commuter route (Tunbridge Wells → London Terminals, morning peak).

**Main purpose:** Query a train pricing API and present journey options and fares clearly in the terminal. Given any date, find that week's cheapest advance fares on the configured travel days.

## Running Commands

```bash
uv run python tickets.py <command>

# Examples
uv run python tickets.py status
uv run python tickets.py search 2026-08-15
uv run python tickets.py record 2026-08-15 --days Mon,Fri
```

## Architecture

```
tickets.py                  CLI entry point — registers all commands
core/
  config.py                 Load tunbridge-wells.local → JourneyConfig dataclass
  dates.py                  Week calculation (Mon–Sun for a given date)
  fares.py                  Parse raw API responses into fare summaries
  client.py                 TrainClient — all HTTP requests, token caching
  storage.py                Read/write local JSON price record
commands/
  setup.py                  ColouredGroup and status command
  search.py                 search command
  record.py                 record command (search + persist)
tunbridge-wells.local       Committed config: station codes, days, time window
tests/                      27 tests (all HTTP mocked, no live API calls)
```

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
- Budget: a full week lookup is approximately 15 spaced requests (3 days × (1 plan + 4 detail fetches)).
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
