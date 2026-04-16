# Contributing to DepAdvisor

Thanks for your interest in contributing! This guide covers setup, code style, testing, and how to submit changes.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/chaubes/depadvisor.git
cd depadvisor

# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (including dev extras)
uv sync --all-extras

# Install Ollama for local LLM testing (optional)
# macOS: brew install ollama
# Linux: curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
```

## Code Style

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
uv run ruff check src/ tests/

# Auto-fix issues
uv run ruff check src/ tests/ --fix

# Format code
uv run ruff format src/ tests/
```

Key conventions:
- Line length: 120 characters
- Python 3.11+ type hints (`str | None` instead of `Optional[str]`)
- Import sorting: `isort`-compatible via Ruff

## Testing

Tests are organized into three tiers:

```bash
# Unit tests (fast, no network, no LLM)
uv run pytest tests/unit -v

# Integration tests (requires network)
uv run pytest tests/integration -v

# Agent tests (requires LangGraph, optionally Ollama)
uv run pytest tests/agent -v

# All tests
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=src/depadvisor --cov-report=term-missing
```

### Writing Tests

- **Unit tests** go in `tests/unit/`. Mock external APIs with `respx`.
- **Integration tests** go in `tests/integration/`. These hit real APIs.
- **Agent tests** go in `tests/agent/`. Test graph construction and pipeline.
- Use fixtures from `tests/fixtures/` for test data.

## Adding a New Ecosystem

1. Create a parser in `src/depadvisor/parsers/` inheriting from `BaseParser`
2. Create a registry client in `src/depadvisor/clients/` inheriting from `BaseRegistryClient`
3. Add the ecosystem to `Ecosystem` enum in `models/schemas.py`
4. Register the parser in `agent/nodes/parse_deps.py`
5. Register the client in `agent/nodes/check_updates.py`
6. Add test fixtures and tests

## Pull Requests

1. Fork the repository and create a feature branch
2. Make your changes with tests
3. Ensure all checks pass: `uv run ruff check src/ tests/ && uv run pytest tests/unit tests/agent -v`
4. Submit a PR with a clear description of what changed and why

## Reporting Issues

Please include:
- DepAdvisor version (`depadvisor version`)
- Python version
- OS
- Steps to reproduce
- Expected vs actual behavior
