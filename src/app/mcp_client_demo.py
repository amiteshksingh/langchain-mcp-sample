from __future__ import annotations

import asyncio
from typing import Any

from .config import load_settings
from .mcp_client import open_mcp_session


def _result_to_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, list) and content:
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text is not None:
                parts.append(str(text))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(result)


async def run_demo() -> None:
    settings = load_settings()
    async with open_mcp_session(settings) as session:
        tools = await session.list_tools()
        tool_names = [tool.name for tool in getattr(tools, "tools", [])]
        print("Available MCP tools:", ", ".join(tool_names))

        add_result = await session.call_tool("add_numbers_tool", {"a": 12.5, "b": 7.5})
        print("add_numbers_tool result:", _result_to_text(add_result))

        time_result = await session.call_tool("get_utc_time_tool", {})
        print("get_utc_time_tool result:", _result_to_text(time_result))


if __name__ == "__main__":
    asyncio.run(run_demo())