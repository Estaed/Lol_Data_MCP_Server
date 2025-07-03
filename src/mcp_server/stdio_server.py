#!/usr/bin/env python3
"""
Stdio-based MCP Server for Cursor Integration.

This module provides a stdio-based MCP server that communicates via stdin/stdout
for integration with Cursor and other MCP clients that expect stdio protocol.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

from src.mcp_server.mcp_handler import MCPHandler

import structlog

# Configure logging to go to stderr with minimal output for MCP compliance
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class StdioMCPServer:
    """
    Stdio-based MCP server for Cursor integration.
    
    Communicates via stdin/stdout using the MCP protocol specification.
    """

    def __init__(self):
        """Initialize the stdio MCP server."""
        self.handler = None
        self.running = True

    async def initialize(self):
        """Initialize the MCP handler."""
        try:
            self.handler = MCPHandler()
            await self.handler.initialize()
            # Only log critical startup info to stderr
            print("Stdio MCP Server initialized", file=sys.stderr)
        except Exception as e:
            print(f"Failed to initialize MCP handler: {e}", file=sys.stderr)
            raise

    async def run(self):
        """Run the stdio MCP server."""
        await self.initialize()
        
        print("Starting stdio MCP server for Cursor integration", file=sys.stderr)
        
        try:
            while self.running:
                try:
                    # Read from stdin with proper async handling
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, sys.stdin.readline
                    )
                    
                    if not line:
                        # EOF reached
                        break
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse JSON message
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON received: {e}", file=sys.stderr)
                        continue
                    
                    # Process message
                    if self.handler:
                        response = await self.handler.handle_message(message)
                        
                        # Send response to stdout with proper formatting
                        if response:
                            response_json = json.dumps(response, ensure_ascii=False)
                            print(response_json, flush=True)
                
                except Exception as e:
                    print(f"Error processing message: {e}", file=sys.stderr)
                    # Send proper error response
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e),
                        },
                    }
                    print(json.dumps(error_response), flush=True)
        
        except KeyboardInterrupt:
            print("Server stopped by user", file=sys.stderr)
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.handler:
                await self.handler.cleanup()
            print("Stdio MCP Server shutdown complete", file=sys.stderr)
        except Exception as e:
            print(f"Cleanup error: {e}", file=sys.stderr)


async def main():
    """Main function to start the stdio MCP server."""
    try:
        server = StdioMCPServer()
        await server.run()
    except Exception as e:
        print(f"Failed to start MCP server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Ensure we're running with proper setup
    asyncio.run(main()) 