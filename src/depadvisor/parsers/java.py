"""
Parser for Java/Maven dependency files.

Supports:
- pom.xml (Maven POM format)
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from depadvisor.models.schemas import DependencyInfo, Ecosystem
from depadvisor.parsers.base import BaseParser

# Maven POM namespace
MAVEN_NS = "{http://maven.apache.org/POM/4.0.0}"


class JavaParser(BaseParser):
    """Parses Java/Maven dependency files."""

    ecosystem = Ecosystem.JAVA

    def can_parse(self, file_path: str) -> bool:
        return Path(file_path).name.lower() == "pom.xml"

    def parse(self, file_path: str) -> list[DependencyInfo]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        tree = ET.parse(path)
        root = tree.getroot()

        # Detect namespace usage
        ns = MAVEN_NS if root.tag.startswith("{") else ""

        # Extract properties for variable resolution
        properties = self._extract_properties(root, ns)

        dependencies = []

        # Parse <dependencies> section
        deps_elem = root.find(f"{ns}dependencies")
        if deps_elem is not None:
            for dep_elem in deps_elem.findall(f"{ns}dependency"):
                dep = self._parse_dependency(dep_elem, ns, properties, str(path))
                if dep:
                    dependencies.append(dep)

        # Parse <dependencyManagement><dependencies> section
        dep_mgmt = root.find(f"{ns}dependencyManagement")
        if dep_mgmt is not None:
            mgmt_deps = dep_mgmt.find(f"{ns}dependencies")
            if mgmt_deps is not None:
                for dep_elem in mgmt_deps.findall(f"{ns}dependency"):
                    dep = self._parse_dependency(dep_elem, ns, properties, str(path))
                    if dep:
                        dependencies.append(dep)

        return dependencies

    def _extract_properties(self, root: ET.Element, ns: str) -> dict[str, str]:
        """Extract Maven properties for ${variable} resolution."""
        properties = {}
        props_elem = root.find(f"{ns}properties")
        if props_elem is not None:
            for prop in props_elem:
                # Strip namespace from tag name
                tag = prop.tag.replace(ns, "")
                if prop.text:
                    properties[tag] = prop.text.strip()
        return properties

    def _resolve_property(self, value: str | None, properties: dict[str, str]) -> str | None:
        """Resolve Maven property references like ${spring.version}."""
        if value is None:
            return None

        def replace_prop(match: re.Match) -> str:
            prop_name = match.group(1)
            return properties.get(prop_name, match.group(0))

        resolved = re.sub(r"\$\{(.+?)}", replace_prop, value)
        # If still contains unresolved properties, return None
        if "${" in resolved:
            return None
        return resolved

    def _parse_dependency(
        self, elem: ET.Element, ns: str, properties: dict[str, str], source_file: str
    ) -> DependencyInfo | None:
        """Parse a single <dependency> element."""
        group_id_elem = elem.find(f"{ns}groupId")
        artifact_id_elem = elem.find(f"{ns}artifactId")

        if group_id_elem is None or artifact_id_elem is None:
            return None

        group_id = group_id_elem.text
        artifact_id = artifact_id_elem.text
        if not group_id or not artifact_id:
            return None

        # Resolve properties in groupId and artifactId
        group_id = self._resolve_property(group_id, properties) or group_id
        artifact_id = self._resolve_property(artifact_id, properties) or artifact_id

        # Maven coordinate as name
        name = f"{group_id}:{artifact_id}"

        # Version (may be absent if managed by parent or BOM)
        version_elem = elem.find(f"{ns}version")
        raw_version = version_elem.text.strip() if version_elem is not None and version_elem.text else None
        current_version = self._resolve_property(raw_version, properties)

        # Scope
        scope_elem = elem.find(f"{ns}scope")
        scope = scope_elem.text.strip().lower() if scope_elem is not None and scope_elem.text else "compile"
        is_dev = scope in ("test", "provided")

        return DependencyInfo(
            name=name,
            current_version=current_version,
            version_constraint=raw_version if raw_version != current_version else None,
            ecosystem=Ecosystem.JAVA,
            is_dev_dependency=is_dev,
            source_file=source_file,
        )
