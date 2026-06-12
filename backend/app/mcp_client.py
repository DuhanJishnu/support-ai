"""MCP Client Manager for discovering and invoking external tools."""

from typing import Any

import structlog
from fastmcp import Client
from pydantic import BaseModel

logger = structlog.get_logger(__name__)


class MCPClientManager:
    """Manages connections to MCP servers and handles tool discovery and invocation."""

    def __init__(
        self,
        server_urls: list[str] | None = None,
        telemetry_server_url: str | None = "http://telemetry:8001/sse",
        billing_server_url: str | None = "http://billing:8002/sse",
        timeout: float = 30.0,
    ):
        """Initialize the MCP Client Manager.

        Args:
            server_urls: URLs to MCP servers.
            telemetry_server_url: Legacy URL to the telemetry MCP server.
            billing_server_url: Legacy URL to the billing MCP server.
            timeout: Request timeout in seconds.
        """
        self.server_urls = server_urls or [
            url for url in (telemetry_server_url, billing_server_url) if url
        ]
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

        for server_url in self.server_urls:
            await self._discover_tools_from_server(server_url, server_url)

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
            async with Client(server_url, timeout=self.timeout) as client:
                tools = await client.list_tools()

            for tool in tools:
                tool_config = self._serialize_model(tool)
                tool_name = tool_config.get("name")
                if tool_name:
                    self._tools_registry[tool_name] = (server_url, tool_config)
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

            async with Client(server_url, timeout=self.timeout) as client:
                result = await client.call_tool(tool_name, tool_input)

            serialized_result = self._serialize_tool_result(result)
            logger.info(
                "Tool invocation succeeded",
                tool_name=tool_name,
                result=serialized_result,
            )
            return serialized_result

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

    @staticmethod
    def _serialize_model(value: Any) -> dict[str, Any]:
        """Serialize MCP/Pydantic objects into JSON-ready dictionaries."""
        if isinstance(value, BaseModel):
            return value.model_dump(by_alias=True, exclude_none=True)
        if isinstance(value, dict):
            return value
        return dict(value)

    @classmethod
    def _serialize_tool_result(cls, result: Any) -> dict[str, Any]:
        """Serialize FastMCP call results while preserving structured data."""
        data = getattr(result, "data", None)
        if data is not None:
            return {"data": data}

        structured_content = getattr(result, "structured_content", None)
        if structured_content is not None:
            return {"data": structured_content}

        return cls._serialize_model(result)
