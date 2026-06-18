"""Pydantic schemas for structured LLM outputs in the agent system."""

from typing import Literal

from pydantic import BaseModel, Field

# Intent categories the router can classify
IntentCategory = Literal["BILLING", "SAFETY", "GENERAL"]
ResolutionAction = Literal[
    "ISSUE_REFUND",
    "NO_ACTION",
    "ESCALATE",
    "REVIEW_CASE",
]


class IntentClassification(BaseModel):
    """Structured output for the Router Agent's intent classification."""

    intent: IntentCategory = Field(
        description=(
            "The classified intent of the user message. "
            "BILLING for payment/refund/charge issues, "
            "SAFETY for ride safety concerns, route deviations, or driver behaviour, "
            "GENERAL for all other queries."
        )
    )
    urgency: int = Field(
        ge=1,
        le=5,
        description=(
            "Urgency score from 1 (low) to 5 (critical/immediate). "
            "Safety threats should be 4-5. Billing disputes 2-3. General queries 1-2."
        ),
    )
    reasoning: str = Field(
        description=(
            "One-sentence explanation of why this intent and urgency were chosen."
        )
    )


class ResolutionDecision(BaseModel):
    """Deterministic final resolution produced by the policy guardrail."""

    action: ResolutionAction = Field(
        description=(
            "The final support action to take. "
            "ISSUE_REFUND for approved refunds, "
            "ESCALATE when policy requires a human review, "
            "REVIEW_CASE for ambiguous disputes, and "
            "NO_ACTION when no remediation is needed."
        )
    )
    amount: float = Field(
        ge=0,
        description=(
            "Monetary amount associated with the action. "
            "Use 0 when the action does not involve a refund."
        ),
    )
    reason: str = Field(
        min_length=1,
        description="Short human-readable explanation for the final decision.",
    )
