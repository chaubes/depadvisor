"""
GitHub Releases API client for fetching changelogs.

Uses the public API: https://api.github.com/repos/{owner}/{repo}/releases
Authentication optional but recommended for higher rate limits (60/hr -> 5000/hr).
"""

import os
import re
from datetime import datetime

import httpx

from depadvisor.models.schemas import ChangelogEntry, ChangelogSummary

# Keywords that indicate breaking changes in release notes
BREAKING_KEYWORDS = [
    "breaking change",
    "breaking:",
    "BREAKING",
    "backwards incompatible",
    "backward incompatible",
    "migration required",
    "migrate from",
    "removed",
    "deprecated and removed",
]


class GitHubClient:
    """Client for the GitHub Releases API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None, timeout: float = 30.0):
        self._token = token or os.environ.get("GITHUB_TOKEN")
        headers = {"Accept": "application/vnd.github+json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.AsyncClient(timeout=timeout, headers=headers)

    async def close(self):
        await self._client.aclose()

    async def get_releases(
        self, repo_url: str, since_version: str | None = None, max_entries: int = 10
    ) -> ChangelogSummary:
        """
        Fetch release notes from a GitHub repository.

        Args:
            repo_url: GitHub repository URL (e.g., https://github.com/pallets/flask)
            since_version: Only include releases newer than this version
            max_entries: Maximum number of entries to return
        """
        owner_repo = self._parse_repo_url(repo_url)
        if owner_repo is None:
            return ChangelogSummary(
                package_name=repo_url,
                entries=[],
                source="none",
            )

        owner, repo = owner_repo

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/repos/{owner}/{repo}/releases",
                params={"per_page": max_entries},
            )
            if response.status_code == 404:
                return ChangelogSummary(
                    package_name=f"{owner}/{repo}",
                    entries=[],
                    source="none",
                )
            if response.status_code == 403:
                # Rate limited
                return ChangelogSummary(
                    package_name=f"{owner}/{repo}",
                    entries=[],
                    source="none",
                    truncated=True,
                )
            response.raise_for_status()
            releases = response.json()
        except httpx.HTTPError:
            return ChangelogSummary(
                package_name=f"{owner}/{repo}",
                entries=[],
                source="none",
            )

        entries = []
        for release in releases:
            tag = release.get("tag_name", "")
            # Strip common prefixes from tag (v1.0.0 -> 1.0.0)
            version = re.sub(r"^v", "", tag)

            body = release.get("body", "") or ""
            # Truncate very long release notes
            if len(body) > 2000:
                body = body[:2000] + "\n... (truncated)"

            published = release.get("published_at")
            date = None
            if published:
                try:
                    date = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except ValueError:
                    pass

            is_breaking = self._detect_breaking_changes(body)

            entries.append(
                ChangelogEntry(
                    version=version,
                    date=date,
                    body=body,
                    is_breaking=is_breaking,
                    url=release.get("html_url"),
                )
            )

        return ChangelogSummary(
            package_name=f"{owner}/{repo}",
            entries=entries,
            source="github_releases",
            truncated=len(releases) >= max_entries,
        )

    def _parse_repo_url(self, url: str) -> tuple[str, str] | None:
        """
        Extract owner and repo from a GitHub URL.

        Handles:
        - https://github.com/owner/repo
        - https://github.com/owner/repo.git
        - git+https://github.com/owner/repo.git
        - github.com/owner/repo
        """
        # Clean up the URL
        url = url.replace("git+", "").rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]

        # Try to match github.com/owner/repo
        match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
        if match:
            return match.group(1), match.group(2)
        return None

    def _detect_breaking_changes(self, body: str) -> bool:
        """Check if release notes mention breaking changes."""
        body_lower = body.lower()
        return any(keyword.lower() in body_lower for keyword in BREAKING_KEYWORDS)
