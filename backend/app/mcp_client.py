"""MCP Client Manager for discovering and invoking external tools."""

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class MCPClientManager:
    """Manages connections to MCP servers and handles tool discovery and invocation."""

    def __init__(
        self,
        telemetry_server_url: str = "http://localhost:8001",
        billing_server_url: str = "http://localhost:8002",
        timeout: float = 30.0,
    ):
        """Initialize the MCP Client Manager.

        Args:
            telemetry_server_url: URL to the telemetry MCP server.
            billing_server_url: URL to the billing MCP server.
            timeout: Request timeout in seconds.
        """
        self.telemetry_server_url = telemetry_server_url
        self.billing_server_url = billing_server_url
        self.timeout = timeout

        # Available tools registry: {tool_name: (server_url, tool_config)}
        self._tools_registry: dict[str, tuple[str, dict[str, Any]]] = {}
        self._is_initialized = False

    async def initialize(self) -> None:
        """Discover available tools from all registered MCP servers."""
        if self._is_initialized:
            return

        logger.info("Starting MCP server discovery...")

        # Discover tools from telemetry server
        await self._discover_tools_from_server(
            "telemetry", self.telemetry_server_url
        )

        # Discover tools from billing server
        await self._discover_tools_from_server("billing", self.billing_server_url)

        logger.info(
            "MCP discovery complete",
            tools_count=len(self._tools_registry),
            tools=list(self._tools_registry.keys()),
        )
        self._is_initialized = True

    async def _discover_tools_from_server(
        self, server_name: str, server_url: str
    ) -> None:
        """Discover available tools from a specific MCP server.

        Args:
            server_name: Friendly name of the server for logging.
            server_url: Base URL of the MCP server.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{server_url}/tools", follow_redirects=True
                )
                response.raise_for_status()

                tools_data = response.json()
                tools = tools_data.get("tools", [])

                for tool in tools:
                    tool_name = tool.get("name")
                    if tool_name:
                        self._tools_registry[tool_name] = (server_url, tool)
                        logger.info(
                            f"Discovered tool from {server_name}",
                            tool_name=tool_name,
                        )

        except Exception as e:
            logger.warning(
                f"Failed to discover tools from {server_name}",
                server_url=server_url,
                error=str(e),
            )

    async def invoke_tool(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a specific tool on the appropriate MCP server.

        Args:
            tool_name: Name of the tool to invoke.
            tool_input: Arguments to pass to the tool.

        Returns:
            The result from the tool execution.

        Raises:
            ValueError: If the tool is not found.
        """
        if tool_name not in self._tools_registry:
            logger.error("Tool not found", tool_name=tool_name)
            raise ValueError(f"Tool '{tool_name}' not found in registry")

        server_url, _tool_config = self._tools_registry[tool_name]

        try:
            logger.info(
                "Invoking tool",
                tool_name=tool_name,
                server_url=server_url,
                input=tool_input,
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{server_url}/invoke",
                    json={"tool_name": tool_name, "input": tool_input},
                )
                response.raise_for_status()

                result = response.json()
                logger.info(
                    "Tool invocation succeeded",
                    tool_name=tool_name,
                    result=result,
                )
                return result

        except Exception as e:
            logger.error(
                "Tool invocation failed",
                tool_name=tool_name,
                error=str(e),
            )
            raise

    def get_tools(self) -> dict[str, dict[str, Any]]:
        """Get all discovered tools.

        Returns:
            Dictionary mapping tool names to their configurations.
        """
        return {
            name: tool_config
            for name, (_server_url, tool_config) in self._tools_registry.items()
        }

    def get_tool(self, tool_name: str) -> dict[str, Any] | None:
        """Get a specific tool configuration.

        Args:
            tool_name: Name of the tool.

        Returns:
            Tool configuration if found, None otherwise.
        """
        if tool_name in self._tools_registry:
            _server_url, tool_config = self._tools_registry[tool_name]
            return tool_config
        return None

    def is_initialized(self) -> bool:
        """Check if the MCP client has been initialized.

        Returns:
            True if initialized, False otherwise.
        """
        return self._is_initialized
