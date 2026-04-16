"""
Node: parse_dependencies

First node in the graph. Reads dependency files from the project
and populates state['dependencies'].

This node does NOT use the LLM — it's pure Python parsing.
"""

from pathlib import Path

from depadvisor.agent.state import DepAdvisorState
from depadvisor.models.schemas import Ecosystem
from depadvisor.parsers.java import JavaParser
from depadvisor.parsers.node import NodeParser
from depadvisor.parsers.python import PythonParser

# Registry of parsers by ecosystem
PARSERS = {
    Ecosystem.PYTHON: PythonParser(),
    Ecosystem.NODE: NodeParser(),
    Ecosystem.JAVA: JavaParser(),
}


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

    # Find all parseable files in the project directory
    dependencies = []
    for file_path in project_path.rglob("*"):
        if parser.can_parse(str(file_path)):
            try:
                deps = parser.parse(str(file_path))
                dependencies.extend(deps)
            except Exception as e:
                errors.append(f"Error parsing {file_path}: {e}")

    return {
        "dependencies": dependencies,
        "current_node": "parse_deps",
        "errors": errors,
    }
