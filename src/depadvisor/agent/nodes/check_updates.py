"""
Node: check_updates

Queries package registry APIs to find available updates for each dependency.
"""

import asyncio

from depadvisor.agent.state import DepAdvisorState
from depadvisor.clients.maven import MavenClient
from depadvisor.clients.npm import NpmClient
from depadvisor.clients.pypi import PyPIClient
from depadvisor.models.schemas import Ecosystem, UpdateCandidate


async def check_updates_node(state: DepAdvisorState) -> dict:
    """
    Check package registries for available updates.

    Reads: state['dependencies'], state['ecosystem']
    Writes: state['updates'], state['current_node']
    """
    dependencies = state.get("dependencies", [])
    ecosystem = state["ecosystem"]
    errors = list(state.get("errors", []))

    if not dependencies:
        return {"updates": [], "current_node": "check_updates", "errors": errors}

    # Select the appropriate registry client
    client_map = {
        Ecosystem.PYTHON: PyPIClient,
        Ecosystem.NODE: NpmClient,
        Ecosystem.JAVA: MavenClient,
    }

    client_cls = client_map.get(ecosystem)
    if client_cls is None:
        errors.append(f"No registry client for ecosystem: {ecosystem}")
        return {"updates": [], "current_node": "check_updates", "errors": errors}

    client = client_cls()
    semaphore = asyncio.Semaphore(5)

    async def fetch_update(dep) -> UpdateCandidate | None:
        async with semaphore:
            try:
                return await client.get_update_candidates(dep)
            except Exception as e:
                errors.append(f"Error checking updates for {dep.name}: {e}")
                return None

    try:
        results = await asyncio.gather(*[fetch_update(dep) for dep in dependencies])
        updates = [r for r in results if r is not None]
    finally:
        await client.close()

    return {
        "updates": updates,
        "current_node": "check_updates",
        "errors": errors,
    }
