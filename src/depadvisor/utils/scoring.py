"""
Deterministic rule-based risk scoring for dependency updates.

This module computes consistent risk levels and scores based on
factual data (vulnerabilities, version bump type, age, dev status).
The LLM is only used to add reasoning on top of these fixed scores.
"""

from depadvisor.models.schemas import (
    Ecosystem,
    RiskAssessment,
    RiskLevel,
    Severity,
    UpdateCandidate,
    VulnerabilityReport,
)
from depadvisor.utils.version import classify_update


def compute_risk_assessment(
    update: UpdateCandidate,
    vuln_report: VulnerabilityReport | None,
    ecosystem: Ecosystem,
) -> RiskAssessment:
    """
    Compute a deterministic risk assessment for a single dependency update.

    Scoring rules (applied in priority order):
    1. CRITICAL/HIGH vuln → risk_level=critical, score=9-10
    2. MEDIUM vuln → risk_level=high, score=7-8
    3. Major version bump → risk_level=medium, score=6-7
    4. Minor version bump → risk_level=medium, score=4-5
    5. Patch-only update → risk_level=low, score=1-3
    6. Dev dependencies get -1 score adjustment
    7. Very new releases (< 7 days) get +1 score adjustment
    """
    dep = update.dependency
    current = dep.current_version or "0.0.0"
    recommended = update.latest_version

    # Start with base score from update type
    update_type = classify_update(current, recommended)
    base_score, risk_level = _score_from_update_type(update_type)

    # Adjust for vulnerabilities (can only increase severity)
    if vuln_report:
        vuln_score, vuln_level = _score_from_vulnerabilities(vuln_report)
        if vuln_score > base_score:
            base_score = vuln_score
            risk_level = vuln_level

    # Adjust for dev dependency (lower priority)
    if dep.is_dev_dependency and base_score > 1:
        base_score = max(1, base_score - 1)
        if risk_level == RiskLevel.CRITICAL:
            risk_level = RiskLevel.HIGH
        elif risk_level == RiskLevel.HIGH:
            risk_level = RiskLevel.MEDIUM

    # Adjust for very new releases
    if update.days_since_latest_release is not None and update.days_since_latest_release < 7:
        if update_type in ("major", "minor"):
            risk_level = RiskLevel.SKIP
            base_score = min(10, base_score + 1)

    # Clamp score
    base_score = max(1, min(10, base_score))

    # Determine recommended version (prefer patch, then minor, then major)
    if risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
        # For security issues, recommend the fix version
        fix_version = _get_vuln_fix_version(vuln_report) if vuln_report else None
        recommended = fix_version or recommended
    elif update.latest_patch and update_type != "patch":
        # For non-security, prefer conservative patch update
        recommended = update.latest_patch

    return RiskAssessment(
        package_name=dep.name,
        ecosystem=ecosystem,
        current_version=current,
        recommended_version=recommended,
        risk_level=risk_level,
        risk_score=base_score,
        reason="",  # Filled by LLM
        breaking_changes=[],  # Filled by LLM
        action="",  # Filled by LLM
        confidence=0.9,  # High confidence for rule-based
    )


def compute_update_order(assessments: list[RiskAssessment]) -> list[str]:
    """
    Compute a deterministic update order based on risk scores.

    Order: critical (highest score first) → high → medium → low → skip
    """
    level_priority = {
        RiskLevel.CRITICAL: 0,
        RiskLevel.HIGH: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.LOW: 3,
        RiskLevel.SKIP: 4,
    }

    sorted_assessments = sorted(
        assessments,
        key=lambda a: (level_priority.get(a.risk_level, 5), -a.risk_score),
    )

    return [a.package_name for a in sorted_assessments if a.risk_level != RiskLevel.SKIP]


def _score_from_update_type(update_type: str) -> tuple[int, RiskLevel]:
    """Base score from the type of version bump."""
    if update_type == "major":
        return 7, RiskLevel.MEDIUM
    elif update_type == "minor":
        return 4, RiskLevel.MEDIUM
    elif update_type == "patch":
        return 2, RiskLevel.LOW
    else:
        return 3, RiskLevel.LOW


def _score_from_vulnerabilities(vuln_report: VulnerabilityReport) -> tuple[int, RiskLevel]:
    """Score based on the highest severity vulnerability."""
    if not vuln_report.vulnerabilities:
        return 0, RiskLevel.LOW

    severities = [v.severity for v in vuln_report.vulnerabilities]

    if Severity.CRITICAL in severities:
        return 10, RiskLevel.CRITICAL
    elif Severity.HIGH in severities:
        return 9, RiskLevel.CRITICAL
    elif Severity.MEDIUM in severities:
        return 7, RiskLevel.HIGH
    elif Severity.LOW in severities:
        return 4, RiskLevel.MEDIUM
    else:
        # UNKNOWN severity — treat as medium concern
        return 5, RiskLevel.MEDIUM


def _get_vuln_fix_version(vuln_report: VulnerabilityReport) -> str | None:
    """Get the highest fix version from vulnerability data."""
    from depadvisor.utils.version import parse_version

    fix_versions = []
    for v in vuln_report.vulnerabilities:
        if v.fixed_version:
            parsed = parse_version(v.fixed_version)
            if parsed:
                fix_versions.append((parsed, v.fixed_version))

    if not fix_versions:
        return None

    return max(fix_versions, key=lambda x: x[0])[1]
