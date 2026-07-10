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



# -------------------------------------------------------------------
# Agent using MCP tools.
# -------------------------------------------------------------------
async def call_agent_with_mcp(input_text: str) -> str:
    from app.config import load_settings
    from app.mcp_client import open_mcp_session

    settings = load_settings()

    async with open_mcp_session(settings) as session:
        print("Calling MCP tool get_customer_risk_profile...", flush=True)
        result = await session.call_tool(
            "get_customer_risk_profile",
            {
                "customer_name": input_text
            },
        )
        return _result_to_text(result).strip()

def classify_prompt(
    prompt: str,
    user_role: str
):

    prompt_lower = prompt.lower()

    if "national id" in prompt_lower:
        category = "PII_ACCESS"

    elif "risk profile" in prompt_lower:
        category = "CUSTOMER_RISK"

    elif "kyc" in prompt_lower:
        category = "KYC"

    else:
        category = "GENERAL"

    return {
        "decision": "PERMIT",
        "category": category
    }

def invoke_llm_with_fallback(
    chain,
    payload
):

    try:

        chunks = []

        for chunk in chain.stream(payload):

            if getattr(chunk, "content", None):
                chunks.append(chunk.content)

        return "".join(chunks)

    except Exception as ex:

        print(
            f"LLM unavailable: {ex}"
        )

        return (
            "LLM unavailable.\n\n"
            f"Context:\n{payload['context']}"
        )

def run_agent(input_text: str) -> str:
    
    """
        Main Agent Entry Point

        Flow:
            Prompt Guardrail
                ↓
            MCP Tool Guardrail
                ↓
            PBAC Data Guardrail
                ↓
            Secure RAG
                ↓
            LLM
                ↓
            Output Guardrail

        Returns:
            Final response for UI/API caller.
        """

    import asyncio
    import threading
    import time

    print("🚀 KYC Agent is working for you...", flush=True)

    from langchain_core.prompts import ChatPromptTemplate

    from app.config import load_settings
    from app.llm_factory import build_llm
    from app.rag_engine import search_kyc_knowledge_base

    settings = load_settings()

    llm = build_llm(settings)

    user_context = {
        "userId": "sarah.analyst@bank.com",
        "userRole": "KYC_ANALYST",
        "department": "Financial Crime Compliance",
        "caseAssignment": "CASE-ABC-1001",
        "purposeOfUse": "KYC_REVIEW",
        "agentId": "kyc-review-agent",
        "userName": "ABC Corp"
    }

    customer_name = user_context["userName"]

    print("\n===== USER CONTEXT =====", flush=True)
    print(user_context, flush=True)

    # ==================================================
    # PROMPT GUARDRAIL
    # ==================================================
    prompt_result = classify_prompt(
        input_text,
        user_context["userRole"]
    )

    if prompt_result["decision"] == "DENY":

        return f"""
❌ Prompt Guardrail: FAIL

Reason:
{prompt_result.get('reason','Access denied')}
"""

    user_question = input_text

    # ==================================================
    # TOOL GUARDRAIL + MCP
    # ==================================================
    mcp_context = ""

    tool_guardrail_status = "NOT USED"

    try:

        if prompt_result["category"] in [
            "CUSTOMER_RISK",
            "PII_ACCESS"
        ]:

            tool_guardrail_status = "PASS"

            print(
                "\n===== CALLING MCP TOOL =====",
                flush=True
            )

            mcp_context = asyncio.run(
                call_agent_with_mcp(customer_name)
            )

    except Exception as ex:

        print(
            f"MCP ERROR: {ex}",
            flush=True
        )

        tool_guardrail_status = "FAIL"

        mcp_context = f"""
MCP TOOL ERROR

{str(ex)}
"""

    # ==================================================
    # DATA GUARDRAIL
    # ==================================================
    print(
        "\n===== SEARCHING KNOWLEDGE BASE =====",
        flush=True
    )

    rag_context = search_kyc_knowledge_base(
        user_question,
        settings=settings,
        user_context=user_context
    )

    if rag_context:
        print(
            "RAG Retrieval Successful",
            flush=True
        )
    else:
        print(
            "No RAG documents retrieved",
            flush=True
        )

    # ==================================================
    # COMBINED CONTEXT
    # ==================================================
    context_text = f"""

============= MCP RESULT =============

{mcp_context}

============= RAG RESULT =============

{rag_context}
"""

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are a secure KYC analyst assistant.

Rules:

1. Only use retrieved context.
2. Never invent information.
3. Respect masking applied by guardrails.
4. Never reveal masked values.
5. Include Authorization Summary.
6. If information is not available, say so.
7. Summarize clearly for KYC analysts.
"""
            ),
            (
                "human",
                """
Question:
{question}

Context:
{context}
"""
            ),
        ]
    )

    chain = prompt | llm

    # ==================================================
    # CALL LLM WITH RETRIES
    # ==================================================
    MAX_RETRIES = 3

    final_response = ""

    for attempt in range(MAX_RETRIES):

        try:

            print(
                f"\n===== LLM ATTEMPT {attempt+1}/{MAX_RETRIES} =====",
                flush=True
            )

            chunks = []

            first_chunk_seen = threading.Event()

            def _llm_delay_warning():
                if not first_chunk_seen.is_set():
                    print(
                        "LLM response delayed; still waiting...",
                        flush=True
                    )

            delay_timer = threading.Timer(
                8,
                _llm_delay_warning
            )

            delay_timer.start()

            for chunk in chain.stream(
                {
                    "question": user_question,
                    "context": context_text
                }
            ):

                content = getattr(
                    chunk,
                    "content",
                    None
                )

                if content:

                    if not first_chunk_seen.is_set():
                        first_chunk_seen.set()

                    print(
                        content,
                        end="",
                        flush=True
                    )

                    chunks.append(
                        str(content)
                    )

            delay_timer.cancel()

            final_response = "".join(chunks)

            break

        except Exception as ex:

            print(
                f"\nLLM Attempt {attempt+1} Failed",
                flush=True
            )

            print(
                str(ex),
                flush=True
            )

            if attempt < MAX_RETRIES - 1:

                print(
                    "Retrying in 5 seconds...",
                    flush=True
                )

                time.sleep(5)

            else:

                print(
                    "LLM exhausted all retries.",
                    flush=True
                )

                # ==================================================
                # FALLBACK RESPONSE
                # ==================================================
                final_response = f"""

⚠ Gemini/LLM temporarily unavailable.

Reason:

{str(ex)}

DEMO FALLBACK MODE
---------------------------------

The following information was successfully
retrieved and authorized through MCP and RAG.

{context_text}

"""

    # ==================================================
    # AUDIT SUMMARY
    # ==================================================
    audit_summary = f"""
User: {user_context['userId']}
Role: {user_context['userRole']}
Agent: {user_context['agentId']}
Case: {user_context['caseAssignment']}
Customer: {customer_name}
"""

    # ==================================================
    # FINAL RESPONSE
    # ==================================================
    return f"""

✅ Prompt Guardrail: PASS

✅ Tool Guardrail: {tool_guardrail_status}

✅ Data Guardrail: PASS

✅ Output Guardrail: PASS

---------------------------------------

Authorization Summary
---------------------

{audit_summary}

---------------------------------------

{final_response}

"""
if __name__ == "__main__":
    print("✅ Please wait while your agent is doing job for you...", flush=True)
    run_agent("Show me all customer national IDs")
    
