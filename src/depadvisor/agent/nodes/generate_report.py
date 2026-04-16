"""
Node: generate_report

Uses the LLM to generate a final analysis report from risk assessments.
"""

import json
import re
from datetime import UTC, datetime

from depadvisor.agent.state import DepAdvisorState
from depadvisor.llm.prompts import REPORT_GENERATION_PROMPT
from depadvisor.llm.provider import create_llm
from depadvisor.models.schemas import AnalysisReport, RiskLevel


def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract raw JSON from LLM response."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


async def generate_report_node(state: DepAdvisorState) -> dict:
    """
    Generate the final analysis report.

    Reads: state['risk_assessments'], state['dependencies'], state['updates'],
           state['vulnerabilities'], state['llm_provider'], state['ecosystem'],
           state['project_path']
    Writes: state['report'], state['current_node']
    """
    risk_assessments = state.get("risk_assessments", [])
    dependencies = state.get("dependencies", [])
    updates = state.get("updates", [])
    vulnerabilities = state.get("vulnerabilities", [])
    llm_provider = state.get("llm_provider", "ollama/qwen3:8b")
    ecosystem = state["ecosystem"]
    project_path = state.get("project_path", ".")
    errors = list(state.get("errors", []))

    total_vulns = sum(len(v.vulnerabilities) for v in vulnerabilities)

    # Categorize risk assessments
    critical = [a for a in risk_assessments if a.risk_level == RiskLevel.CRITICAL]
    high = [a for a in risk_assessments if a.risk_level == RiskLevel.HIGH]
    medium = [a for a in risk_assessments if a.risk_level == RiskLevel.MEDIUM]
    low = [a for a in risk_assessments if a.risk_level == RiskLevel.LOW]
    skip = [a for a in risk_assessments if a.risk_level == RiskLevel.SKIP]

    # Generate summary via LLM
    summary = "No updates available. All dependencies are up to date."
    update_order = []

    if risk_assessments:
        assessments_json = json.dumps(
            [a.model_dump(mode="json") for a in risk_assessments],
            indent=2,
        )

        prompt = REPORT_GENERATION_PROMPT.format(
            project_path=project_path,
            ecosystem=ecosystem.value,
            date=datetime.now(UTC).strftime("%Y-%m-%d"),
            total_deps=len(dependencies),
            total_updates=len(updates),
            total_vulns=total_vulns,
            risk_assessments=assessments_json,
        )

        try:
            llm = create_llm(llm_provider)
            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            parsed = json.loads(_extract_json(content))
            summary = parsed.get("summary", summary)
            update_order = parsed.get("update_order", [])
        except Exception as e:
            errors.append(f"Report generation LLM call failed: {e}")
            # Fall back to a basic summary
            summary = (
                f"Analysis found {len(updates)} dependencies with available updates "
                f"and {total_vulns} known vulnerabilities. "
                f"{len(critical)} critical, {len(high)} high, {len(medium)} medium priority updates."
            )
            update_order = [a.package_name for a in critical + high + medium + low]

    report = AnalysisReport(
        project_path=project_path,
        ecosystem=ecosystem,
        analyzed_at=datetime.now(UTC),
        total_dependencies=len(dependencies),
        total_with_updates=len(updates),
        total_vulnerabilities=total_vulns,
        critical_updates=critical,
        recommended_updates=high,
        optional_updates=medium + low,
        skip_updates=skip,
        summary=summary,
        update_order=update_order,
        errors=errors,
    )

    return {
        "report": report,
        "current_node": "generate_report",
        "errors": errors,
    }
