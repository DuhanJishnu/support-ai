"""MCP Telemetry Server exposing ride diagnostics tools."""

import os
import random
from typing import Any

from fastmcp import FastMCP

# Initialize the Telemetry MCP Server
mcp = FastMCP("TelemetryServer")


@mcp.tool()
def get_ride_route_deviation(ride_id: str) -> dict[str, Any]:
    """Retrieve GPS points and the deviation/anomaly score for a given ride ID.

    Args:
        ride_id (str): The unique identifier of the ride.

    Returns:
        dict: GPS coordinates path, deviation/anomaly score, and status.
    """
    # Mock route path (5 sequential GPS points)
    gps_points = [
        {
            "latitude": 37.7749 + i * 0.0005,
            "longitude": -122.4194 + i * 0.0005,
            "timestamp": f"2026-06-12T08:00:{10 * i:02d}Z",
        }
        for i in range(5)
    ]

    # Generate a mock deviation score
    # Score range: 0.0 (on-track) to 1.0 (completely deviated)
    deviation_score = round(random.uniform(0.0, 0.45), 2)

    # Force a high deviation/anomaly if request matches custom testing patterns
    if ride_id.startswith("anomaly_") or "anomaly" in ride_id.lower():
        deviation_score = 0.85

    status = "normal" if deviation_score < 0.5 else "anomaly_detected"

    return {
        "ride_id": ride_id,
        "gps_points": gps_points,
        "deviation_score": deviation_score,
        "status": status,
        "details": (
            "GPS trace matches the expected route."
            if status == "normal"
            else "Ride route deviates significantly from the pre-calculated path."
        ),
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
