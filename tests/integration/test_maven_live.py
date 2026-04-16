"""
Integration tests for the Maven Central client.

These tests make REAL API calls to Maven Central.
Run with: make test-integration
"""

import pytest

from depadvisor.clients.maven import MavenClient
from depadvisor.models.schemas import DependencyInfo, Ecosystem


@pytest.fixture
async def maven_client():
    client = MavenClient()
    yield client
    await client.close()


class TestMavenClientLive:
    @pytest.mark.asyncio
    async def test_get_junit_versions(self, maven_client: MavenClient):
        """junit:junit is a well-known artifact."""
        docs = await maven_client.get_package_versions("junit", "junit")
        assert docs is not None
        assert len(docs) > 0
        versions = [d["v"] for d in docs]
        assert "4.13.2" in versions

    @pytest.mark.asyncio
    async def test_get_nonexistent_package(self, maven_client: MavenClient):
        docs = await maven_client.get_package_versions("com.nonexistent.fake", "does-not-exist-12345")
        assert docs is None

    @pytest.mark.asyncio
    async def test_get_update_candidates(self, maven_client: MavenClient):
        """Check for updates to an old version of junit."""
        dep = DependencyInfo(
            name="junit:junit",
            current_version="4.12",
            ecosystem=Ecosystem.JAVA,
            source_file="pom.xml",
        )
        update = await maven_client.get_update_candidates(dep)
        assert update is not None
        assert update.latest_version is not None
        assert update.versions_behind > 0
