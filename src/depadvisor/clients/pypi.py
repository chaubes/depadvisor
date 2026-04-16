"""
PyPI (Python Package Index) API client.

Uses the public JSON API: https://pypi.org/pypi/{package}/json
No authentication required.
"""

from datetime import UTC, datetime

import httpx

from depadvisor.clients.base import BaseRegistryClient
from depadvisor.models.schemas import DependencyInfo, Ecosystem, UpdateCandidate
from depadvisor.utils.version import count_versions_between, find_latest_in_range, parse_version


class PyPIClient(BaseRegistryClient):
    """Client for the PyPI JSON API."""

    BASE_URL = "https://pypi.org/pypi"

    def __init__(self, timeout: float = 30.0):
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self):
        await self._client.aclose()

    async def get_package_info(self, package_name: str) -> dict | None:
        """Fetch package metadata from PyPI."""
        try:
            response = await self._client.get(f"{self.BASE_URL}/{package_name}/json")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def get_update_candidates(self, dependency: DependencyInfo) -> UpdateCandidate | None:
        """Check PyPI for available updates."""
        if dependency.ecosystem != Ecosystem.PYTHON:
            return None

        data = await self.get_package_info(dependency.name)
        if data is None:
            return None

        # Get all version strings
        all_versions = list(data.get("releases", {}).keys())

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

        # If no updates available, return None
        if latest_version is None:
            return None

        # Calculate days since releases
        info = data.get("info", {})
        releases = data.get("releases", {})

        current_date = self._get_release_date(releases, dependency.current_version)
        latest_date = self._get_release_date(releases, latest_version)

        now = datetime.now(UTC)
        days_since_current = (now - current_date).days if current_date else None
        days_since_latest = (now - latest_date).days if latest_date else None

        # Get repository URL
        repo_url = (
            info.get("project_urls", {}).get("Source")
            or info.get("project_urls", {}).get("Repository")
            or info.get("project_urls", {}).get("Homepage")
            or info.get("home_page")
        )

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

    def _get_release_date(self, releases: dict, version: str) -> datetime | None:
        """Extract the release date for a specific version."""
        version_files = releases.get(version, [])
        if not version_files:
            return None
        # Use the upload time of the first file
        upload_time = version_files[0].get("upload_time_iso_8601")
        if upload_time:
            return datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
        return None
