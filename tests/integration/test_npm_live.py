"""
Integration tests for the npm client.

These tests make REAL API calls to the npm registry.
Run with: make test-integration
"""

import pytest

from depadvisor.clients.npm import NpmClient
from depadvisor.models.schemas import DependencyInfo, Ecosystem


@pytest.fixture
async def npm_client():
    client = NpmClient()
    yield client
    await client.close()


class TestNpmClientLive:
    @pytest.mark.asyncio
    async def test_get_express_info(self, npm_client: NpmClient):
        """Express is a well-known package — this should always work."""
        info = await npm_client.get_package_info("express")
        assert info is not None
        assert "versions" in info
        assert info["name"] == "express"

    @pytest.mark.asyncio
    async def test_get_nonexistent_package(self, npm_client: NpmClient):
        info = await npm_client.get_package_info("this-package-definitely-does-not-exist-12345")
        assert info is None

    @pytest.mark.asyncio
    async def test_get_update_candidates(self, npm_client: NpmClient):
        """Check for updates to an old version of express."""
        dep = DependencyInfo(
            name="express",
            current_version="4.17.0",
            ecosystem=Ecosystem.NODE,
            source_file="package.json",
        )
        update = await npm_client.get_update_candidates(dep)
        assert update is not None
        assert update.latest_version is not None
        assert update.versions_behind > 0
