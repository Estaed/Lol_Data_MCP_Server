"""
MCP Protocol message handler for League of Legends data server.

This module implements the core MCP protocol message handling including
initialization, tool listing, and tool execution for LoL data access.
"""

from typing import Any, Dict, Optional
import uuid
from datetime import datetime

import structlog
from .tools import ToolRegistry

logger = structlog.get_logger()


class MCPHandler:
    """
    Handles MCP protocol messages and implements core MCP functionality.

    This class processes incoming MCP messages, manages client sessions,
    and provides responses according to the MCP specification.
    """

    def __init__(self):
        """Initialize the MCP handler."""
        self.server_info = {
            "name": "lol-data-mcp-server",
            "version": "1.0.0",
            "description": "League of Legends data provider via MCP protocol",
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
        }

        self.tool_registry = ToolRegistry()
        self.clients = {}
        self.initialized = False

    async def initialize(self):
        """Initialize the MCP handler and load available tools."""
        logger.info("Initializing MCP handler")

        # Tools are already registered in ToolRegistry during initialization
        self.initialized = True
        total_tools = len(self.tool_registry.list_tools())
        logger.info("MCP handler initialized", tools_count=total_tools)

    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up MCP handler")
        self.clients.clear()
        self.initialized = False

    async def is_healthy(self) -> bool:
        """Check if the handler is healthy and ready to serve requests."""
        return self.initialized

    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle an incoming MCP message and return appropriate response.

        Args:
            message: Parsed JSON message from client

        Returns:
            Response dictionary or None if no response needed
        """
        try:
            method = message.get("method")
            params = message.get("params", {})
            message_id = message.get("id")

            logger.debug("Processing MCP message", method=method, id=message_id)

            # Handle different MCP methods
            if method == "initialize":
                return await self._handle_initialize(message_id, params)
            elif method == "notifications/initialized":
                return await self._handle_initialized(params)
            elif method == "tools/list":
                return await self._handle_list_tools(message_id, params)
            elif method == "tools/call":
                return await self._handle_call_tool(message_id, params)
            else:
                return self._create_error_response(
                    message_id, -32601, f"Method not found: {method}"
                )

        except Exception as e:
            logger.error("Error handling MCP message", error=str(e), message=message)
            return self._create_error_response(
                message.get("id"), -32603, f"Internal error: {str(e)}"
            )

    async def _handle_initialize(
        self, message_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle MCP initialize request.

        Args:
            message_id: Message ID for response
            params: Initialize parameters from client

        Returns:
            Initialize response
        """
        client_info = params.get("clientInfo", {})
        protocol_version = params.get("protocolVersion", "2024-11-05")

        logger.info(
            "Client initializing",
            client_info=client_info,
            protocol_version=protocol_version,
        )

        # Store client information
        client_id = str(uuid.uuid4())
        self.clients[client_id] = {
            "info": client_info,
            "protocol_version": protocol_version,
            "connected_at": datetime.utcnow().isoformat(),
        }

        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "protocolVersion": protocol_version,
                "capabilities": self.server_info["capabilities"],
                "serverInfo": {
                    "name": self.server_info["name"],
                    "version": self.server_info["version"],
                },
                "instructions": (
                    "League of Legends data MCP server ready. "
                    "Use tools/list to see available tools."
                ),
            },
        }

    async def _handle_initialized(self, params: Dict[str, Any]) -> None:
        """
        Handle initialized notification from client.

        Args:
            params: Notification parameters
        """
        logger.info("Client initialization complete")
        # No response needed for notifications
        return None

    async def _handle_list_tools(
        self, message_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle tools/list request.

        Args:
            message_id: Message ID for response
            params: List tools parameters

        Returns:
            Tools list response
        """
        logger.debug("Listing available tools")

        tools_list = []
        
        # Add all tools from ToolRegistry (includes both basic and LoL data tools)
        for tool_schema in self.tool_registry.list_tools():
            tools_list.append({
                "name": tool_schema.name,
                "description": tool_schema.description,
                "inputSchema": tool_schema.input_schema,
            })

        return {"jsonrpc": "2.0", "id": message_id, "result": {"tools": tools_list}}

    async def _handle_call_tool(
        self, message_id: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle tools/call request.

        Args:
            message_id: Message ID for response
            params: Tool call parameters

        Returns:
            Tool execution response
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        logger.info("Calling tool", tool_name=tool_name, arguments=arguments)

        # Use unified ToolRegistry for all tools
        tool = self.tool_registry.get_tool(tool_name)
        if tool:
            try:
                result = await tool.execute(arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {"content": [{"type": "text", "text": str(result)}]},
                }
            except Exception as e:
                logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
                return self._create_error_response(
                    message_id, -32603, f"Tool execution failed: {str(e)}"
                )

        return self._create_error_response(
            message_id, -32602, f"Tool not found: {tool_name}"
        )

    def _create_error_response(
        self, message_id: Optional[str], code: int, message: str
    ) -> Dict[str, Any]:
        """
        Create a standardized error response.

        Args:
            message_id: Original message ID
            code: Error code
            message: Error message

        Returns:
            Error response dictionary
        """
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {"code": code, "message": message},
        }


