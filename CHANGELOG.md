# Changelog

All notable changes to DepAdvisor will be documented in this file.

## [0.1.0] - 2026-04-15

### Added

- Initial release
- Python ecosystem support: `requirements.txt`, `pyproject.toml` (PEP 621 + Poetry)
- Node.js ecosystem support: `package.json`
- Java/Maven ecosystem support: `pom.xml`
- PyPI, npm, and Maven Central registry clients
- OSV.dev vulnerability scanning
- GitHub Releases changelog fetching
- LangGraph-powered analysis pipeline with risk scoring
- LLM integration: Ollama (local) and OpenAI (cloud)
- CLI with `analyze`, `scan`, `version`, and `serve` commands
- Output formats: terminal (Rich), Markdown, JSON, GitHub comment
- FastAPI HTTP server mode
- `--fail-on` flag for CI/CD integration
- File-based response caching
