"""
Node: generate_report

Generates the final analysis report. Update order is deterministic (rule-based).
The LLM is only used to write the executive summary prose.
"""

import json
import re
from datetime import UTC, datetime

from depadvisor.agent.state import DepAdvisorState
from depadvisor.llm.prompts import REPORT_GENERATION_PROMPT
from depadvisor.llm.provider import create_llm
from depadvisor.models.schemas import AnalysisReport, RiskLevel
from depadvisor.utils.scoring import compute_update_order


def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract raw JSON from LLM response."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


async def generate_report_node(state: DepAdvisorState) -> dict:
    """
    Generate the final analysis report.

    - Update order: deterministic from rule-based scores
    - Summary: LLM-generated prose (best-effort, with fallback)
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

    # Deterministic update order from rule-based scores
    update_order = compute_update_order(risk_assessments)

    # Generate summary via LLM (best-effort)
    summary = "No updates available. All dependencies are up to date."

    if risk_assessments:
        # Default summary (used if LLM fails)
        summary = (
            f"Analysis found {len(updates)} dependencies with available updates "
            f"and {total_vulns} known vulnerabilities. "
            f"{len(critical)} critical, {len(high)} high, "
            f"{len(medium)} medium, {len(low)} low priority updates."
        )

        try:
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

            llm = create_llm(llm_provider)
            response = await llm.ainvoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            parsed = json.loads(_extract_json(content))
            summary = parsed.get("summary", summary)
            # NOTE: update_order from LLM is ignored — we use the deterministic one
        except Exception as e:
            errors.append(f"Report summary LLM call failed (using default): {e}")

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
