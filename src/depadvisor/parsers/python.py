"""
Parser for Python dependency files.

Supports:
- requirements.txt (pip format)
- pyproject.toml (PEP 621 and Poetry formats)
"""

import re
from pathlib import Path

from depadvisor.models.schemas import DependencyInfo, Ecosystem
from depadvisor.parsers.base import BaseParser


class PythonParser(BaseParser):
    """Parses Python dependency files."""

    ecosystem = Ecosystem.PYTHON

    def can_parse(self, file_path: str) -> bool:
        name = Path(file_path).name.lower()
        return name in ("requirements.txt", "pyproject.toml", "pipfile") or name.startswith("requirements")

    def parse(self, file_path: str) -> list[DependencyInfo]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        name = path.name.lower()

        if name.startswith("requirements") and name.endswith(".txt"):
            return self._parse_requirements_txt(path)
        elif name.endswith(".toml"):
            return self._parse_pyproject_toml(path)
        else:
            raise ValueError(f"Unsupported Python dependency file: {name}")

    def _parse_requirements_txt(self, path: Path) -> list[DependencyInfo]:
        """
        Parse requirements.txt format.

        Handles:
        - Pinned: flask==3.0.0
        - Ranges: flask>=2.0,<3.0
        - Unpinned: flask
        - Comments: # this is a comment
        - Blank lines
        - Extras: flask[async]==3.0.0
        - Line continuations: flask \\ (next line) ==3.0.0
        """
        dependencies = []
        content = path.read_text()

        # Join line continuations
        content = content.replace("\\\n", "")

        for line in content.splitlines():
            line = line.strip()

            # Skip comments, blank lines, options (-r, -i, -f, etc.)
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            # Skip URLs (git+https://, https://)
            if "://" in line:
                continue

            dep = self._parse_requirement_line(line, str(path))
            if dep:
                dependencies.append(dep)

        return dependencies

    def _parse_requirement_line(self, line: str, source_file: str) -> DependencyInfo | None:
        """Parse a single line from requirements.txt."""
        # Remove inline comments
        line = line.split("#")[0].strip()
        if not line:
            return None

        # Remove environment markers (e.g., ; python_version >= "3.8")
        line = line.split(";")[0].strip()

        # Remove extras (e.g., flask[async])
        name_part = re.split(r"[><=!~\[]", line)[0].strip()
        if not name_part:
            return None

        # Extract version constraint
        version_constraint = line[len(name_part) :].strip()
        # Remove extras bracket from constraint if present
        version_constraint = re.sub(r"\[.*?\]", "", version_constraint).strip()

        # Extract exact pinned version if available
        current_version = None
        exact_match = re.search(r"==\s*([\w.]+)", version_constraint)
        if exact_match:
            current_version = exact_match.group(1)

        return DependencyInfo(
            name=name_part.lower(),  # Normalize to lowercase
            current_version=current_version,
            version_constraint=version_constraint or None,
            ecosystem=Ecosystem.PYTHON,
            is_dev_dependency=False,
            source_file=source_file,
        )

    def _parse_pyproject_toml(self, path: Path) -> list[DependencyInfo]:
        """
        Parse pyproject.toml format.

        Supports:
        - PEP 621: [project.dependencies] and [project.optional-dependencies]
        - Poetry: [tool.poetry.dependencies] and [tool.poetry.group.dev.dependencies]
        """
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            import tomli as tomllib  # Fallback for older Python

        with open(path, "rb") as f:
            data = tomllib.load(f)

        dependencies = []

        # PEP 621 format: [project]
        project = data.get("project", {})
        for dep_str in project.get("dependencies", []):
            dep = self._parse_requirement_line(dep_str, str(path))
            if dep:
                dependencies.append(dep)

        # PEP 621 optional deps
        for group_deps in project.get("optional-dependencies", {}).values():
            for dep_str in group_deps:
                dep = self._parse_requirement_line(dep_str, str(path))
                if dep:
                    dep.is_dev_dependency = True
                    dependencies.append(dep)

        # Poetry format: [tool.poetry.dependencies]
        poetry = data.get("tool", {}).get("poetry", {})
        for name, spec in poetry.get("dependencies", {}).items():
            if name.lower() == "python":
                continue  # Skip python version constraint
            dep = self._parse_poetry_dep(name, spec, str(path), is_dev=False)
            if dep:
                dependencies.append(dep)

        # Poetry dev deps
        for group_name, group in poetry.get("group", {}).items():
            for name, spec in group.get("dependencies", {}).items():
                dep = self._parse_poetry_dep(name, spec, str(path), is_dev=True)
                if dep:
                    dependencies.append(dep)

        return dependencies

    def _parse_poetry_dep(self, name: str, spec: str | dict, source_file: str, is_dev: bool) -> DependencyInfo | None:
        """Parse a Poetry dependency entry."""
        if isinstance(spec, str):
            # Simple version: "flask" = "^3.0"
            version_constraint = spec
            # Try to extract exact version (^3.0.0 → 3.0.0)
            exact = re.match(r"[\^~]?([\d.]+)", spec)
            current_version = exact.group(1) if exact else None
        elif isinstance(spec, dict):
            # Complex: "flask" = {version = "^3.0", extras = ["async"]}
            version_constraint = spec.get("version", "")
            exact = re.match(r"[\^~]?([\d.]+)", version_constraint) if version_constraint else None
            current_version = exact.group(1) if exact else None
        else:
            return None

        return DependencyInfo(
            name=name.lower(),
            current_version=current_version,
            version_constraint=version_constraint or None,
            ecosystem=Ecosystem.PYTHON,
            is_dev_dependency=is_dev,
            source_file=source_file,
        )
