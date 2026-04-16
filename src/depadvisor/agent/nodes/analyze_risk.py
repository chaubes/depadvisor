"""
Node: analyze_risk

Uses the LLM to produce risk assessments for each dependency update.
"""

import json
import re

from depadvisor.agent.state import DepAdvisorState
from depadvisor.llm.prompts import RISK_ANALYSIS_PROMPT
from depadvisor.llm.provider import create_llm
from depadvisor.models.schemas import RiskAssessment, RiskLevel


def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract raw JSON from LLM response."""
    # Remove ```json ... ``` or ``` ... ``` blocks
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


async def analyze_risk_node(state: DepAdvisorState) -> dict:
    """
    Use LLM to analyze risk for each dependency update.

    Reads: state['updates'], state['vulnerabilities'], state['changelogs'],
           state['llm_provider'], state['ecosystem']
    Writes: state['risk_assessments'], state['current_node'], state['iteration']
    """
    updates = state.get("updates", [])
    vulnerabilities = state.get("vulnerabilities", [])
    changelogs = state.get("changelogs", [])
    llm_provider = state.get("llm_provider", "ollama/qwen3:8b")
    ecosystem = state["ecosystem"]
    errors = list(state.get("errors", []))
    iteration = state.get("iteration", 0) + 1

    if not updates:
        return {
            "risk_assessments": [],
            "current_node": "analyze_risk",
            "iteration": iteration,
            "errors": errors,
        }

    # Build lookup maps
    vuln_map = {v.package_name: v for v in vulnerabilities}
    changelog_map = {c.package_name: c for c in changelogs}

    # Format data for the prompt
    update_data = []
    for u in updates:
        update_data.append(
            {
                "package": u.dependency.name,
                "current_version": u.dependency.current_version,
                "latest_version": u.latest_version,
                "latest_patch": u.latest_patch,
                "latest_minor": u.latest_minor,
                "versions_behind": u.versions_behind,
                "days_since_current": u.days_since_current_release,
                "days_since_latest": u.days_since_latest_release,
                "is_dev_dependency": u.dependency.is_dev_dependency,
            }
        )

    vuln_data = []
    for u in updates:
        report = vuln_map.get(u.dependency.name)
        if report and report.vulnerabilities:
            for v in report.vulnerabilities:
                vuln_data.append(
                    {
                        "package": u.dependency.name,
                        "cve_id": v.cve_id,
                        "severity": v.severity.value,
                        "summary": v.summary,
                        "fixed_version": v.fixed_version,
                    }
                )

    changelog_data = []
    for u in updates:
        # Try both the package name and owner/repo format
        summary = changelog_map.get(u.dependency.name)
        if not summary:
            # Try matching by repository URL parsing
            for key, val in changelog_map.items():
                if val.entries:
                    summary = val
                    break
        if summary and summary.entries:
            for entry in summary.entries[:3]:
                changelog_data.append(
                    {
                        "package": u.dependency.name,
                        "version": entry.version,
                        "is_breaking": entry.is_breaking,
                        "body": entry.body[:500] if entry.body else "",
                    }
                )

    prompt = RISK_ANALYSIS_PROMPT.format(
        ecosystem=ecosystem.value,
        update_data=json.dumps(update_data, indent=2),
        vulnerability_data=json.dumps(vuln_data, indent=2) if vuln_data else "No known vulnerabilities.",
        changelog_data=json.dumps(changelog_data, indent=2) if changelog_data else "No changelog data available.",
    )

    try:
        llm = create_llm(llm_provider)
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        # Parse JSON response (strip markdown fences if present)
        parsed = json.loads(_extract_json(content))
        assessments_data = parsed.get("assessments", [])

        risk_assessments = []
        for a in assessments_data:
            try:
                risk_assessments.append(
                    RiskAssessment(
                        package_name=a["package_name"],
                        ecosystem=ecosystem,
                        current_version=a["current_version"],
                        recommended_version=a["recommended_version"],
                        risk_level=RiskLevel(a["risk_level"]),
                        risk_score=a.get("risk_score", 5),
                        reason=a["reason"],
                        breaking_changes=a.get("breaking_changes", []),
                        action=a["action"],
                        confidence=a.get("confidence", 0.5),
                    )
                )
            except (KeyError, ValueError) as e:
                errors.append(f"Failed to parse risk assessment for {a.get('package_name', 'unknown')}: {e}")

    except json.JSONDecodeError as e:
        errors.append(f"LLM returned invalid JSON: {e}")
        risk_assessments = []
    except Exception as e:
        errors.append(f"LLM analysis failed: {e}")
        risk_assessments = []

    return {
        "risk_assessments": risk_assessments,
        "current_node": "analyze_risk",
        "iteration": iteration,
        "errors": errors,
    }
