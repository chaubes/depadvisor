"""Prompt templates for LLM-powered analysis nodes."""

RISK_ANALYSIS_PROMPT = """You are a senior software engineer analyzing dependency updates for a {ecosystem} project.

For each dependency with an available update, provide a risk assessment.

DEPENDENCY UPDATE DATA:
{update_data}

VULNERABILITY DATA:
{vulnerability_data}

CHANGELOG EXCERPTS:
{changelog_data}

Respond with a JSON object in this exact format:
{{
  "assessments": [
    {{
      "package_name": "package-name",
      "current_version": "1.0.0",
      "recommended_version": "1.2.0",
      "risk_level": "critical|high|medium|low|skip",
      "risk_score": 5,
      "reason": "Plain English explanation of the recommendation",
      "breaking_changes": ["list of breaking changes if any"],
      "action": "Specific action recommendation",
      "confidence": 0.85
    }}
  ]
}}

RULES:
1. Any dependency with a CRITICAL or HIGH severity vulnerability MUST be risk_level "critical".
2. Major version bumps (e.g., 2.x to 3.x) should be at least "medium" risk.
3. If a new version was released less than 7 days ago and is a major/minor bump, recommend "skip".
4. Dev dependencies (test frameworks, linters) are generally lower risk than runtime dependencies.
5. Prefer recommending the latest patch version within the current major when possible.
6. Be specific about breaking changes — reference actual API changes from changelogs, not generic warnings.
7. risk_score is 1-10 where 1=very safe to update, 10=very risky.
8. confidence is 0.0-1.0 representing how confident you are in the assessment.

Respond ONLY with the JSON object. No additional text."""


REPORT_GENERATION_PROMPT = """You are writing a dependency update report for a development team.

PROJECT: {project_path}
ECOSYSTEM: {ecosystem}
ANALYSIS DATE: {date}
TOTAL DEPENDENCIES: {total_deps}
DEPENDENCIES WITH UPDATES: {total_updates}
TOTAL VULNERABILITIES: {total_vulns}

RISK ASSESSMENTS:
{risk_assessments}

Generate a clear, actionable summary. Respond with a JSON object:
{{
  "summary": "2-3 sentence executive summary of overall dependency health",
  "update_order": ["package1", "package2"]
}}

The summary should:
1. State the overall dependency health (good/needs attention/critical).
2. Highlight any security-critical updates that need immediate attention.
3. Suggest a strategy for tackling updates (order, grouping).

The update_order should list package names in recommended update order
(security-critical first, then by risk level descending).

Write for a developer audience. Be specific, not generic.
Reference actual package names and version numbers. Keep the summary under 200 words.

Respond ONLY with the JSON object. No additional text."""
