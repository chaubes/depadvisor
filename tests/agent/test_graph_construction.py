"""Test that the LangGraph graph compiles correctly."""

from depadvisor.agent.graph import build_depadvisor_graph


class TestGraphConstruction:
    def test_graph_compiles(self):
        """The graph should compile without errors."""
        graph = build_depadvisor_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        """Verify all expected nodes are in the graph."""
        graph = build_depadvisor_graph()
        node_names = set(graph.get_graph().nodes.keys())
        expected = {
            "__start__",
            "__end__",
            "parse_deps",
            "check_updates",
            "fetch_vulns",
            "fetch_changelogs",
            "analyze_risk",
            "generate_report",
        }
        assert expected.issubset(node_names)
