"""
Integration tests for the GitHub Releases client.

These tests make REAL API calls to GitHub.
Run with: make test-integration

Note: Without GITHUB_TOKEN, rate limit is 60 requests/hour.
"""

import pytest

from depadvisor.clients.github import GitHubClient


@pytest.fixture
async def github_client():
    client = GitHubClient()
    yield client
    await client.close()


class TestGitHubClientLive:
    @pytest.mark.asyncio
    async def test_get_flask_releases(self, github_client: GitHubClient):
        """Fetch releases for pallets/flask."""
        summary = await github_client.get_releases("https://github.com/pallets/flask", max_entries=5)
        assert summary.source == "github_releases"
        assert len(summary.entries) > 0
        # Each entry should have a version
        for entry in summary.entries:
            assert entry.version

    @pytest.mark.asyncio
    async def test_nonexistent_repo(self, github_client: GitHubClient):
        """A nonexistent repo should return empty entries."""
        summary = await github_client.get_releases("https://github.com/nonexistent-user-12345/nonexistent-repo-12345")
        assert len(summary.entries) == 0
        assert summary.source == "none"

    @pytest.mark.asyncio
    async def test_parse_repo_url_variants(self, github_client: GitHubClient):
        """Test URL parsing with different formats."""
        assert github_client._parse_repo_url("https://github.com/pallets/flask") == ("pallets", "flask")
        assert github_client._parse_repo_url("https://github.com/pallets/flask.git") == ("pallets", "flask")
        assert github_client._parse_repo_url("git+https://github.com/pallets/flask.git") == ("pallets", "flask")
        assert github_client._parse_repo_url("not-a-github-url") is None
