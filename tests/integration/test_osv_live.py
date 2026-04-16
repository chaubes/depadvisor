"""
Integration tests for the OSV vulnerability client.

These tests make REAL API calls to OSV.dev.
Run with: make test-integration
"""

import pytest

from depadvisor.clients.osv import OSVClient
from depadvisor.models.schemas import Ecosystem


@pytest.fixture
async def osv_client():
    client = OSVClient()
    yield client
    await client.close()


class TestOSVClientLive:
    @pytest.mark.asyncio
    async def test_query_known_vulnerable_package(self, osv_client: OSVClient):
        """jinja2 3.1.2 has known vulnerabilities."""
        report = await osv_client.query_vulnerabilities(
            package_name="jinja2",
            version="3.1.2",
            ecosystem=Ecosystem.PYTHON,
        )
        assert report.package_name == "jinja2"
        assert report.current_version == "3.1.2"
        assert len(report.vulnerabilities) > 0

    @pytest.mark.asyncio
    async def test_query_clean_package(self, osv_client: OSVClient):
        """A recent version of a well-maintained package should have few/no vulns."""
        report = await osv_client.query_vulnerabilities(
            package_name="packaging",
            version="24.0",
            ecosystem=Ecosystem.PYTHON,
        )
        assert report.package_name == "packaging"
        # packaging 24.0 should have no known vulnerabilities
        assert len(report.vulnerabilities) == 0
