.PHONY: test test-unit test-integration test-agent lint format typecheck run serve

# Run all unit tests
test-unit:
	uv run pytest tests/unit -v

# Run integration tests (needs network)
test-integration:
	uv run pytest tests/integration -v

# Run agent tests (needs Ollama running)
test-agent:
	uv run pytest tests/agent -v

# Run all tests
test:
	uv run pytest tests/ -v

# Run tests with coverage
test-coverage:
	uv run pytest tests/ --cov=src/depadvisor --cov-report=term-missing

# Lint code
lint:
	uv run ruff check src/ tests/

# Auto-format code
format:
	uv run ruff format src/ tests/

# Type check
typecheck:
	uv run mypy src/depadvisor

# Run the CLI
run:
	uv run depadvisor $(ARGS)

# Run the server
serve:
	uv run depadvisor serve