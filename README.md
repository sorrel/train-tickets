# 🚂 Train Tickets

A Python CLI tool for looking up UK train advance ticket prices on a commuter route you configure.

## Commands

Given any date, the tool finds that date's week and reports the five earliest morning trains on your configured route and time window, on the configured days (Tue/Wed/Thu by default, overridable with `--days`). Every lookup is saved, so prices build up over time.

| Command | Description |
|---------|-------------|
| `search WEEK_DATE [--days]` | Fetch, display, and save the advance fares for the week containing WEEK_DATE 🎫 |
| `view [--all]` | Browse saved fares grouped by week (future dates by default; `--all` includes the past) |
| `refresh-price-data` | Slowly walk every future week from tomorrow, gathering fares until none are on sale |
| `status` | Show the active configuration and local record path |

```bash
# Show (and save) the earliest fares for the week of 15 August 2026
uv run python tickets.py search 2026-08-15

# Override travel days (comma-separated three-letter abbreviations)
uv run python tickets.py search 2026-08-15 --days Mon,Fri

# Browse what's been gathered so far
uv run python tickets.py view

# Gather everything available, week by week (slow and deliberate — leave it running)
uv run python tickets.py refresh-price-data

# Show current configuration
uv run python tickets.py status
```

Results are saved to a local JSON file (`~/.train-tickets/prices.json`) kept outside the repo, so prices accumulate over time without being committed. `view` highlights the cheapest fares — green `← cheapest` for the lowest across everything on show, yellow `← cheaper` for a week's own low — flags when a day's cheapest has risen or fallen since the last check, and notes the booking horizon (the point beyond which fares aren't on sale yet).

`refresh-price-data` reuses the same gathering as `search`, looping it across weeks with a randomised pause between each so a long run stays a polite, ordinary stream of requests. It saves as it goes, so you can watch progress with `view` in another terminal.

## Configuration

Copy `config.example.json` to `config.local.json` and set your own route (station NLC codes and names), travel days, and time window:

```bash
cp config.example.json config.local.json
# then edit config.local.json
```

`config.local.json` is gitignored — your personal route never leaves your machine. The storage path points outside the repo and is expanded at runtime.

## Development

```bash
# Install dependencies
uv sync

# Run tests (all HTTP mocked)
uv run python -m pytest -v
```
