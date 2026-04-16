"""
Integration tests for the PyPI client.

These tests make REAL API calls to PyPI.
Run with: make test-integration
"""

import pytest

from depadvisor.clients.pypi import PyPIClient
from depadvisor.models.schemas import DependencyInfo, Ecosystem


@pytest.fixture
async def pypi_client():
    client = PyPIClient()
    yield client
    await client.close()


class TestPyPIClientLive:
    @pytest.mark.asyncio
    async def test_get_flask_info(self, pypi_client: PyPIClient):
        """Flask is a well-known package — this should always work."""
        info = await pypi_client.get_package_info("flask")
        assert info is not None
        assert "info" in info
        assert info["info"]["name"].lower() == "flask"

    @pytest.mark.asyncio
    async def test_get_nonexistent_package(self, pypi_client: PyPIClient):
        """A package that doesn't exist should return None."""
        info = await pypi_client.get_package_info("this-package-definitely-does-not-exist-12345")
        assert info is None

    @pytest.mark.asyncio
    async def test_get_update_candidates(self, pypi_client: PyPIClient):
        """Check for updates to an old version of flask."""
        dep = DependencyInfo(
            name="flask",
            current_version="2.0.0",  # Old version — updates should exist
            ecosystem=Ecosystem.PYTHON,
            source_file="requirements.txt",
        )
        update = await pypi_client.get_update_candidates(dep)
        assert update is not None
        assert update.latest_version is not None
        assert update.versions_behind > 0
