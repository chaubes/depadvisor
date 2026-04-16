"""Output formatters for DepAdvisor analysis reports."""

from rich.console import Console
from rich.table import Table

from depadvisor.models.schemas import AnalysisReport, RiskLevel

console = Console()

# Color mapping for risk levels
RISK_COLORS = {
    RiskLevel.CRITICAL: "bold red",
    RiskLevel.HIGH: "red",
    RiskLevel.MEDIUM: "yellow",
    RiskLevel.LOW: "green",
    RiskLevel.SKIP: "dim",
}


def format_terminal(report: AnalysisReport) -> None:
    """Render the report to the terminal using Rich."""
    console.print()
    console.rule(f"[bold]DepAdvisor Report — {report.ecosystem.value.title()}")
    console.print()

    # Summary
    console.print(f"[bold]Summary:[/bold] {report.summary}")
    console.print()
    console.print(
        f"Dependencies: {report.total_dependencies} | "
        f"Updates available: {report.total_with_updates} | "
        f"Vulnerabilities: {report.total_vulnerabilities}"
    )
    console.print()

    # Updates table
    all_updates = report.critical_updates + report.recommended_updates + report.optional_updates + report.skip_updates

    if all_updates:
        table = Table(title="Dependency Updates")
        table.add_column("Package", style="bold")
        table.add_column("Current")
        table.add_column("Recommended")
        table.add_column("Risk")
        table.add_column("Score", justify="center")
        table.add_column("Action")

        for a in all_updates:
            color = RISK_COLORS.get(a.risk_level, "")
            table.add_row(
                a.package_name,
                a.current_version,
                a.recommended_version,
                f"[{color}]{a.risk_level.value.upper()}[/{color}]",
                str(a.risk_score),
                a.action,
            )

        console.print(table)
    else:
        console.print("[green]All dependencies are up to date![/green]")

    # Update order
    if report.update_order:
        console.print()
        console.print("[bold]Recommended update order:[/bold]")
        for i, pkg in enumerate(report.update_order, 1):
            console.print(f"  {i}. {pkg}")

    # Errors
    if report.errors:
        console.print()
        console.print("[yellow]Warnings/Errors:[/yellow]")
        for err in report.errors:
            console.print(f"  - {err}")

    console.print()


def format_markdown(report: AnalysisReport) -> str:
    """Generate a Markdown document from the report."""
    lines = [
        f"# DepAdvisor Report — {report.ecosystem.value.title()}",
        "",
        f"**Analyzed:** {report.analyzed_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Project:** {report.project_path}",
        "",
        "## Summary",
        "",
        report.summary,
        "",
        f"- **Total dependencies:** {report.total_dependencies}",
        f"- **Updates available:** {report.total_with_updates}",
        f"- **Vulnerabilities found:** {report.total_vulnerabilities}",
        "",
    ]

    for section_name, updates in [
        ("Critical Updates", report.critical_updates),
        ("Recommended Updates", report.recommended_updates),
        ("Optional Updates", report.optional_updates),
        ("Skipped Updates", report.skip_updates),
    ]:
        if updates:
            lines.append(f"## {section_name}")
            lines.append("")
            lines.append("| Package | Current | Recommended | Risk | Action |")
            lines.append("|---------|---------|-------------|------|--------|")
            for a in updates:
                lines.append(
                    f"| {a.package_name} | {a.current_version} | "
                    f"{a.recommended_version} | {a.risk_level.value.upper()} | {a.action} |"
                )
            lines.append("")

    if report.update_order:
        lines.append("## Recommended Update Order")
        lines.append("")
        for i, pkg in enumerate(report.update_order, 1):
            lines.append(f"{i}. {pkg}")
        lines.append("")

    if report.errors:
        lines.append("## Warnings")
        lines.append("")
        for err in report.errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)


def format_json(report: AnalysisReport) -> str:
    """Generate JSON output from the report."""
    return report.model_dump_json(indent=2)


def format_github_comment(report: AnalysisReport) -> str:
    """Generate a GitHub-flavored Markdown comment with collapsible sections."""
    lines = [
        f"## DepAdvisor Report — {report.ecosystem.value.title()}",
        "",
        report.summary,
        "",
        f"> Dependencies: {report.total_dependencies} | "
        f"Updates: {report.total_with_updates} | "
        f"Vulnerabilities: {report.total_vulnerabilities}",
        "",
    ]

    if report.critical_updates:
        lines.append("### Critical Updates")
        lines.append("")
        for a in report.critical_updates:
            lines.append(f"- **{a.package_name}** `{a.current_version}` -> `{a.recommended_version}` — {a.reason}")
        lines.append("")

    for section_name, updates in [
        ("Recommended Updates", report.recommended_updates),
        ("Optional Updates", report.optional_updates),
    ]:
        if updates:
            lines.append(f"<details><summary>{section_name} ({len(updates)})</summary>")
            lines.append("")
            lines.append("| Package | Current | Recommended | Action |")
            lines.append("|---------|---------|-------------|--------|")
            for a in updates:
                lines.append(f"| {a.package_name} | {a.current_version} | {a.recommended_version} | {a.action} |")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    if report.skip_updates:
        lines.append(f"<details><summary>Skipped ({len(report.skip_updates)})</summary>")
        lines.append("")
        for a in report.skip_updates:
            lines.append(f"- **{a.package_name}**: {a.reason}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


# Format dispatcher
FORMATTERS = {
    "terminal": None,  # Terminal is handled specially (prints directly)
    "markdown": format_markdown,
    "json": format_json,
    "github-comment": format_github_comment,
}


def output_report(report: AnalysisReport, fmt: str = "terminal", output_file: str | None = None) -> None:
    """
    Output the report in the specified format.

    Args:
        report: The analysis report
        fmt: Output format (terminal, markdown, json, github-comment)
        output_file: Optional file path to write output to
    """
    if fmt == "terminal" and output_file is None:
        format_terminal(report)
        return

    formatter = FORMATTERS.get(fmt)
    if formatter is None:
        # Default to JSON for unknown formats
        formatter = format_json

    content = formatter(report)

    if output_file:
        with open(output_file, "w") as f:
            f.write(content)
        console.print(f"Report written to {output_file}")
    else:
        print(content)
