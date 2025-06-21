"""
MCP Server implementation for League of Legends data.

This module provides the main FastAPI server that implements the Model Context Protocol
for serving LoL champion, item, and game data to development environments and AI agents.
"""

import asyncio
import json
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import structlog
import uvicorn

from .mcp_handler import MCPHandler


# Configure structured logging
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    logger.info("Starting LoL Data MCP Server...")

    # Initialize MCP handler
    app.state.mcp_handler = MCPHandler()
    await app.state.mcp_handler.initialize()

    logger.info("MCP Server started successfully")
    yield

    # Cleanup
    logger.info("Shutting down LoL Data MCP Server...")
    if hasattr(app.state, "mcp_handler"):
        await app.state.mcp_handler.cleanup()
    logger.info("MCP Server shutdown complete")


class MCPServer:
    """
    Main MCP server class that implements the Model Context Protocol for LoL data.

    Provides WebSocket endpoints for MCP protocol communication and REST endpoints
    for health checking and basic server management.
    """

    def __init__(self, host: str = "localhost", port: int = 8000):
        """
        Initialize the MCP server.

        Args:
            host: Server host address
            port: Server port number
        """
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="LoL Data MCP Server",
            description="Model Context Protocol server for League of Legends game data",
            version="1.0.0",
            lifespan=lifespan,
        )

        self._setup_routes()
        self._setup_signal_handlers()

    def _setup_routes(self):
        """Set up FastAPI routes."""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint for monitoring server status."""
            try:
                handler = getattr(self.app.state, "mcp_handler", None)
                if handler and await handler.is_healthy():
                    return JSONResponse(
                        {
                            "status": "healthy",
                            "service": "lol-data-mcp-server",
                            "version": "1.0.0",
                        }
                    )
                else:
                    raise HTTPException(status_code=503, detail="Service unhealthy")
            except Exception as e:
                logger.error("Health check failed", error=str(e))
                raise HTTPException(status_code=503, detail="Service unhealthy")

        @self.app.websocket("/mcp")
        async def mcp_websocket_endpoint(websocket: WebSocket):
            """Main MCP protocol WebSocket endpoint."""
            await self._handle_mcp_connection(websocket)

    async def _handle_mcp_connection(self, websocket: WebSocket):
        """
        Handle a single MCP WebSocket connection.

        Args:
            websocket: FastAPI WebSocket connection
        """
        await websocket.accept()
        client_id = id(websocket)

        logger.info("MCP client connected", client_id=client_id)

        try:
            handler = self.app.state.mcp_handler

            while True:
                # Receive message from client
                try:
                    message = await websocket.receive_text()
                    logger.debug(
                        "Received MCP message", client_id=client_id, message=message
                    )

                    # Parse JSON message
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError as e:
                        await self._send_error(websocket, "Invalid JSON", str(e))
                        continue

                    # Process MCP message
                    response = await handler.handle_message(data)

                    # Send response back to client
                    if response:
                        await websocket.send_text(json.dumps(response))
                        logger.debug(
                            "Sent MCP response", client_id=client_id, response=response
                        )

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(
                        "Error processing MCP message",
                        client_id=client_id,
                        error=str(e),
                    )
                    await self._send_error(websocket, "Internal server error", str(e))

        except Exception as e:
            logger.error(
                "WebSocket connection error", client_id=client_id, error=str(e)
            )
        finally:
            logger.info("MCP client disconnected", client_id=client_id)

    async def _send_error(self, websocket: WebSocket, error_type: str, message: str):
        """
        Send an error response to the client.

        Args:
            websocket: WebSocket connection
            error_type: Type of error
            message: Error message
        """
        error_response = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": error_type,
                "data": message,
            },  # Internal error
        }

        try:
            await websocket.send_text(json.dumps(error_response))
        except Exception as e:
            logger.error("Failed to send error response", error=str(e))

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info("Received shutdown signal", signal=signum)
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start(self):
        """Start the MCP server."""
        logger.info("Starting MCP server", host=self.host, port=self.port)

        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=True,
        )

        server = uvicorn.Server(config)
        await server.serve()

    def run(self):
        """Run the MCP server (blocking call)."""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error("Server error", error=str(e))
            raise


if __name__ == "__main__":
    # Basic server startup for development
    server = MCPServer()
    server.run()
