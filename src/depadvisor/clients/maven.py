"""
Maven Central Search API client.

Uses the public search API: https://search.maven.org/solrsearch/select
No authentication required.
"""

from datetime import UTC, datetime

import httpx

from depadvisor.clients.base import BaseRegistryClient
from depadvisor.models.schemas import DependencyInfo, Ecosystem, UpdateCandidate
from depadvisor.utils.version import count_versions_between, find_latest_in_range, parse_version


class MavenClient(BaseRegistryClient):
    """Client for the Maven Central Search API."""

    BASE_URL = "https://search.maven.org/solrsearch/select"

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def get_package_versions(self, group_id: str, artifact_id: str) -> list[dict] | None:
        """Fetch all versions of an artifact from Maven Central."""
        try:
            response = await self._client.get(
                self.BASE_URL,
                params={
                    "q": f"g:{group_id} AND a:{artifact_id}",
                    "core": "gav",
                    "rows": 200,
                    "wt": "json",
                },
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            docs = data.get("response", {}).get("docs", [])
            return docs if docs else None
        except httpx.HTTPError:
            return None

    async def get_update_candidates(self, dependency: DependencyInfo) -> UpdateCandidate | None:
        """Check Maven Central for available updates."""
        if dependency.ecosystem != Ecosystem.JAVA:
            return None

        # Split name into groupId:artifactId
        parts = dependency.name.split(":", 1)
        if len(parts) != 2:
            return None
        group_id, artifact_id = parts

        docs = await self.get_package_versions(group_id, artifact_id)
        if docs is None:
            return None

        # Extract version strings
        all_versions = [doc.get("v", "") for doc in docs if doc.get("v")]

        # Filter stable versions (parse_version returns None for unparseable versions)
        stable_versions = [
            v
            for v in all_versions
            if parse_version(v) is not None
            and not parse_version(v).is_prerelease
            and not parse_version(v).is_devrelease
        ]

        if not stable_versions or not dependency.current_version:
            return None

        # If current version isn't parseable by packaging, we can't compare
        if parse_version(dependency.current_version) is None:
            return None

        latest_version = find_latest_in_range(stable_versions, dependency.current_version, "major")
        latest_minor = find_latest_in_range(stable_versions, dependency.current_version, "minor")
        latest_patch = find_latest_in_range(stable_versions, dependency.current_version, "patch")

        if latest_version is None:
            return None

        # Calculate days since releases from timestamps
        version_timestamps = {doc["v"]: doc.get("timestamp") for doc in docs if doc.get("v")}
        current_date = self._timestamp_to_datetime(version_timestamps.get(dependency.current_version))
        latest_date = self._timestamp_to_datetime(version_timestamps.get(latest_version))

        now = datetime.now(UTC)
        days_since_current = (now - current_date).days if current_date else None
        days_since_latest = (now - latest_date).days if latest_date else None

        return UpdateCandidate(
            dependency=dependency,
            latest_version=latest_version,
            latest_patch=latest_patch,
            latest_minor=latest_minor,
            latest_major=latest_version,
            versions_behind=count_versions_between(stable_versions, dependency.current_version, latest_version),
            days_since_current_release=days_since_current,
            days_since_latest_release=days_since_latest,
            repository_url=None,  # Maven Central doesn't reliably provide repo URLs
        )

    def _timestamp_to_datetime(self, timestamp_ms: int | None) -> datetime | None:
        """Convert a Maven Central timestamp (milliseconds) to datetime."""
        if timestamp_ms is None:
            return None
        try:
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
        except (ValueError, OSError):
            return None
