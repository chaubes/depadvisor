"""
LangGraph Agent State Definition.

The state is the central data structure that flows through every node
in the graph. Each node reads from the state and writes updates to it.

Think of it like a shared whiteboard: Node 1 writes the dependency list,
Node 2 reads that list and writes update candidates, Node 3 reads those
and writes vulnerabilities, etc.
"""

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages

from depadvisor.models.schemas import (
    AnalysisReport,
    ChangelogSummary,
    DependencyInfo,
    Ecosystem,
    RiskAssessment,
    UpdateCandidate,
    VulnerabilityReport,
)


class DepAdvisorState(TypedDict):
    """
    The complete state of a DepAdvisor analysis run.

    Every node in the graph receives this state and returns
    a partial update to it. LangGraph merges the updates.
    """

    # ── Input (set once at the start) ──
    project_path: str
    ecosystem: Ecosystem
    llm_provider: str

    # ── Pipeline data (accumulated by nodes) ──
    dependencies: list[DependencyInfo]
    updates: list[UpdateCandidate]
    vulnerabilities: list[VulnerabilityReport]
    changelogs: list[ChangelogSummary]
    risk_assessments: list[RiskAssessment]

    # ── Output ──
    report: AnalysisReport | None

    # ── Control flow ──
    current_node: str
    iteration: int
    errors: list[str]

    # ── LLM message history ──
    messages: Annotated[list[BaseMessage], add_messages]
