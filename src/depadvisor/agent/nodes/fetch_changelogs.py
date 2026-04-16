"""
Node: fetch_changelogs

Fetches changelog/release notes from GitHub for dependencies with updates.
"""

import asyncio

from depadvisor.agent.state import DepAdvisorState
from depadvisor.clients.github import GitHubClient
from depadvisor.models.schemas import ChangelogSummary


async def fetch_changelogs_node(state: DepAdvisorState) -> dict:
    """
    Fetch changelogs for dependencies that have available updates.

    Reads: state['updates']
    Writes: state['changelogs'], state['current_node']
    """
    updates = state.get("updates", [])
    errors = list(state.get("errors", []))

    if not updates:
        return {"changelogs": [], "current_node": "fetch_changelogs", "errors": errors}

    client = GitHubClient()
    semaphore = asyncio.Semaphore(3)  # Lower concurrency for GitHub rate limits

    async def fetch_changelog(update) -> ChangelogSummary:
        if not update.repository_url:
            return ChangelogSummary(
                package_name=update.dependency.name,
                entries=[],
                source="none",
            )
        async with semaphore:
            try:
                return await client.get_releases(
                    repo_url=update.repository_url,
                    since_version=update.dependency.current_version,
                    max_entries=5,
                )
            except Exception as e:
                errors.append(f"Error fetching changelog for {update.dependency.name}: {e}")
                return ChangelogSummary(
                    package_name=update.dependency.name,
                    entries=[],
                    source="none",
                )

    try:
        changelogs = await asyncio.gather(*[fetch_changelog(u) for u in updates])
    finally:
        await client.close()

    return {
        "changelogs": list(changelogs),
        "current_node": "fetch_changelogs",
        "errors": errors,
    }
