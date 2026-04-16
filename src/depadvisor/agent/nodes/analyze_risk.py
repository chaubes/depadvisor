"""
Node: analyze_risk

Two-layer risk assessment:
1. Rule-based scoring (deterministic) — sets risk_level, risk_score, recommended_version
2. LLM enrichment (variable) — adds reason, breaking_changes, action text

This ensures consistent risk levels and update ordering across runs,
while the LLM adds valuable human-readable context.
"""

import json
import re

from depadvisor.agent.state import DepAdvisorState
from depadvisor.llm.provider import create_llm
from depadvisor.models.schemas import RiskAssessment, UpdateCandidate
from depadvisor.utils.scoring import compute_risk_assessment


def _extract_json(text: str) -> str:
    """Strip markdown code fences and extract raw JSON from LLM response."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


LLM_ENRICHMENT_PROMPT = """You are a senior software engineer. For each dependency update below, \
write a brief explanation and action recommendation.

The risk_level and risk_score have already been determined by automated analysis. \
Do NOT change them. Your job is to add:
- "reason": A 1-2 sentence plain English explanation of WHY this risk level was assigned
- "breaking_changes": List of specific breaking changes from the changelog (empty list if none known)
- "action": A short, specific action recommendation (e.g., "Update to 3.1.6 to fix XSS vulnerability")

DEPENDENCY DATA:
{dep_data}

Respond with a JSON object:
{{
  "enrichments": [
    {{
      "package_name": "...",
      "reason": "...",
      "breaking_changes": [],
      "action": "..."
    }}
  ]
}}

Respond ONLY with the JSON object. No additional text."""


async def analyze_risk_node(state: DepAdvisorState) -> dict:
    """
    Assess risk for each dependency update.

    Layer 1: Deterministic rule-based scoring (always runs)
    Layer 2: LLM enrichment for human-readable context (best-effort)
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

    # === Layer 1: Rule-based scoring (deterministic) ===
    assessments = []
    for u in updates:
        vuln_report = vuln_map.get(u.dependency.name)
        assessment = compute_risk_assessment(u, vuln_report, ecosystem)
        assessments.append(assessment)

    # === Layer 2: LLM enrichment (best-effort) ===
    dep_data = []
    for i, u in enumerate(updates):
        a = assessments[i]
        vuln_report = vuln_map.get(u.dependency.name)
        changelog = changelog_map.get(u.dependency.name)

        entry = {
            "package_name": a.package_name,
            "current_version": a.current_version,
            "recommended_version": a.recommended_version,
            "risk_level": a.risk_level.value,
            "risk_score": a.risk_score,
            "update_type": _get_update_type(u),
            "is_dev_dependency": u.dependency.is_dev_dependency,
            "versions_behind": u.versions_behind,
        }

        if vuln_report and vuln_report.vulnerabilities:
            entry["vulnerabilities"] = [
                {"severity": v.severity.value, "summary": v.summary, "fixed_in": v.fixed_version}
                for v in vuln_report.vulnerabilities[:5]
            ]

        if changelog and changelog.entries:
            entry["changelog"] = [
                {"version": e.version, "is_breaking": e.is_breaking, "body": e.body[:300]}
                for e in changelog.entries[:3]
            ]

        dep_data.append(entry)

    try:
        llm = create_llm(llm_provider)
        prompt = LLM_ENRICHMENT_PROMPT.format(dep_data=json.dumps(dep_data, indent=2))
        response = await llm.ainvoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        parsed = json.loads(_extract_json(content))

        # Merge LLM enrichments into rule-based assessments
        enrichment_map = {e["package_name"]: e for e in parsed.get("enrichments", [])}

        enriched = []
        for a in assessments:
            e = enrichment_map.get(a.package_name, {})
            enriched.append(
                RiskAssessment(
                    package_name=a.package_name,
                    ecosystem=a.ecosystem,
                    current_version=a.current_version,
                    recommended_version=a.recommended_version,
                    risk_level=a.risk_level,  # From rules, NOT LLM
                    risk_score=a.risk_score,  # From rules, NOT LLM
                    reason=e.get("reason", _default_reason(a)),
                    breaking_changes=e.get("breaking_changes", []),
                    action=e.get("action", _default_action(a)),
                    confidence=a.confidence,
                )
            )
        assessments = enriched

    except Exception as e:
        errors.append(f"LLM enrichment failed (using rule-based defaults): {e}")
        # Fall back to rule-based defaults — assessments still have valid scores
        assessments = [
            RiskAssessment(
                package_name=a.package_name,
                ecosystem=a.ecosystem,
                current_version=a.current_version,
                recommended_version=a.recommended_version,
                risk_level=a.risk_level,
                risk_score=a.risk_score,
                reason=_default_reason(a),
                breaking_changes=[],
                action=_default_action(a),
                confidence=a.confidence,
            )
            for a in assessments
        ]

    return {
        "risk_assessments": assessments,
        "current_node": "analyze_risk",
        "iteration": iteration,
        "errors": errors,
    }


def _get_update_type(update: UpdateCandidate) -> str:
    """Get the update type string for an update candidate."""
    from depadvisor.utils.version import classify_update

    current = update.dependency.current_version or "0.0.0"
    return classify_update(current, update.latest_version)


def _default_reason(a: RiskAssessment) -> str:
    """Generate a default reason when LLM is unavailable."""
    if a.risk_level.value == "critical":
        return f"Security vulnerabilities found in {a.package_name} {a.current_version}."
    elif a.risk_level.value == "high":
        return f"Medium severity vulnerabilities found in {a.package_name} {a.current_version}."
    elif a.risk_level.value == "skip":
        return f"New release of {a.package_name} is too recent. Wait for community stabilization."
    else:
        return f"Update available for {a.package_name}: {a.current_version} -> {a.recommended_version}."


def _default_action(a: RiskAssessment) -> str:
    """Generate a default action when LLM is unavailable."""
    if a.risk_level.value == "critical":
        return f"Update to {a.recommended_version} immediately."
    elif a.risk_level.value == "high":
        return f"Update to {a.recommended_version} soon."
    elif a.risk_level.value == "skip":
        return "Wait for the release to stabilize before updating."
    else:
        return f"Update to {a.recommended_version} when convenient."
