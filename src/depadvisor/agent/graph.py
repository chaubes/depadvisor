"""
LangGraph graph construction for DepAdvisor.

Wires all agent nodes into a directed graph with conditional routing.
"""

from pathlib import Path

from langgraph.graph import END, StateGraph

from depadvisor.agent.nodes.analyze_risk import analyze_risk_node
from depadvisor.agent.nodes.check_updates import check_updates_node
from depadvisor.agent.nodes.fetch_changelogs import fetch_changelogs_node
from depadvisor.agent.nodes.fetch_vulns import fetch_vulnerabilities_node
from depadvisor.agent.nodes.generate_report import generate_report_node
from depadvisor.agent.nodes.parse_deps import parse_dependencies_node
from depadvisor.agent.state import DepAdvisorState
from depadvisor.models.schemas import AnalysisReport, Ecosystem


def should_continue_after_updates(state: DepAdvisorState) -> str:
    """Route based on whether any updates were found."""
    if not state.get("updates"):
        return "no_updates"
    return "has_updates"


def should_retry_analysis(state: DepAdvisorState) -> str:
    """Route based on whether risk analysis succeeded."""
    if state.get("iteration", 0) < 2 and not state.get("risk_assessments"):
        return "retry"
    return "done"


def build_depadvisor_graph():
    """
    Construct and compile the DepAdvisor agent graph.

    Graph structure:
        parse_deps -> check_updates -> [has_updates?]
            yes -> fetch_vulns -> fetch_changelogs -> analyze_risk -> [retry?]
                                                        retry -> analyze_risk
                                                        done  -> generate_report -> END
            no  -> generate_report -> END
    """
    workflow = StateGraph(DepAdvisorState)

    # Register nodes
    workflow.add_node("parse_deps", parse_dependencies_node)
    workflow.add_node("check_updates", check_updates_node)
    workflow.add_node("fetch_vulns", fetch_vulnerabilities_node)
    workflow.add_node("fetch_changelogs", fetch_changelogs_node)
    workflow.add_node("analyze_risk", analyze_risk_node)
    workflow.add_node("generate_report", generate_report_node)

    # Set entry point
    workflow.set_entry_point("parse_deps")

    # Wire edges
    workflow.add_edge("parse_deps", "check_updates")

    workflow.add_conditional_edges(
        "check_updates",
        should_continue_after_updates,
        {
            "has_updates": "fetch_vulns",
            "no_updates": "generate_report",
        },
    )

    workflow.add_edge("fetch_vulns", "fetch_changelogs")
    workflow.add_edge("fetch_changelogs", "analyze_risk")

    workflow.add_conditional_edges(
        "analyze_risk",
        should_retry_analysis,
        {
            "done": "generate_report",
            "retry": "analyze_risk",
        },
    )

    workflow.add_edge("generate_report", END)

    return workflow.compile()


async def run_analysis(
    project_path: str,
    ecosystem: Ecosystem,
    llm_provider: str = "ollama/qwen3:8b",
) -> AnalysisReport | None:
    """
    Run a complete dependency analysis.

    Args:
        project_path: Path to the project directory
        ecosystem: Target ecosystem (python, node, java)
        llm_provider: LLM provider string (e.g., "ollama/qwen3:8b")

    Returns:
        AnalysisReport or None if analysis fails
    """
    graph = build_depadvisor_graph()

    initial_state = {
        "project_path": project_path,
        "ecosystem": ecosystem,
        "llm_provider": llm_provider,
        "dependencies": [],
        "updates": [],
        "vulnerabilities": [],
        "changelogs": [],
        "risk_assessments": [],
        "report": None,
        "current_node": "",
        "iteration": 0,
        "errors": [],
        "messages": [],
    }

    # LangSmith tracing config — automatically used when
    # LANGSMITH_TRACING=true is set in the environment.
    from datetime import UTC, datetime

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    project_name = Path(project_path).resolve().name
    run_config = {
        "run_name": f"depadvisor-{ecosystem.value}-{project_name}-{timestamp}",
        "tags": ["depadvisor", ecosystem.value, llm_provider.split("/")[0]],
        "metadata": {
            "project_path": project_path,
            "ecosystem": ecosystem.value,
            "llm_provider": llm_provider,
        },
    }

    result = await graph.ainvoke(initial_state, config=run_config)
    return result.get("report")
