from __future__ import annotations

import argparse
import asyncio
from typing import Any

import httpx

from app.config import load_settings
from app.llm_factory import build_llm
from app.mcp_client import open_mcp_session


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


def _ensure_provider_ready() -> None:
    settings = load_settings()

    if settings.provider == "huggingface" and not settings.hf_api_key:
        raise RuntimeError(
            "HF_API_KEY is missing. Set HF_API_KEY in .env or switch to Ollama with "
            "LLM_PROVIDER=ollama."
        )

    if settings.provider == "github" and not settings.github_token:
        raise RuntimeError(
            "GITHUB_TOKEN is missing. Set GITHUB_TOKEN in .env or switch provider with "
            "LLM_PROVIDER=ollama or LLM_PROVIDER=huggingface."
        )

    if settings.provider == "ollama":
        base_url = settings.ollama_base_url.rstrip("/")
        try:
            response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(
                "Ollama is not reachable. Start Ollama and ensure OLLAMA_BASE_URL is correct "
                f"(current: {settings.ollama_base_url}). Original error: {exc}"
            ) from exc


async def run_agent_demo(question: str) -> str:
    # Delay langchain imports until actually running (they can block)
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
    from langchain_core.tools import StructuredTool
    import asyncio
    
    print("[agent] Starting agent demo", flush=True)
    print("[agent] Checking provider readiness...", flush=True)
    _ensure_provider_ready()
    print("[agent] Provider ready", flush=True)
    settings = load_settings()
    print(
        f"[agent] settings: provider={settings.provider}, mcp_server_url={settings.mcp_server_url!r}",
        flush=True,
    )
    print("[agent] Building LLM...", flush=True)
    try:
        llm = build_llm(settings)
        print("[agent] LLM initialized successfully", flush=True)
    except Exception as exc:
        raise RuntimeError(f"Failed to initialize LLM provider '{settings.provider}': {exc}") from exc

    async with open_mcp_session(settings) as session:
        print("[agent] MCP session opened", flush=True)

        async def add_numbers_impl(a: float, b: float) -> str:
            """Add two numbers and return the computed sum."""
            print(f"[agent] Calling tool add_numbers_tool with a={a}, b={b}", flush=True)
            result = await session.call_tool("add_numbers_tool", {"a": a, "b": b})
            print(f"[agent] add_numbers_tool result: {result}", flush=True)
            return _result_to_text(result)

        async def get_utc_time_impl() -> str:
            """Get the current UTC time in ISO-8601 format."""
            print("[agent] Calling tool get_utc_time_tool", flush=True)
            result = await session.call_tool("get_utc_time_tool", {})
            print(f"[agent] get_utc_time_tool result: {result}", flush=True)
            return _result_to_text(result)

        # Create structured tools explicitly
        add_numbers_tool = StructuredTool.from_function(
            add_numbers_impl,
            name="add_numbers_tool",
            description="Add two numbers and return the result"
        )
        get_utc_time_tool = StructuredTool.from_function(
            get_utc_time_impl,
            name="get_utc_time_tool",
            description="Get the current UTC time in ISO-8601 format"
        )

        tools = [add_numbers_tool, get_utc_time_tool]
        print(f"[agent] Bound tools: {[t.name for t in tools]}", flush=True)
        llm_with_tools = llm.bind_tools(tools)
        tool_map = {t.name: t for t in tools}

        messages: list[Any] = [
            SystemMessage(
                content=(
                    "You are a concise assistant. Use MCP tools when relevant and "
                    "return a direct final answer."
                )
            ),
            HumanMessage(content=question),
        ]

        for step in range(1, 7):
            print(f"[agent] LLM step {step}: sending {len(messages)} message(s)", flush=True)
            try:
                ai_message = await asyncio.wait_for(
                    llm_with_tools.ainvoke(messages), timeout=settings.timeout_seconds
                )
                print(f"[agent] LLM response received at step {step}", flush=True)
            except TimeoutError as exc:
                raise RuntimeError(
                    "LLM request timed out. Try a smaller/faster model or increase "
                    "LLM_TIMEOUT_SECONDS in .env."
                ) from exc
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "LLM endpoint is unreachable. Verify provider credentials/endpoints, or for "
                    "Ollama ensure the daemon is running and the model is pulled."
                ) from exc
            except Exception as exc:
                print(f"[agent] Unexpected error from LLM: {exc}", flush=True)
                raise

            print(f"[agent] ai_message type: {type(ai_message)}", flush=True)
            try:
                print(f"[agent] ai_message repr: {ai_message!r}", flush=True)
            except Exception as exc:
                print(f"[agent] Failed to repr ai_message: {exc}", flush=True)
            try:
                print(f"[agent] ai_message dict: {getattr(ai_message, '__dict__', None)}", flush=True)
            except Exception as exc:
                print(f"[agent] Failed to inspect ai_message dict: {exc}", flush=True)

            if isinstance(ai_message, str):
                print("[agent] Wrapping raw string response into AIMessage", flush=True)
                ai_message = AIMessage(content=ai_message)
            elif ai_message is None:
                print("[agent] LLM returned None; wrapping empty AIMessage", flush=True)
                ai_message = AIMessage(content="")

            content = getattr(ai_message, 'content', None)
            print(f"[agent] LLM message content: {content!r}", flush=True)
            tool_calls = getattr(ai_message, "tool_calls", None) or []
            print(f"[agent] tool_calls: {tool_calls}", flush=True)
            messages.append(ai_message)

            if not tool_calls:
                print("[agent] No tool calls returned; final answer path", flush=True)
                if content is None:
                    print("[agent] Final content is None; returning empty string", flush=True)
                    return ""
                return str(content)

            for call in tool_calls:
                tool_name = call.get("name", "")
                tool_args = call.get("args", {})
                tool_id = call.get("id", "")

                print(f"[agent] Processing tool call: name={tool_name}, id={tool_id}, args={tool_args}", flush=True)
                if tool_name not in tool_map:
                    print(f"[agent] Tool '{tool_name}' is not available", flush=True)
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_id,
                            content=f"Tool '{tool_name}' is not available.",
                        )
                    )
                    continue

                try:
                    result = await tool_map[tool_name].ainvoke(tool_args)
                    result_text = _result_to_text(result)
                    print(f"[agent] Tool '{tool_name}' result: {result_text}", flush=True)
                    messages.append(
                        ToolMessage(
                            name=tool_name,
                            tool_call_id=tool_id,
                            content=result_text,
                        )
                    )
                except Exception as exc:
                    print(f"[agent] Tool '{tool_name}' failed: {exc}", flush=True)
                    messages.append(
                        ToolMessage(
                            tool_call_id=tool_id,
                            content=f"Tool execution failed: {exc}",
                        )
                    )

        print("[agent] Reached max step limit without final answer", flush=True)
        return "Agent did not finish within the step limit."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a single-command LangChain + MCP orchestration demo"
    )
    parser.add_argument(
        "--question",
        default="What time is it in UTC, and what is 14.5 + 10.5?",
        help="Question to send to the tool-enabled LangChain flow",
    )
    return parser.parse_args()


if __name__ == "__main__":
    print("[__main__] Starting agent_mcp_demo", flush=True)
    args = parse_args()
    print(f"[__main__] Question: {args.question}", flush=True)
    try:
        print("[__main__] Running agent...", flush=True)
        result = asyncio.run(run_agent_demo(args.question))
        print(result)
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)