# 🚂 Train Tickets

A Python CLI tool for looking up UK train advance ticket prices.

## Running

```bash
# Search for advance tickets 🎫
uv run python tickets.py search "London Kings Cross" "Edinburgh" 2026-07-01

# Show status
uv run python tickets.py status
```

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run python -m pytest -v
```

## Project Structure

- `tickets.py` — CLI entry point
- `core/client.py` — API client
- `commands/setup.py` — Status command and `ColouredGroup`
- `commands/search.py` — Search command
