"""
Parser for Node.js dependency files.

Supports:
- package.json (dependencies and devDependencies)
"""

import json
import re
from pathlib import Path

from depadvisor.models.schemas import DependencyInfo, Ecosystem
from depadvisor.parsers.base import BaseParser


class NodeParser(BaseParser):
    """Parses Node.js dependency files."""

    ecosystem = Ecosystem.NODE

    def can_parse(self, file_path: str) -> bool:
        return Path(file_path).name.lower() == "package.json"

    def parse(self, file_path: str) -> list[DependencyInfo]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path) as f:
            data = json.load(f)

        dependencies = []

        for name, version_spec in data.get("dependencies", {}).items():
            dep = self._parse_dep(name, version_spec, str(path), is_dev=False)
            if dep:
                dependencies.append(dep)

        for name, version_spec in data.get("devDependencies", {}).items():
            dep = self._parse_dep(name, version_spec, str(path), is_dev=True)
            if dep:
                dependencies.append(dep)

        return dependencies

    def _parse_dep(self, name: str, version_spec: str, source_file: str, is_dev: bool) -> DependencyInfo | None:
        """Parse a single dependency entry from package.json."""
        # Skip non-version specs (git URLs, file paths, etc.)
        if version_spec.startswith(("git+", "git://", "http", "file:", "/", "./")):
            return None

        current_version = self._extract_version(version_spec)

        return DependencyInfo(
            name=name,
            current_version=current_version,
            version_constraint=version_spec if version_spec != current_version else None,
            ecosystem=Ecosystem.NODE,
            is_dev_dependency=is_dev,
            source_file=source_file,
        )

    def _extract_version(self, version_spec: str) -> str | None:
        """
        Extract the base version from a npm version spec.

        Handles: ^1.2.3, ~1.2.3, >=1.2.3, 1.2.3, *, latest, 1.x, 1.2.x
        """
        if version_spec in ("*", "latest", ""):
            return None

        # Strip range prefixes: ^, ~, >=, <=, >, <, =
        match = re.match(r"[~^>=<]*\s*([\d]+\.[\d]+\.[\d]+(?:-[\w.]+)?)", version_spec)
        if match:
            return match.group(1)

        # Handle partial versions like "1" or "1.2"
        match = re.match(r"[~^>=<]*\s*([\d]+(?:\.[\d]+)?)", version_spec)
        if match and "x" not in version_spec.lower():
            return match.group(1)

        return None
