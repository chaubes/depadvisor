"""Prompt templates for LLM-powered analysis nodes."""

REPORT_GENERATION_PROMPT = """You are writing a dependency update report for a development team.

PROJECT: {project_path}
ECOSYSTEM: {ecosystem}
ANALYSIS DATE: {date}
TOTAL DEPENDENCIES: {total_deps}
DEPENDENCIES WITH UPDATES: {total_updates}
TOTAL VULNERABILITIES: {total_vulns}

RISK ASSESSMENTS:
{risk_assessments}

Generate a clear, actionable executive summary. Respond with a JSON object:
{{
  "summary": "2-3 sentence executive summary of overall dependency health"
}}

The summary should:
1. State the overall dependency health (good/needs attention/critical).
2. Highlight any security-critical updates that need immediate attention.
3. Briefly mention the recommended update strategy.

Write for a developer audience. Be specific, not generic.
Reference actual package names and version numbers. Keep under 200 words.

Respond ONLY with the JSON object. No additional text."""
