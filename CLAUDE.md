# CLAUDE.md

## Project Overview

A Python CLI tool for looking up UK train advance ticket prices.

**Main purpose:** Query a train pricing API and present journey options and fares clearly in the terminal.

## Running Commands

```bash
uv run python train_tickets.py <command>

# Examples
uv run python train_tickets.py status
uv run python train_tickets.py search "London Kings Cross" "Edinburgh" 2026-07-01
```

## Architecture

### Entry Point

- `train_tickets.py` — Click CLI, registers all commands

### Core

- `core/client.py` — `TrainClient` class; all HTTP requests go here

### Commands

- `commands/setup.py` — `ColouredGroup` and `status` command
- `commands/search.py` — `search` command

## Style Rules

- **Always British English** in code, comments, output, and documentation
- **Small files** — keep modules focused; split when a file grows beyond ~150 lines
- **Reuse helpers** — add shared logic to `core/` rather than duplicating across commands
- **No third-party scraping libraries** — use `requests` directly

## Git Workflow

Single-person project — commit directly to `main`. No feature branches needed.

## Dependencies

- `click>=8.0.0` — CLI framework
- `requests>=2.28.0` — HTTP client
