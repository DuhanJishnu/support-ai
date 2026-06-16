"""Router Node: classifies user intent and sets routing destination."""

from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.schemas import IntentClassification
from app.agents.state import AgentState, coerce_agent_state
from app.config import settings

logger = structlog.get_logger()

ROUTER_SYSTEM_PROMPT = (
    "You are the Triage Agent for a customer support platform "
    "for a ride-hailing service (similar to Uber).\n\n"
    "Your ONLY task is to classify the user's support message into the "
    "correct category and assign an urgency score.\n\n"
    "Categories:\n"
    "- BILLING: Payment issues, double charges, incorrect fare, "
    "refund requests, receipt problems\n"
    "- SAFETY: Ride route deviations, driver behaviour, unsafe situations, "
    "GPS anomalies, SOS concerns\n"
    "- GENERAL: Account questions, app issues, trip history, "
    "ETA queries, promo codes, everything else\n\n"
    "Urgency (1-5):\n"
    "- 5: Immediate safety threat (e.g. driver attacking passenger)\n"
    "- 4: Serious safety concern (e.g. significant route deviation)\n"
    "- 3: Billing dispute with significant amount (>$20) or urgent refund\n"
    "- 2: Standard billing query or moderate account issue\n"
    "- 1: General informational query, low impact\n\n"
    "Be decisive. Use the exact category names. "
    "Do not ask clarifying questions."
)


def get_router_llm() -> ChatGoogleGenerativeAI:
    """Return a configured Gemini LLM bound to the IntentClassification schema."""
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0,
    )
    return llm.with_structured_output(IntentClassification)


def router_node(state: AgentState | dict[str, Any]) -> AgentState:
    """Classify user intent and route to the correct sub-agent node."""
    agent_state = coerce_agent_state(state)

    # Extract the latest human message
    human_messages = [m for m in agent_state.messages if isinstance(m, HumanMessage)]
    if not human_messages:
        logger.warning("RouterNode: no human message found in state")
        return agent_state.model_copy(
            update={
                "current_node": "router",
                "gathered_context": {
                    **agent_state.gathered_context,
                    "intent": "GENERAL",
                    "urgency": 1,
                    "reasoning": "No user message found; defaulting to GENERAL.",
                },
            }
        )

    user_message = human_messages[-1].content
    logger.info("RouterNode: classifying intent", user_message=str(user_message)[:120])

    try:
        llm = get_router_llm()
        messages = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]
        result: IntentClassification = llm.invoke(messages)  # type: ignore[assignment]

        logger.info(
            "RouterNode: classification complete",
            intent=result.intent,
            urgency=result.urgency,
            reasoning=result.reasoning,
        )

        return agent_state.model_copy(
            update={
                "current_node": "router",
                "resolution_status": "in_progress",
                "gathered_context": {
                    **agent_state.gathered_context,
                    "intent": result.intent,
                    "urgency": result.urgency,
                    "reasoning": result.reasoning,
                },
            }
        )

    except Exception:
        logger.exception("RouterNode: LLM classification failed, defaulting to GENERAL")
        return agent_state.model_copy(
            update={
                "current_node": "router",
                "gathered_context": {
                    **agent_state.gathered_context,
                    "intent": "GENERAL",
                    "urgency": 1,
                    "reasoning": "Classification failed; defaulted to GENERAL.",
                },
            }
        )


def route_after_router(state: AgentState | dict[str, Any]) -> str:
    """Conditional edge function: returns the next node name based on intent."""
    agent_state = coerce_agent_state(state)
    intent = agent_state.gathered_context.get("intent", "GENERAL")

    routing_map = {
        "BILLING": "billing_agent",
        "SAFETY": "telemetry_agent",
        "GENERAL": "general_agent",
    }
    return routing_map.get(intent, "general_agent")
