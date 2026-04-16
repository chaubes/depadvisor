"""DepAdvisor CLI application built with Typer."""

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from depadvisor.models.schemas import Ecosystem

app = typer.Typer(
    name="depadvisor",
    help="AI-powered dependency update advisor",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def _load_env() -> None:
    """Load .env file before any command runs."""
    # override=True ensures .env values take effect even if
    # the variable was previously set in the shell environment.
    load_dotenv(override=True)


def _is_git_url(path: str) -> bool:
    """Check if the path looks like a git repository URL."""
    return bool(re.match(r"^(https?://|git@|git://|ssh://)", path) or (path.endswith(".git") and "/" in path))


def _clone_repo(url: str, verbose: bool = False) -> str:
    """
    Shallow-clone a git repository to a temporary directory.

    Returns the path to the cloned directory.
    """
    tmp_dir = tempfile.mkdtemp(prefix="depadvisor-")
    if verbose:
        console.print(f"Cloning {url}...")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, tmp_dir],
            check=True,
            capture_output=not verbose,
            text=True,
        )
    except subprocess.CalledProcessError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        console.print(f"[red]Failed to clone repository: {url}[/red]")
        raise typer.Exit(code=1)
    except FileNotFoundError:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        console.print("[red]git is not installed. Install git to analyze remote repositories.[/red]")
        raise typer.Exit(code=1)
    return tmp_dir


def _detect_ecosystem(project_path: str) -> Ecosystem | None:
    """Auto-detect the project ecosystem from files present."""
    path = Path(project_path)

    python_files = ["requirements.txt", "pyproject.toml", "Pipfile"]
    node_files = ["package.json"]
    java_files = ["pom.xml"]

    for f in python_files:
        if (path / f).exists() or list(path.glob("requirements*.txt")):
            return Ecosystem.PYTHON

    for f in node_files:
        if (path / f).exists():
            return Ecosystem.NODE

    for f in java_files:
        if (path / f).exists():
            return Ecosystem.JAVA

    return None


@app.command()
def analyze(
    path: str = typer.Argument(".", help="Local path or git URL (https/ssh) of the project"),
    ecosystem: str | None = typer.Option(
        None,
        "--ecosystem",
        "-e",
        help="Force ecosystem (python, node, java). Auto-detected if not specified.",
    ),
    llm: str = typer.Option(
        None,
        "--llm",
        "-l",
        help="LLM provider/model (e.g., ollama/qwen3:8b, openai/gpt-4o-mini)",
    ),
    format: str = typer.Option(
        "terminal",
        "--format",
        "-f",
        help="Output format: terminal, markdown, json, github-comment",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to file instead of stdout",
    ),
    fail_on: str | None = typer.Option(
        None,
        "--fail-on",
        help="Exit with code 1 if risk level found: critical, high, medium",
    ),
    include_dev: bool = typer.Option(
        False,
        "--include-dev",
        help="Include dev dependencies in analysis",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed progress",
    ),
) -> None:
    """Analyze a project's dependencies for updates and risks."""
    # Handle git URLs — clone to a temp directory
    cloned_dir = None
    if _is_git_url(path):
        cloned_dir = _clone_repo(path, verbose=verbose)
        path = cloned_dir

    try:
        _run_analyze(path, ecosystem, llm, format, output, fail_on, include_dev, verbose)
    finally:
        if cloned_dir:
            console.print("Cleaning up cloned repository...")
            shutil.rmtree(cloned_dir, ignore_errors=True)


def _run_analyze(
    path: str,
    ecosystem: str | None,
    llm: str | None,
    format: str,
    output: str | None,
    fail_on: str | None,
    include_dev: bool,
    verbose: bool,
) -> None:
    """Core analyze logic (separated to allow cleanup of cloned repos)."""
    # Resolve LLM provider
    llm_provider = llm or os.environ.get("DEPADVISOR_LLM_PROVIDER", "ollama") + "/" + os.environ.get(
        "DEPADVISOR_LLM_MODEL", "qwen3:8b"
    )
    if llm:
        llm_provider = llm

    # Resolve ecosystem
    if ecosystem:
        try:
            eco = Ecosystem(ecosystem.lower())
        except ValueError:
            console.print(f"[red]Unknown ecosystem: {ecosystem}[/red]")
            console.print("Supported: python, node, java")
            raise typer.Exit(code=1)
    else:
        eco = _detect_ecosystem(path)
        if eco is None:
            console.print("[red]Could not auto-detect ecosystem.[/red]")
            console.print("Use --ecosystem to specify: python, node, java")
            raise typer.Exit(code=1)
        if verbose:
            console.print(f"Detected ecosystem: {eco.value}")

    if verbose:
        console.print(f"Analyzing {path} ({eco.value}) with {llm_provider}...")

    # Run the analysis
    from depadvisor.agent.graph import run_analysis

    try:
        report = asyncio.run(run_analysis(path, eco, llm_provider))
    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/red]")
        raise typer.Exit(code=1)

    if report is None:
        console.print("[red]Analysis produced no report.[/red]")
        raise typer.Exit(code=1)

    # Output the report
    from depadvisor.utils.output import output_report

    output_report(report, fmt=format, output_file=output)

    # Handle --fail-on
    if fail_on:
        fail_levels = {
            "critical": [report.critical_updates],
            "high": [report.critical_updates, report.recommended_updates],
            "medium": [
                report.critical_updates,
                report.recommended_updates,
                report.optional_updates,
            ],
        }
        check_lists = fail_levels.get(fail_on.lower(), [])
        if any(updates for updates in check_lists):
            raise typer.Exit(code=1)


@app.command()
def scan(
    path: str = typer.Argument(".", help="Local path or git URL (https/ssh) of the project"),
    ecosystem: str | None = typer.Option(
        None,
        "--ecosystem",
        "-e",
        help="Force ecosystem (python, node, java)",
    ),
) -> None:
    """Quick vulnerability-only scan (no LLM required)."""
    # Handle git URLs
    cloned_dir = None
    if _is_git_url(path):
        cloned_dir = _clone_repo(path, verbose=True)
        path = cloned_dir

    try:
        _run_scan(path, ecosystem)
    finally:
        if cloned_dir:
            console.print("Cleaning up cloned repository...")
            shutil.rmtree(cloned_dir, ignore_errors=True)


def _run_scan(path: str, ecosystem: str | None) -> None:
    """Core scan logic."""
    from depadvisor.clients.osv import OSVClient
    from depadvisor.parsers.java import JavaParser
    from depadvisor.parsers.node import NodeParser
    from depadvisor.parsers.python import PythonParser

    # Resolve ecosystem
    if ecosystem:
        try:
            eco = Ecosystem(ecosystem.lower())
        except ValueError:
            console.print(f"[red]Unknown ecosystem: {ecosystem}[/red]")
            raise typer.Exit(code=1)
    else:
        eco = _detect_ecosystem(path)
        if eco is None:
            console.print("[red]Could not auto-detect ecosystem.[/red]")
            raise typer.Exit(code=1)

    # Parse dependencies (uses same skip-dirs logic as the agent node)
    from depadvisor.agent.nodes.parse_deps import _deduplicate, _find_dep_files

    parsers = {
        Ecosystem.PYTHON: PythonParser(),
        Ecosystem.NODE: NodeParser(),
        Ecosystem.JAVA: JavaParser(),
    }
    parser = parsers[eco]
    project_path = Path(path)
    deps = []
    for file_path in _find_dep_files(project_path, parser):
        try:
            deps.extend(parser.parse(str(file_path)))
        except Exception as e:
            console.print(f"[yellow]Warning: {e}[/yellow]")
    deps = _deduplicate(deps)

    if not deps:
        console.print("No dependencies found.")
        raise typer.Exit()

    console.print(f"Found {len(deps)} dependencies. Scanning for vulnerabilities...")

    # Query OSV using batch API
    async def _scan():
        client = OSVClient()
        try:
            packages = [
                (dep.name, dep.current_version, dep.ecosystem)
                for dep in deps
                if dep.current_version
            ]
            if not packages:
                return []
            all_reports = await client.query_batch(packages)
            return [r for r in all_reports if r.vulnerabilities]
        finally:
            await client.close()

    vuln_reports = asyncio.run(_scan())

    if not vuln_reports:
        console.print("[green]No known vulnerabilities found![/green]")
        return

    console.print(f"[red]Found vulnerabilities in {len(vuln_reports)} packages:[/red]")
    for report in vuln_reports:
        console.print(f"\n  [bold]{report.package_name}[/bold] ({report.current_version})")
        for v in report.vulnerabilities:
            severity_color = {"critical": "red", "high": "red", "medium": "yellow"}.get(v.severity.value, "dim")
            console.print(f"    [{severity_color}]{v.severity.value.upper()}[/{severity_color}] {v.summary}")
            if v.fixed_version:
                console.print(f"    Fixed in: {v.fixed_version}")


@app.command()
def version() -> None:
    """Show DepAdvisor version."""
    from importlib.metadata import version as pkg_version

    try:
        v = pkg_version("depadvisor")
    except Exception:
        v = "0.1.0"
    console.print(f"depadvisor {v}")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8888, "--port", "-p", help="Port to listen on"),
) -> None:
    """Start the DepAdvisor HTTP API server."""
    try:
        import uvicorn

        from depadvisor.server.api import app as fastapi_app  # noqa: F811
    except ImportError:
        console.print("[red]Server dependencies not installed.[/red]")
        console.print("Install with: pip install depadvisor[server]")
        raise typer.Exit(code=1)

    console.print(f"Starting DepAdvisor server on {host}:{port}...")
    uvicorn.run(fastapi_app, host=host, port=port)
