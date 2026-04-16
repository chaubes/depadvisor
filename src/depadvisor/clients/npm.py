"""
npm Registry API client.

Uses the public registry: https://registry.npmjs.org/{package}
No authentication required.
"""

from datetime import UTC, datetime

import httpx

from depadvisor.clients.base import BaseRegistryClient
from depadvisor.models.schemas import DependencyInfo, Ecosystem, UpdateCandidate
from depadvisor.utils.version import count_versions_between, find_latest_in_range, parse_version


class NpmClient(BaseRegistryClient):
    """Client for the npm Registry API."""

    BASE_URL = "https://registry.npmjs.org"

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def get_package_info(self, package_name: str) -> dict | None:
        """Fetch package metadata from the npm registry."""
        try:
            response = await self._client.get(f"{self.BASE_URL}/{package_name}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def get_update_candidates(self, dependency: DependencyInfo) -> UpdateCandidate | None:
        """Check npm for available updates."""
        if dependency.ecosystem != Ecosystem.NODE:
            return None

        data = await self.get_package_info(dependency.name)
        if data is None:
            return None

        # Get all version strings from the "versions" dict
        all_versions = list(data.get("versions", {}).keys())

        # Filter out pre-releases and invalid versions
        stable_versions = [
            v
            for v in all_versions
            if parse_version(v) is not None
            and not parse_version(v).is_prerelease
            and not parse_version(v).is_devrelease
        ]

        if not stable_versions or not dependency.current_version:
            return None

        # Find latest versions at different levels
        latest_version = find_latest_in_range(stable_versions, dependency.current_version, "major")
        latest_minor = find_latest_in_range(stable_versions, dependency.current_version, "minor")
        latest_patch = find_latest_in_range(stable_versions, dependency.current_version, "patch")

        if latest_version is None:
            return None

        # Calculate days since releases using the "time" field
        time_data = data.get("time", {})
        current_date = self._parse_date(time_data.get(dependency.current_version))
        latest_date = self._parse_date(time_data.get(latest_version))

        now = datetime.now(UTC)
        days_since_current = (now - current_date).days if current_date else None
        days_since_latest = (now - latest_date).days if latest_date else None

        # Get repository URL
        repo = data.get("repository", {})
        repo_url = None
        if isinstance(repo, dict):
            repo_url = repo.get("url", "")
            # Clean up git+https:// and .git suffix
            repo_url = repo_url.replace("git+", "").replace("git://", "https://")
            if repo_url.endswith(".git"):
                repo_url = repo_url[:-4]
            if not repo_url.startswith("http"):
                repo_url = None

        return UpdateCandidate(
            dependency=dependency,
            latest_version=latest_version,
            latest_patch=latest_patch,
            latest_minor=latest_minor,
            latest_major=latest_version,
            versions_behind=count_versions_between(stable_versions, dependency.current_version, latest_version),
            days_since_current_release=days_since_current,
            days_since_latest_release=days_since_latest,
            repository_url=repo_url,
        )

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse an ISO 8601 date string."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
