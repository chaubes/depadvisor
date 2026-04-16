"""Unit tests for the Java/Maven dependency parser."""

from pathlib import Path

import pytest

from depadvisor.models.schemas import Ecosystem
from depadvisor.parsers.java import JavaParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "java"


class TestJavaParser:
    def setup_method(self):
        self.parser = JavaParser()

    def test_can_parse_pom_xml(self):
        assert self.parser.can_parse("pom.xml") is True
        assert self.parser.can_parse("package.json") is False
        assert self.parser.can_parse("requirements.txt") is False

    def test_parse_simple_pom(self):
        deps = self.parser.parse(str(FIXTURES / "pom_simple.xml"))

        assert len(deps) == 3

        # Check dependency with property-resolved version
        spring = next(d for d in deps if "spring-core" in d.name)
        assert spring.name == "org.springframework:spring-core"
        assert spring.current_version == "5.3.20"
        assert spring.ecosystem == Ecosystem.JAVA
        assert spring.is_dev_dependency is False

        # Check regular dependency
        guava = next(d for d in deps if "guava" in d.name)
        assert guava.name == "com.google.guava:guava"
        assert guava.current_version == "32.1.3-jre"

        # Check test-scoped dependency
        junit = next(d for d in deps if "junit" in d.name)
        assert junit.name == "junit:junit"
        assert junit.current_version == "4.13.2"
        assert junit.is_dev_dependency is True

    def test_parse_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse("/nonexistent/pom.xml")

    def test_property_resolution(self):
        """Verify that ${property} references are resolved."""
        deps = self.parser.parse(str(FIXTURES / "pom_simple.xml"))
        spring = next(d for d in deps if "spring-core" in d.name)
        # ${spring.version} should be resolved to 5.3.20
        assert spring.current_version == "5.3.20"
        # version_constraint should store the raw property reference
        assert spring.version_constraint == "${spring.version}"
