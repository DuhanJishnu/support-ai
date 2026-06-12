"""MCP Billing Server exposing transaction verify tools."""

import os
import time
from typing import Any

from fastmcp import FastMCP

# Initialize the Billing MCP Server
mcp = FastMCP("BillingServer")


@mcp.tool()
def verify_transaction_status(transaction_id: str) -> dict[str, Any]:
    """Verify payment status, amount, and timestamp for a given transaction ID.

    Args:
        transaction_id (str): The unique identifier of the transaction.

    Returns:
        dict: Transaction status, amount, currency, timestamp, and payment method.
    """
    # Mock data generation based on transaction_id patterns
    status = "SUCCESS"
    amount = 25.50
    currency = "USD"

    # Support testing failure/pending flows via transaction_id prefixes
    if transaction_id.startswith("fail_") or "fail" in transaction_id.lower():
        status = "FAILED"
    elif (
        transaction_id.startswith("pend_") or "pending" in transaction_id.lower()
    ):
        status = "PENDING"

    return {
        "transaction_id": transaction_id,
        "status": status,
        "amount": amount,
        "currency": currency,
        "timestamp": int(time.time()),
        "payment_method": "Credit Card",
        "description": f"Verifying transaction lookup for {transaction_id}.",
    }


if __name__ == "__main__":
    # Configure transport based on environment variables
    # Stdio transport is used for local shell/agent invocation
    # SSE transport is used for network container-to-container calls
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    port = os.getenv("PORT", 8001)

    if transport in ("sse", "streamable-http"):
        mcp.run(transport=transport,
                host = "0.0.0.0",
                port = port        
        )
    else:
        mcp.run(transport="stdio",
                host = "0.0.0.0",
                port = port        
        )
