from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool

from .tools import add_numbers, explain_text, get_utc_time

# FastMCP with explicit ServerSession
mcp = FastMCP("sample-tools")


@mcp.tool()
def add_numbers_tool(a: float, b: float) -> float:
    """Add two numbers and return the result."""
    return add_numbers(a, b)


@mcp.tool()
def get_utc_time_tool() -> str:
    """Return current UTC time in ISO-8601 format."""
    return get_utc_time()


@mcp.tool()
def explain_text_tool(text: str) -> str:
    """Prefix input text with 'Explain'."""
    return explain_text(text)


def run() -> None:
    """Run MCP server with stdio transport for robustness."""
    # Silently run stdio transport; all output must be JSONRPC for client parsing
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run()
