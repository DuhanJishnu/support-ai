"""Agent graph API endpoints."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from app.agents import run_support_graph
from app.config import settings

router = APIRouter(prefix="/api/agents", tags=["agents"])


class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""

    message: str = Field(..., min_length=1, description="Customer support message")
    gathered_context: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str = Field(default="", description="Session ID for multi-turn")
    previous_messages: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Serialized messages from prior turns",
    )
    extracted_entities: dict[str, Any] = Field(
        default_factory=dict,
        description="Entities extracted in prior turns (transaction_id, ride_id)",
    )


class ChatResponse(BaseModel):
    """Serialized response including triage classification."""

    current_node: str
    resolution_status: str
    intent: str
    urgency: int
    reasoning: str
    gathered_context: dict[str, Any]
    messages: list[dict[str, Any]]
    conversation_id: str = ""
    extracted_entities: dict[str, Any] = Field(default_factory=dict)


def encode_sse(event: str, data: dict[str, Any]) -> str:
    """Encode a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def serialize_message(message: BaseMessage) -> dict[str, Any]:
    """Serialize a LangChain message into a stable API shape."""
    return {
        "type": message.type,
        "content": message.content,
    }


def _ensure_conversation_id(request: ChatRequest) -> str:
    """Return the request's conversation_id or generate a new one."""
    return request.conversation_id or str(uuid.uuid4())


async def simulated_stream(request: ChatRequest) -> AsyncIterator[str]:
    """Provide a rich, simulated agent experience when LLM API is unavailable."""
    msg = request.message.lower()
    conv_id = _ensure_conversation_id(request)
    intent = (
        "BILLING"
        if any(x in msg for x in ["charge", "pay", "refund", "fare", "money"])
        else "SAFETY"
        if any(x in msg for x in ["route", "driver", "gps", "danger", "safe"])
        else "GENERAL"
    )

    yield encode_sse(
        "agent_status_change",
        {"node": "router", "status": "in_progress", "label": "Classifying intent"},
    )
    await asyncio.sleep(0.8)
    yield encode_sse(
        "token",
        {"content": "I am analyzing your request to identify the correct specialist...\n"},
    )
    await asyncio.sleep(0.5)

    node = (
        "billing_agent"
        if intent == "BILLING"
        else "telemetry_agent"
        if intent == "SAFETY"
        else "generic_llm"
    )
    yield encode_sse(
        "agent_status_change", {"node": node, "status": "querying", "intent": intent, "urgency": 3}
    )

    if intent == "BILLING":
        yield encode_sse(
            "token",
            {"content": "Intent recognized as BILLING. Accessing transaction records via MCP...\n"},
        )
        await asyncio.sleep(1.2)
        tool_call = {
            "node": "billing_agent",
            "tool_name": "verify_transaction_status",
            "input": {"transaction_id": "txn_sim_99"},
            "status": "succeeded",
            "result": {
                "data": {
                    "transaction_id": "txn_sim_99",
                    "status": "SUCCESS",
                    "amount": 29.99,
                    "currency": "USD",
                    "payment_method": "Credit Card",
                }
            },
        }
        yield encode_sse("tool_invocation", tool_call)
    elif intent == "SAFETY":
        yield encode_sse(
            "token",
            {"content": "Intent recognized as SAFETY. Fetching ride telemetry data...\n"},
        )
        await asyncio.sleep(1.2)
        tool_call = {
            "node": "telemetry_agent",
            "tool_name": "get_ride_route_deviation",
            "input": {"ride_id": "ride_sim_101"},
            "status": "succeeded",
            "result": {
                "data": {
                    "ride_id": "ride_sim_101",
                    "deviation_score": 0.12,
                    "status": "Normal",
                    "details": "Minor traffic-related detour detected. No safety risk identified.",
                }
            },
        }
        yield encode_sse("tool_invocation", tool_call)
    else:
        yield encode_sse(
            "token",
            {"content": "Directing your inquiry to our general support specialist...\n"},
        )
        await asyncio.sleep(1.0)

    yield encode_sse("agent_status_change", {"node": "guardrail", "status": "in_progress"})
    await asyncio.sleep(0.6)

    final_text = "I've reviewed the system data. "
    if intent == "BILLING":
        final_text += (
            "Your transaction txn_sim_99 was successful for $29.99. "
            "I have forwarded this to our refund engine for a policy-compliant adjustment."
        )
    elif intent == "SAFETY":
        final_text += (
            "The route for ride_sim_101 shows a 12% deviation, which is within "
            "standard traffic variance. Your safety score remains optimal."
        )
    else:
        final_text += (
            "I've logged your request in our general queue. "
            "A human representative will follow up if further action is required."
        )

    for chunk in final_text.split(" "):
        yield encode_sse("token", {"content": chunk + " "})
        await asyncio.sleep(0.1)

    yield encode_sse(
        "done",
        {
            "current_node": "guardrail",
            "resolution_status": "resolved",
            "gathered_context": {"intent": intent, "urgency": 3},
            "messages": [{"type": "ai", "content": final_text}],
            "conversation_id": conv_id,
            "extracted_entities": {},
        },
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Run the triage+router agent graph",
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Classify intent via the Router Agent and route to the right sub-agent."""
    conv_id = _ensure_conversation_id(request)
    state = run_support_graph(
        message=request.message,
        gathered_context=request.gathered_context,
        previous_messages=request.previous_messages,
        extracted_entities=request.extracted_entities,
        conversation_id=conv_id,
    )
    ctx = state.gathered_context
    return ChatResponse(
        current_node=state.current_node,
        resolution_status=state.resolution_status,
        intent=ctx.get("intent", "GENERAL"),
        urgency=ctx.get("urgency", 1),
        reasoning=ctx.get("reasoning", ""),
        gathered_context=ctx,
        messages=[serialize_message(m) for m in state.messages],
        conversation_id=state.conversation_id,
        extracted_entities=state.extracted_entities,
    )


async def stream_support_graph(request: ChatRequest) -> AsyncIterator[str]:
    """Yield agent progress as Server-Sent Events."""
    conv_id = _ensure_conversation_id(request)

    yield encode_sse(
        "agent_status_change",
        {"node": "router", "status": "in_progress", "label": "Classifying intent"},
    )
    yield encode_sse("token", {"content": "Classifying the support request..."})
    await asyncio.sleep(0)

    state = run_support_graph(
        message=request.message,
        gathered_context=request.gathered_context,
        previous_messages=request.previous_messages,
        extracted_entities=request.extracted_entities,
        conversation_id=conv_id,
    )
    ctx = state.gathered_context

    if last_tool_call := ctx.get("last_tool_call"):
        tool_event = dict(last_tool_call)
        if last_tool_call.get("tool_name") == "verify_transaction_status":
            tool_event["result"] = ctx.get("billing", {}).get("result")
        if last_tool_call.get("tool_name") == "get_ride_route_deviation":
            tool_event["result"] = ctx.get("telemetry", {}).get("result")

        yield encode_sse("tool_invocation", tool_event)
        await asyncio.sleep(0)

    yield encode_sse(
        "agent_status_change",
        {
            "node": state.current_node,
            "status": state.resolution_status,
            "intent": ctx.get("intent", "GENERAL"),
            "urgency": ctx.get("urgency", 1),
        },
    )

    if state.messages:
        yield encode_sse(
            "token",
            {"content": str(state.messages[-1].content), "message_type": "ai"},
        )

    yield encode_sse(
        "done",
        {
            "current_node": state.current_node,
            "resolution_status": state.resolution_status,
            "gathered_context": ctx,
            "messages": [serialize_message(m) for m in state.messages],
            "conversation_id": state.conversation_id,
            "extracted_entities": state.extracted_entities,
        },
    )


@router.post(
    "/chat/stream",
    summary="Run the agent graph and stream status, tool, and token events",
)
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Stream support-agent progress as SSE frames."""
    return StreamingResponse(
        stream_support_graph(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Legacy endpoint — kept for backwards compatibility
# ---------------------------------------------------------------------------


class AgentRunRequest(BaseModel):
    """Request model for invoking the support agent graph."""

    message: str = Field(..., min_length=1, description="Customer support message")
    gathered_context: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    """Serialized response from the support agent graph."""

    current_node: str
    resolution_status: str
    gathered_context: dict[str, Any]
    messages: list[dict[str, Any]]


@router.post("/run", response_model=AgentRunResponse, include_in_schema=False)
async def run_agent(request: AgentRunRequest) -> AgentRunResponse:
    """Run the support-agent graph (legacy endpoint)."""
    state = run_support_graph(
        message=request.message,
        gathered_context=request.gathered_context,
    )
    return AgentRunResponse(
        current_node=state.current_node,
        resolution_status=state.resolution_status,
        gathered_context=state.gathered_context,
        messages=[serialize_message(m) for m in state.messages],
    )
