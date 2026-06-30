from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from app.config import Settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


@asynccontextmanager
async def open_mcp_session(settings: Settings) -> AsyncGenerator:
    """Open an MCP session using a remote server URL or stdio subprocess transport."""
    # Defer MCP imports until actually needed (they can block on initialization)
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client

    if settings.mcp_server_url:
        logger.info("Connecting to external MCP server at %s", settings.mcp_server_url)
        try:
            async with streamable_http_client(settings.mcp_server_url) as (
                read_stream,
                write_stream,
                close_fn,
            ):
                logger.debug("streamable_http_client connected")
                async with ClientSession(read_stream, write_stream) as session:
                    logger.info("Initializing MCP session")
                    await session.initialize()
                    logger.info("MCP session initialized")
                    logger.debug(
                        f"Available tools: {[t.name for t in (await session.list_tools()).tools]}"
                    )
                    yield session
        except Exception as exc:
            logger.error(
                "Failed to open remote MCP session: %s",
                exc,
                exc_info=True,
            )
            raise

    logger.info("Starting MCP stdio session (subprocess)...")
    repo_root = Path(__file__).resolve().parents[2]
    server = StdioServerParameters(
        command=sys.executable,
        args=["-u", "-m", "mcp_server.server"],
        env={"PYTHONPATH": str(repo_root / "src")},
        cwd=str(repo_root),
    )

    try:
        logger.debug(f"Spawning MCP server subprocess: {server.command} {server.args} cwd={server.cwd}")
        async with stdio_client(server) as (read_stream, write_stream):
            logger.debug("stdio_client connected")
            async with ClientSession(read_stream, write_stream) as session:
                logger.info("Initializing MCP session")
                await session.initialize()
                logger.info("MCP session initialized")
                logger.debug(
                    f"Available tools: {[t.name for t in (await session.list_tools()).tools]}"
                )
                yield session
    except Exception as exc:
        logger.error(f"Failed to open MCP session: {exc}", exc_info=True)
        raise
