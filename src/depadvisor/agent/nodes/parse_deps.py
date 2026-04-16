"""
Node: parse_dependencies

First node in the graph. Reads dependency files from the project
and populates state['dependencies'].

This node does NOT use the LLM — it's pure Python parsing.
"""

from pathlib import Path

from depadvisor.agent.state import DepAdvisorState
from depadvisor.models.schemas import DependencyInfo, Ecosystem
from depadvisor.parsers.java import JavaParser
from depadvisor.parsers.node import NodeParser
from depadvisor.parsers.python import PythonParser

# Registry of parsers by ecosystem
PARSERS = {
    Ecosystem.PYTHON: PythonParser(),
    Ecosystem.NODE: NodeParser(),
    Ecosystem.JAVA: JavaParser(),
}

# Directories to skip during file discovery
SKIP_DIRS = {
    "node_modules", ".venv", "venv", "env", ".env",
    ".git", ".hg", ".svn",
    "target", "build", "dist", "__pycache__",
    ".tox", ".nox", ".mypy_cache", ".ruff_cache",
    "vendor", "bower_components",
}


def _find_dep_files(project_path: Path, parser) -> list[Path]:
    """Find dependency files, skipping vendored/generated directories."""
    results = []
    for item in project_path.iterdir():
        if item.is_dir():
            if item.name in SKIP_DIRS:
                continue
            results.extend(_find_dep_files(item, parser))
        elif item.is_file() and parser.can_parse(str(item)):
            results.append(item)
    return results


def _deduplicate(deps: list[DependencyInfo]) -> list[DependencyInfo]:
    """Deduplicate dependencies, keeping the first occurrence of each package."""
    seen = set()
    unique = []
    for dep in deps:
        key = (dep.name, dep.ecosystem)
        if key not in seen:
            seen.add(key)
            unique.append(dep)
    return unique


async def parse_dependencies_node(state: DepAdvisorState) -> dict:
    """
    Parse dependency files from the project directory.

    Reads: state['project_path'], state['ecosystem']
    Writes: state['dependencies'], state['current_node']
    """
    project_path = Path(state["project_path"])
    ecosystem = state["ecosystem"]
    errors = list(state.get("errors", []))

    parser = PARSERS.get(ecosystem)
    if parser is None:
        errors.append(f"No parser available for ecosystem: {ecosystem}")
        return {
            "dependencies": [],
            "current_node": "parse_deps",
            "errors": errors,
        }

    # Find dependency files, skipping node_modules/venv/etc.
    dep_files = _find_dep_files(project_path, parser)

    dependencies = []
    for file_path in dep_files:
        try:
            deps = parser.parse(str(file_path))
            dependencies.extend(deps)
        except Exception as e:
            errors.append(f"Error parsing {file_path}: {e}")

    dependencies = _deduplicate(dependencies)

    return {
        "dependencies": dependencies,
        "current_node": "parse_deps",
        "errors": errors,
    }
