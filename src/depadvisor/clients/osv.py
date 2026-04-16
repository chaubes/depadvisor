"""
OSV.dev vulnerability database client.

OSV (Open Source Vulnerabilities) is Google's aggregated vulnerability database.
API docs: https://osv.dev/docs/

No authentication required.
"""

from datetime import datetime

import httpx

from depadvisor.models.schemas import Ecosystem, Severity, VulnerabilityInfo, VulnerabilityReport

# Map OSV ecosystem names to our Ecosystem enum
ECOSYSTEM_MAP = {
    Ecosystem.PYTHON: "PyPI",
    Ecosystem.NODE: "npm",
    Ecosystem.JAVA: "Maven",
}


class OSVClient:
    """Client for the OSV.dev API."""

    BASE_URL = "https://api.osv.dev/v1"

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def query_vulnerabilities(
        self,
        package_name: str,
        version: str,
        ecosystem: Ecosystem,
    ) -> VulnerabilityReport:
        """
        Query OSV for known vulnerabilities affecting a specific package version.
        """
        osv_ecosystem = ECOSYSTEM_MAP.get(ecosystem)
        if not osv_ecosystem:
            return VulnerabilityReport(
                package_name=package_name,
                ecosystem=ecosystem,
                current_version=version,
            )

        try:
            response = await self._client.post(
                f"{self.BASE_URL}/query",
                json={
                    "version": version,
                    "package": {
                        "name": package_name,
                        "ecosystem": osv_ecosystem,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError:
            return VulnerabilityReport(
                package_name=package_name,
                ecosystem=ecosystem,
                current_version=version,
            )

        vulnerabilities = []
        for vuln in data.get("vulns", []):
            severity = self._extract_severity(vuln)
            fixed_version = self._extract_fixed_version(vuln, osv_ecosystem)

            vulnerabilities.append(
                VulnerabilityInfo(
                    cve_id=self._extract_cve_id(vuln),
                    osv_id=vuln.get("id"),
                    summary=vuln.get("summary", "No description available"),
                    severity=severity,
                    affected_versions=self._format_affected(vuln),
                    fixed_version=fixed_version,
                    published_date=self._parse_date(vuln.get("published")),
                    url=f"https://osv.dev/vulnerability/{vuln.get('id', '')}",
                )
            )

        return VulnerabilityReport(
            package_name=package_name,
            ecosystem=ecosystem,
            current_version=version,
            vulnerabilities=vulnerabilities,
        )

    def _extract_severity(self, vuln: dict) -> Severity:
        """Extract severity from OSV vulnerability data."""
        # Fall back to database_specific severity
        db_specific = vuln.get("database_specific", {})
        severity_str = db_specific.get("severity", "").upper()

        severity_map = {
            "CRITICAL": Severity.CRITICAL,
            "HIGH": Severity.HIGH,
            "MODERATE": Severity.MEDIUM,
            "MEDIUM": Severity.MEDIUM,
            "LOW": Severity.LOW,
        }
        return severity_map.get(severity_str, Severity.UNKNOWN)

    def _extract_cve_id(self, vuln: dict) -> str | None:
        """Extract CVE ID from aliases."""
        for alias in vuln.get("aliases", []):
            if alias.startswith("CVE-"):
                return alias
        return None

    def _extract_fixed_version(self, vuln: dict, ecosystem: str) -> str | None:
        """Extract the fix version from affected ranges."""
        for affected in vuln.get("affected", []):
            if affected.get("package", {}).get("ecosystem") != ecosystem:
                continue
            for range_entry in affected.get("ranges", []):
                for event in range_entry.get("events", []):
                    if "fixed" in event:
                        return event["fixed"]
        return None

    def _format_affected(self, vuln: dict) -> str:
        """Format affected version ranges as a readable string."""
        ranges = []
        for affected in vuln.get("affected", []):
            for range_entry in affected.get("ranges", []):
                introduced = None
                fixed = None
                for event in range_entry.get("events", []):
                    if "introduced" in event:
                        introduced = event["introduced"]
                    if "fixed" in event:
                        fixed = event["fixed"]
                if introduced and fixed:
                    ranges.append(f">={introduced}, <{fixed}")
                elif introduced:
                    ranges.append(f">={introduced}")
        return " | ".join(ranges) if ranges else "unknown"

    def _parse_date(self, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
