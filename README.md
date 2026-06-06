# 🚂 Train Tickets

A Python CLI tool for looking up UK train advance ticket prices on a fixed commuter route.

## Commands

Given any date, the tool finds that date's week (Mon–Sun) and reports the four cheapest morning trains (Tunbridge Wells → London Terminals, 05:44–07:45) on the configured travel days (Tue/Wed/Thu by default, overridable with `--days`).

| Command | Description |
|---------|-------------|
| `search WEEK_DATE [--days]` | Fetch and display the cheapest advance fares for the week containing WEEK_DATE |
| `record WEEK_DATE [--days]` | Same as `search`, and also saves results to a local JSON file 🎫 |
| `status` | Show the active configuration and local record path |

```bash
# Show cheapest fares for the week of 15 August 2026
uv run python tickets.py search 2026-08-15

# Save results as well as printing them
uv run python tickets.py record 2026-08-15

# Override travel days (comma-separated three-letter abbreviations)
uv run python tickets.py search 2026-08-15 --days Mon,Fri

# Show current configuration
uv run python tickets.py status
```

The `record` command saves results to a local JSON file (`~/.train-tickets/prices.json`) kept outside the repository so prices accumulate over time without being committed.

## Configuration

Non-private settings (station codes, travel days, time window) live in `tunbridge-wells.local` and are committed to the repository. The storage path points outside the repo and is expanded at runtime.

## Development

```bash
# Install dependencies
uv sync

# Run tests (27 tests, all HTTP mocked)
uv run python -m pytest -v
```
