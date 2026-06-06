# 🚂 Train Tickets

A Python CLI tool for looking up UK train advance ticket prices on a commuter route you configure.

## Commands

Given any date, the tool finds that date's week and reports the four cheapest morning trains on your configured route and time window, on the configured days (Tue/Wed/Thu by default, overridable with `--days`).

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

The `record` command saves results to a local JSON file (`~/.train-tickets/prices.json`) kept outside the repo so prices accumulate over time without being committed.

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
