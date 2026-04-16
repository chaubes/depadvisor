"""
Node: fetch_vulnerabilities

Queries OSV.dev for known vulnerabilities affecting each dependency.
Uses the batch API for efficiency.
"""

from depadvisor.agent.state import DepAdvisorState
from depadvisor.clients.osv import OSVClient


async def fetch_vulnerabilities_node(state: DepAdvisorState) -> dict:
    """
    Fetch vulnerability data for all dependencies using OSV batch API.

    Reads: state['dependencies']
    Writes: state['vulnerabilities'], state['current_node']
    """
    dependencies = state.get("dependencies", [])
    errors = list(state.get("errors", []))

    if not dependencies:
        return {"vulnerabilities": [], "current_node": "fetch_vulns", "errors": errors}

    packages = [(dep.name, dep.current_version, dep.ecosystem) for dep in dependencies if dep.current_version]

    if not packages:
        return {"vulnerabilities": [], "current_node": "fetch_vulns", "errors": errors}

    client = OSVClient()
    try:
        vulnerabilities = await client.query_batch(packages)
    except Exception as e:
        errors.append(f"Error fetching vulnerabilities: {e}")
        vulnerabilities = []
    finally:
        await client.close()

    return {
        "vulnerabilities": vulnerabilities,
        "current_node": "fetch_vulns",
        "errors": errors,
    }
