"""Agent graph API endpoints."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from app.agents import run_support_graph

router = APIRouter(prefix="/api/agents", tags=["agents"])


class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""

    message: str = Field(..., min_length=1, description="Customer support message")
    gathered_context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Serialized response including triage classification."""

    current_node: str
    resolution_status: str
    intent: str
    urgency: int
    reasoning: str
    gathered_context: dict[str, Any]
    messages: list[dict[str, Any]]


def encode_sse(event: str, data: dict[str, Any]) -> str:
    """Encode a single Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def serialize_message(message: BaseMessage) -> dict[str, Any]:
    """Serialize a LangChain message into a stable API shape."""
    return {
        "type": message.type,
        "content": message.content,
    }


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Run the triage+router agent graph",
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Classify intent via the Router Agent and route to the right sub-agent."""
    state = run_support_graph(
        message=request.message,
        gathered_context=request.gathered_context,
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
    )


async def stream_support_graph(request: ChatRequest) -> AsyncIterator[str]:
    """Yield agent progress as Server-Sent Events."""
    yield encode_sse(
        "agent_status_change",
        {"node": "router", "status": "in_progress", "label": "Classifying intent"},
    )
    yield encode_sse("token", {"content": "Classifying the support request..."})
    await asyncio.sleep(0)

    state = run_support_graph(
        message=request.message,
        gathered_context=request.gathered_context,
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
