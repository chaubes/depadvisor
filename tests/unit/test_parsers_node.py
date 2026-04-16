"""Unit tests for the Node.js dependency parser."""

from pathlib import Path

import pytest

from depadvisor.models.schemas import Ecosystem
from depadvisor.parsers.node import NodeParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "node"


class TestNodeParser:
    def setup_method(self):
        self.parser = NodeParser()

    def test_can_parse_package_json(self):
        assert self.parser.can_parse("package.json") is True
        assert self.parser.can_parse("requirements.txt") is False
        assert self.parser.can_parse("pom.xml") is False

    def test_parse_simple_package_json(self):
        deps = self.parser.parse(str(FIXTURES / "package_simple.json"))

        # 3 deps + 2 devDeps = 5 total
        assert len(deps) == 5

        # Check a regular dependency
        express = next(d for d in deps if d.name == "express")
        assert express.current_version == "4.18.2"
        assert express.ecosystem == Ecosystem.NODE
        assert express.is_dev_dependency is False

        # Check exact pinned version
        lodash = next(d for d in deps if d.name == "lodash")
        assert lodash.current_version == "4.17.21"

        # Check tilde range
        axios = next(d for d in deps if d.name == "axios")
        assert axios.current_version == "1.6.0"

        # Check dev dependency
        jest = next(d for d in deps if d.name == "jest")
        assert jest.is_dev_dependency is True
        assert jest.current_version == "29.0.0"

        eslint = next(d for d in deps if d.name == "eslint")
        assert eslint.is_dev_dependency is True

    def test_parse_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse("/nonexistent/package.json")

    def test_extract_version_star(self):
        assert self.parser._extract_version("*") is None

    def test_extract_version_latest(self):
        assert self.parser._extract_version("latest") is None

    def test_extract_version_caret(self):
        assert self.parser._extract_version("^1.2.3") == "1.2.3"

    def test_extract_version_tilde(self):
        assert self.parser._extract_version("~1.2.3") == "1.2.3"

    def test_extract_version_exact(self):
        assert self.parser._extract_version("1.2.3") == "1.2.3"
