#!/usr/bin/env python3
"""
Stdio-based MCP Server for Cursor Integration.

This module provides a stdio-based MCP server that communicates via stdin/stdout
for integration with Cursor and other MCP clients that expect stdio protocol.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directories to path for proper imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.mcp_handler import MCPHandler
import structlog

# Configure structured logging to stderr to avoid interfering with stdio protocol
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
        self.handler = MCPHandler()
        await self.handler.initialize()
        logger.info("Stdio MCP Server initialized", file=sys.stderr)

    async def run(self):
        """Run the stdio MCP server."""
        await self.initialize()
        
        logger.info("Starting stdio MCP server for Cursor integration", file=sys.stderr)
        
        try:
            while self.running:
                try:
                    # Read from stdin
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
                        logger.debug("Received MCP message", message=message, file=sys.stderr)
                    except json.JSONDecodeError as e:
                        logger.error("Invalid JSON received", error=str(e), file=sys.stderr)
                        continue
                    
                    # Process message
                    response = await self.handler.handle_message(message)
                    
                    # Send response to stdout
                    if response:
                        print(json.dumps(response))
                        sys.stdout.flush()
                        logger.debug("Sent MCP response", response=response, file=sys.stderr)
                
                except Exception as e:
                    logger.error("Error processing message", error=str(e), file=sys.stderr)
                    # Send error response
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                            "data": str(e),
                        },
                    }
                    print(json.dumps(error_response))
                    sys.stdout.flush()
        
        except KeyboardInterrupt:
            logger.info("Server stopped by user", file=sys.stderr)
        except Exception as e:
            logger.error("Server error", error=str(e), file=sys.stderr)
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup resources."""
        if self.handler:
            await self.handler.cleanup()
        logger.info("Stdio MCP Server shutdown complete", file=sys.stderr)


async def main():
    """Main function to start the stdio MCP server."""
    server = StdioMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main()) 