"""Tests for the initial support agent LangGraph."""

from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from app.agents import AgentState, build_support_graph, run_support_graph
from app.main import create_app


def test_support_graph_compiles_and_updates_state():
    """Graph should run through the guardrail and finalize the outcome."""
    graph = build_support_graph()
    initial_state = AgentState(messages=[HumanMessage(content="I was charged twice")])

    result = AgentState.model_validate(graph.invoke(initial_state))

    assert result.current_node == "guardrail"
    assert result.resolution_status == "resolved"
    assert result.gathered_context["last_node"] == "generic_llm"
    assert result.gathered_context["resolution"]["action"] == "NO_ACTION"
    assert len(result.messages) == 2
    assert result.messages[-1].type == "ai"


def test_run_support_graph_helper_preserves_context():
    """Helper should seed a human message and preserve gathered context."""
    result = run_support_graph(
        "My driver took a wrong turn",
        gathered_context={"ticket_id": "ticket_123"},
    )

    assert result.current_node == "guardrail"
    assert result.resolution_status == "resolved"
    assert result.gathered_context["ticket_id"] == "ticket_123"
    assert result.gathered_context["resolution"]["action"] == "NO_ACTION"
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
    assert data["current_node"] == "guardrail"
    assert data["resolution_status"] == "resolved"
    assert data["gathered_context"]["channel"] == "web"
    assert data["gathered_context"]["resolution"]["action"] == "NO_ACTION"
    assert [message["type"] for message in data["messages"]] == ["human", "ai"]


def test_agent_chat_stream_returns_sse_events():
    """Streaming endpoint should emit typed SSE frames for the dashboard."""
    client = TestClient(create_app())

    with client.stream(
        "POST",
        "/api/agents/chat/stream",
        json={"message": "I need help with a promo code"},
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: agent_status_change" in body
    assert "event: token" in body
    assert "event: done" in body
    assert '"current_node": "guardrail"' in body
