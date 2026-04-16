"""
Unit tests for the Python dependency parser.

These tests verify that our parser correctly extracts dependency
information from various Python dependency file formats.

No network access needed — we test against fixture files.
"""

from pathlib import Path

import pytest

from depadvisor.models.schemas import Ecosystem
from depadvisor.parsers.python import PythonParser

# Path to test fixtures
FIXTURES = Path(__file__).parent.parent / "fixtures" / "python"


class TestPythonParserRequirementsTxt:
    """Tests for requirements.txt parsing."""

    def setup_method(self):
        """Create a fresh parser for each test."""
        self.parser = PythonParser()

    def test_can_parse_requirements_txt(self):
        assert self.parser.can_parse("requirements.txt") is True
        assert self.parser.can_parse("requirements-dev.txt") is True
        assert self.parser.can_parse("package.json") is False

    def test_parse_simple_requirements(self):
        deps = self.parser.parse(str(FIXTURES / "requirements_simple.txt"))

        # Should find 6 dependencies (not the comment or blank lines)
        assert len(deps) == 6

        # Check that flask was parsed correctly
        flask = next(d for d in deps if d.name == "flask")
        assert flask.current_version == "3.0.0"
        assert flask.ecosystem == Ecosystem.PYTHON

        # Check that pydantic has a range constraint but no exact version
        pydantic = next(d for d in deps if d.name == "pydantic")
        assert pydantic.current_version is None
        assert pydantic.version_constraint == ">=2.0,<3.0"

        # Check that 'black' is unpinned
        black = next(d for d in deps if d.name == "black")
        assert black.current_version is None
        assert black.version_constraint is None

    def test_parse_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse("/nonexistent/requirements.txt")


class TestPythonParserPyprojectToml:
    """Tests for pyproject.toml parsing."""

    def setup_method(self):
        self.parser = PythonParser()

    def test_parse_pep621_format(self):
        deps = self.parser.parse(str(FIXTURES / "pyproject_pep621.toml"))

        # 3 main deps + 2 dev deps = 5 total
        assert len(deps) == 5

        # Check main dependency
        flask = next(d for d in deps if d.name == "flask")
        assert flask.current_version == "3.0.0"
        assert flask.is_dev_dependency is False

        # Check dev dependency
        pytest_dep = next(d for d in deps if d.name == "pytest")
        assert pytest_dep.is_dev_dependency is True
