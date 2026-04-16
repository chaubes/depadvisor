"""
Node: fetch_vulnerabilities

Queries OSV.dev for known vulnerabilities affecting each dependency.
"""

import asyncio

from depadvisor.agent.state import DepAdvisorState
from depadvisor.clients.osv import OSVClient
from depadvisor.models.schemas import VulnerabilityReport


async def fetch_vulnerabilities_node(state: DepAdvisorState) -> dict:
    """
    Fetch vulnerability data for all dependencies.

    Reads: state['dependencies']
    Writes: state['vulnerabilities'], state['current_node']
    """
    dependencies = state.get("dependencies", [])
    errors = list(state.get("errors", []))

    if not dependencies:
        return {"vulnerabilities": [], "current_node": "fetch_vulns", "errors": errors}

    client = OSVClient()
    semaphore = asyncio.Semaphore(5)

    async def fetch_vuln(dep) -> VulnerabilityReport | None:
        if not dep.current_version:
            return None
        async with semaphore:
            try:
                return await client.query_vulnerabilities(
                    package_name=dep.name,
                    version=dep.current_version,
                    ecosystem=dep.ecosystem,
                )
            except Exception as e:
                errors.append(f"Error fetching vulnerabilities for {dep.name}: {e}")
                return None

    try:
        results = await asyncio.gather(*[fetch_vuln(dep) for dep in dependencies])
        vulnerabilities = [r for r in results if r is not None]
    finally:
        await client.close()

    return {
        "vulnerabilities": vulnerabilities,
        "current_node": "fetch_vulns",
        "errors": errors,
    }
