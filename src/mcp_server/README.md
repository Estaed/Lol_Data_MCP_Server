# MCP Server Internals

This directory contains the core components responsible for running the Model Context Protocol (MCP) server.

## File Breakdown

-   **`stdio_server.py`**: This is the main entry point for the server when integrating with an IDE like Cursor. It uses standard input/output (`stdio`) to communicate with the client, which is the standard way MCP servers are hosted in such environments. It initializes the `MCPHandler` and listens for incoming requests.

-   **`mcp_handler.py`**: This file contains the `MCPHandler` class, which is the brain of the server. It's responsible for:
    -   Parsing incoming JSON-RPC 2.0 requests.
    -   Validating the request format.
    -   Identifying which tool is being called.
    -   Executing the corresponding tool from the `ToolRegistry`.
    -   Catching any errors during tool execution.
    -   Formatting the response (or error) and sending it back to the client.

-   **`tools.py`**: This file defines the public-facing tools that the MCP server exposes. It uses a `ToolRegistry` to collect and manage all available tools. Each tool is a function decorated with `@tool_registry.register` which makes it discoverable by the handler. These functions are the bridge between the MCP protocol and the application's business logic (i.e., the services).

-   **`server.py`**: This file contains a standard FastAPI web server setup. While the primary hosting mechanism for IDE integration is `stdio_server.py`, this file is kept for standalone testing and development. It allows you to run the MCP server as a web service, accessible via HTTP, which can be useful for debugging tools with tools like `curl` or Postman. 