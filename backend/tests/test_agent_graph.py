"""Tests for the initial support agent LangGraph."""

from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from app.agents import AgentState, build_support_graph, run_support_graph
from app.main import create_app


def test_support_graph_compiles_and_updates_state():
    """Graph should run through the initial generic node."""
    graph = build_support_graph()
    initial_state = AgentState(messages=[HumanMessage(content="I was charged twice")])

    result = AgentState.model_validate(graph.invoke(initial_state))

    assert result.current_node == "generic_llm"
    assert result.resolution_status == "in_progress"
    assert result.gathered_context["last_node"] == "generic_llm"
    assert len(result.messages) == 2
    assert result.messages[-1].type == "ai"


def test_run_support_graph_helper_preserves_context():
    """Helper should seed a human message and preserve gathered context."""
    result = run_support_graph(
        "My driver took a wrong turn",
        gathered_context={"ticket_id": "ticket_123"},
    )

    assert result.current_node == "generic_llm"
    assert result.gathered_context["ticket_id"] == "ticket_123"
    assert result.messages[0].type == "human"


def test_agent_run_endpoint_returns_serialized_state():
    """API should expose a simple smoke-test endpoint for the graph."""
    client = TestClient(create_app())

    response = client.post(
        "/api/agents/run",
        json={
            "message": "I need help with a refund",
            "gathered_context": {"channel": "web"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["current_node"] == "generic_llm"
    assert data["resolution_status"] == "in_progress"
    assert data["gathered_context"]["channel"] == "web"
    assert [message["type"] for message in data["messages"]] == ["human", "ai"]
