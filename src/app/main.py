from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any


print("✅ main.py module loaded", flush=True)


# Suppress noisy httpx/httpcore/debug logs
logging.basicConfig(level=logging.WARNING)

for noisy_logger in ["httpx", "httpcore", "asyncio"]:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)


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


async def _build_llm_input_from_mcp(input_text: str) -> str:
    """
    MCP is optional. Keep import lazy so startup does not block.
    """
    from app.config import load_settings
    from app.mcp_client import open_mcp_session

    settings = load_settings()

    async with open_mcp_session(settings) as session:
        print("Calling MCP tool explain_text_tool...", flush=True)
        result = await session.call_tool(
            "explain_text_tool",
            {"text": input_text},
        )
        return _result_to_text(result).strip()


def run_demo(input_text: str = "Artificial Intelligence") -> str:
    t0 = time.time()
    print("🚀 Starting run_demo...", flush=True)


    print("Before langchain_core import", flush=True)
    t1 = time.time()

    from langchain_core.prompts import ChatPromptTemplate
    print(f"langchain_core import took {time.time()-t1:.2f}s", flush=True)

    t2 = time.time()
    print("Before config import", flush=True)
    from app.config import load_settings
    print(f"load_settings took {time.time()-t2:.2f}s", flush=True)

    from app.llm_factory import build_llm
    from app.rag_engine import query_rag

    settings = load_settings()

    print(
        f"✅ Settings loaded: provider={settings.provider}, "
        f"rag_db={settings.rag_db_dir}, "
        f"embedding={settings.rag_embedding_model}",
        flush=True,
    )

    llm = build_llm(settings)

    # For now, bypass MCP to isolate RAG + Google LLM.
    # Once RAG works, you can switch this back to MCP.
    question = input_text

    print(f"Entered Text: {input_text}", flush=True)

    # If you want MCP again later, enable this:
    question = asyncio.run(_build_llm_input_from_mcp(input_text))

    print(f"Question: {question}", flush=True)

    context_chunks = query_rag(question, settings)

    if context_chunks:
        print(f"RAG retrieved {len(context_chunks)} chunk(s).", flush=True)

        for index, chunk in enumerate(context_chunks, start=1):
            print(f"\n--- Chunk #{index} ---", flush=True)
            print(f"Content:\n{chunk}", flush=True)
            print("-" * 20, flush=True)
    else:
        print("RAG retrieved 0 chunks.", flush=True)

    context_text = "\n\n".join(
        f"Context {idx + 1}:\n{chunk}"
        for idx, chunk in enumerate(context_chunks)
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a concise assistant. Use the provided context when relevant. "
                "If context is insufficient, use your general knowledge but mention it briefly. "
                "Keep answers under 6 lines.",
            ),
            (
                "human",
                "Question: {question}\n\nRetrieved Context:\n{context}",
            ),
        ]
    )

    chain = prompt | llm

    print("\nCalling LLM...", flush=True)

    chunks: list[str] = []
    first_chunk_seen = threading.Event()

    def _llm_delay_warning() -> None:
        if not first_chunk_seen.is_set():
            print("LLM response is delayed; still waiting...", flush=True)

    delay_timer = threading.Timer(8, _llm_delay_warning)
    delay_timer.start()

    for chunk in chain.stream(
        {
            "question": question,
            "context": context_text or "(no context retrieved)",
        }
    ):
        content = getattr(chunk, "content", None)

        if content:
            if not first_chunk_seen.is_set():
                first_chunk_seen.set()

            print(content, end="", flush=True)
            chunks.append(str(content))

    delay_timer.cancel()

    if chunks:
        print()
        return "".join(chunks)

    return ""


if __name__ == "__main__":
    print("✅ Main started", flush=True)
    run_demo("Setup a new project")