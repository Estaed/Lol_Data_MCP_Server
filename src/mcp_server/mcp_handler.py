"""
MCP Protocol message handler for League of Legends data server.

This module implements the core MCP protocol message handling including
initialization, tool listing, and tool execution for LoL data access.
"""

from typing import Any, Dict, List, Optional, Union
import uuid
from datetime import datetime

import structlog

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
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {}
            }
        }
        
        self.tools = {}
        self.clients = {}
        self.initialized = False
    
    async def initialize(self):
        """Initialize the MCP handler and load available tools."""
        logger.info("Initializing MCP handler")
        
        # Initialize basic tools (will be expanded in later tasks)
        self._register_basic_tools()
        
        self.initialized = True
        logger.info("MCP handler initialized", tools_count=len(self.tools))
    
    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up MCP handler")
        self.clients.clear()
        self.tools.clear()
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
                    message_id, 
                    -32601, 
                    f"Method not found: {method}"
                )
                
        except Exception as e:
            logger.error("Error handling MCP message", error=str(e), message=message)
            return self._create_error_response(
                message.get("id"),
                -32603,
                f"Internal error: {str(e)}"
            )
    
    async def _handle_initialize(self, message_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
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
        
        logger.info("Client initializing", client_info=client_info, protocol_version=protocol_version)
        
        # Store client information
        client_id = str(uuid.uuid4())
        self.clients[client_id] = {
            "info": client_info,
            "protocol_version": protocol_version,
            "connected_at": datetime.utcnow().isoformat()
        }
        
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "protocolVersion": protocol_version,
                "capabilities": self.server_info["capabilities"],
                "serverInfo": {
                    "name": self.server_info["name"],
                    "version": self.server_info["version"]
                },
                "instructions": "League of Legends data MCP server ready. Use tools/list to see available tools."
            }
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
    
    async def _handle_list_tools(self, message_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
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
        for tool_name, tool_info in self.tools.items():
            tools_list.append({
                "name": tool_name,
                "description": tool_info["description"],
                "inputSchema": tool_info["inputSchema"]
            })
        
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "tools": tools_list
            }
        }
    
    async def _handle_call_tool(self, message_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
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
        
        if tool_name not in self.tools:
            return self._create_error_response(
                message_id,
                -32602,
                f"Tool not found: {tool_name}"
            )
        
        try:
            # Execute the tool
            tool_handler = self.tools[tool_name]["handler"]
            result = await tool_handler(arguments)
            
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result)
                        }
                    ]
                }
            }
            
        except Exception as e:
            logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
            return self._create_error_response(
                message_id,
                -32603,
                f"Tool execution failed: {str(e)}"
            )
    
    def _create_error_response(self, message_id: Optional[str], code: int, message: str) -> Dict[str, Any]:
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
            "error": {
                "code": code,
                "message": message
            }
        }
    
    def _register_basic_tools(self):
        """Register basic tools for initial server functionality."""
        
        # Basic ping tool for connectivity testing
        self.tools["ping"] = {
            "description": "Test connectivity and server response",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Optional message to echo back",
                        "default": "ping"
                    }
                }
            },
            "handler": self._handle_ping_tool
        }
        
        # Server info tool
        self.tools["server_info"] = {
            "description": "Get server information and status",
            "inputSchema": {
                "type": "object",
                "properties": {}
            },
            "handler": self._handle_server_info_tool
        }
    
    async def _handle_ping_tool(self, arguments: Dict[str, Any]) -> str:
        """
        Handle ping tool execution.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Ping response
        """
        message = arguments.get("message", "ping")
        return f"pong: {message}"
    
    async def _handle_server_info_tool(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle server info tool execution.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            Server information
        """
        return {
            "server": self.server_info,
            "stats": {
                "tools_available": len(self.tools),
                "clients_connected": len(self.clients),
                "uptime": "available after full implementation"
            }
        } 