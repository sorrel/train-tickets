# 🚂 Train Tickets

A Python CLI tool for looking up UK train advance ticket prices on a commuter route you configure.

## Commands

Given any date, the tool finds that date's week and reports the earliest morning trains on your configured route and time window, on the configured days (Tue/Wed/Thu by default, overridable with `--days`). Every lookup is saved, so prices build up over time.

There are two directions. The **morning** run (home → London) is the default. Add `--evening` for the **evening return** (London → home); its window (17:45–19:15 by default) is timed at London Bridge, since every train calls there. `view` shows both directions together for any day that has them.

| Command | Description |
|---------|-------------|
| `search WEEK_DATE [--days] [--evening]` | Fetch, display, and save the advance fares for the week containing WEEK_DATE 🎫 |
| `view [--all]` | Browse saved fares grouped by week (future dates by default; `--all` includes the past) |
| `refresh-price-data [--evening]` | Slowly walk every future week from tomorrow, gathering fares until none are on sale |
| `status` | Show the active configuration and local record path |

```bash
# Show (and save) the earliest morning fares for the week of 15 August 2026
uv run python tickets.py search 2026-08-15

# The evening return (London → home) for that week
uv run python tickets.py search 2026-08-15 --evening

# Override travel days (comma-separated three-letter abbreviations)
uv run python tickets.py search 2026-08-15 --days Mon,Fri

# Browse what's been gathered so far (both directions)
uv run python tickets.py view

# Gather everything available, week by week (slow and deliberate — leave it running)
uv run python tickets.py refresh-price-data            # morning
uv run python tickets.py refresh-price-data --evening  # evening return

# Show current configuration
uv run python tickets.py status
```

Results are saved to a local JSON file (`~/.train-tickets/prices.json`) kept outside the repo, so prices accumulate over time without being committed. `view` highlights the cheapest fares — green `← cheapest` for the lowest across everything on show, yellow `← cheaper` for a week's own low (computed separately for each direction, since morning and evening fares aren't comparable) — flags when a day's cheapest has risen or fallen since the last check, and notes the booking horizon (the point beyond which fares aren't on sale yet).

`refresh-price-data` reuses the same gathering as `search`, looping it across weeks with a randomised pause between each so a long run stays a polite, ordinary stream of requests. It saves as it goes, so you can watch progress with `view` in another terminal.

## Configuration

Copy `config.example.json` to `config.local.json` and set your own route (station NLC codes and names), travel days, and time windows. The morning window is `window_start`/`window_end`; the evening return window is `evening_window_start`/`evening_window_end` (default 17:45–19:15). The evening route is the morning's stations reversed, so no extra stations need configuring:

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
