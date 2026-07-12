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

def init_guardrails():
    return {
        "prompt": {
            "status": "NOT_EVALUATED",
            "reason": ""
        },
        "tool": {
            "status": "NOT_USED",
            "reason": ""
        },
        "data": {
            "status": "NOT_EVALUATED",
            "reason": ""
        },
        "output": {
            "status": "NOT_USED",
            "reason": ""
        }
    }


def format_guardrail_status(status: str) -> str:
    """
    Convert guardrail status to display icon.
    """

    mapping = {
        "PASS": "✅",
        "FAIL": "❌",
        "NOT_USED": "⚪",
        "NOT_EVALUATED": "⚪"
    }

    return mapping.get(status, "⚪")

#Function to call MCP tool explain_text_tool asynchronously. This has been obselete and replaced with call_agent_with_mcp function which calls get_customer_risk_profile tool. Keeping this for reference.
async def _build_llm_input_from_mcp(input_text: str) -> str:
    """
    MCP is optional. Keep import lazy so startup does not block.
    """
    from .config import load_settings
    from .mcp_client import open_mcp_session

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
async def call_agent_with_mcp(input_text: str, user_context: dict) -> str:
    from .config import load_settings
    from .mcp_client import open_mcp_session

    settings = load_settings()

    async with open_mcp_session(settings) as session:
        print("Calling MCP tool get_customer_risk_profile...", flush=True)
        result = await session.call_tool(
            "get_customer_risk_profile_tool",
            {
                "customer_name": input_text,
                "user_context": user_context
            },
        )
        print("MCP tool get_customer_risk_profile result...",_result_to_text(result).strip(), flush=True)
        return _result_to_text(result).strip()




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

def run_agent(
    input_text: str,
    user_context: dict = None
) -> str:
    
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

    from .config import load_settings
    from .llm_factory import build_llm
    from .rag_engine import search_kyc_knowledge_base
    from .pbac import classify_prompt

    settings = load_settings()

    llm = build_llm(settings)

    if not user_context:
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

    guardrails = init_guardrails()

    # ==================================================
    # PROMPT GUARDRAIL
    # ==================================================
    prompt_result = classify_prompt(
        input_text,
        user_context["userRole"]
    )

    prompt_result = classify_prompt(
    input_text,
    user_context["userRole"]
    )

    if prompt_result["decision"] == "PERMIT":

        guardrails["prompt"] = {
            "status": "PASS",
            "reason": (
                f"Category="
                f"{prompt_result['category']}"
            )
        }

    else:

        guardrails["prompt"] = {
            "status": "FAIL",
            "reason":
            prompt_result.get(
                "reason",
                "Prompt denied"
            )
        }

    user_question = input_text

    # ==================================================
    # TOOL GUARDRAIL + MCP
    # ==================================================
    mcp_context = ""

    from .pbac import authorize_tool_access

    tool_name = (
        "get_customer_risk_profile"
    )

    tool_decision = authorize_tool_access(
        user_role=user_context["userRole"],
        agent_id=user_context["agentId"],
        tool_name=tool_name
    )

    if tool_decision["decision"] == "PERMIT":

        guardrails["tool"] = {
            "status": "PASS",
            "reason": (
                tool_decision["reason"]
            )
        }

        mcp_context = asyncio.run(
            call_agent_with_mcp(
                customer_name,
                user_context
          
            )
        )

    else:

        guardrails["tool"] = {
            "status": "FAIL",
            "reason": (
                tool_decision["reason"]
            )
        }

        mcp_context = (
            "Tool execution blocked."
        )

    tool_guardrail_status = (
        guardrails["tool"]["status"]
    )

    # ==================================================
    # DATA GUARDRAIL
    # ==================================================
    from .pbac import evaluate_data_guardrail
    print(
        "\n===== SEARCHING KNOWLEDGE BASE =====",
        flush=True
    )

    rag_context = search_kyc_knowledge_base(
        user_question,
        settings=settings,
        user_context=user_context
    )

    guardrails["data"] = (
        evaluate_data_guardrail(rag_context)
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
    User: {user_context.get('userId')}
    Role: {user_context.get('userRole')}
    Department: {user_context.get('department')}
    Agent: {user_context.get('agentId')}
    Case: {user_context.get('caseAssignment')}
    Customer: {customer_name}
    Purpose: {user_context.get('purposeOfUse')}
    """
    # ==================================================
    # OUTPUT GUARDRAIL
    # ==================================================
    from .pbac import evaluate_output_guardrail
    guardrails["output"] = evaluate_output_guardrail(
        user_context["userRole"],
        final_response
    )

    # ==================================================
    # FINAL RESPONSE
    # ==================================================

    return f"""

    ==================================================
    GUARDRAIL STATUS
    ==================================================

    {format_guardrail_status(guardrails["prompt"]["status"])}
    Prompt Guardrail:
    {guardrails["prompt"]["status"]}

    Reason:
    {guardrails["prompt"]["reason"]}

    --------------------------------------------------

    {format_guardrail_status(guardrails["tool"]["status"])}
    Tool Guardrail:
    {guardrails["tool"]["status"]}

    Reason:
    {guardrails["tool"]["reason"]}

    --------------------------------------------------

    {format_guardrail_status(guardrails["data"]["status"])}
    Data Guardrail:
    {guardrails["data"]["status"]}

    Reason:
    {guardrails["data"]["reason"]}

    --------------------------------------------------

    {format_guardrail_status(guardrails["output"]["status"])}
    Output Guardrail:
    {guardrails["output"]["status"]}

    Reason:
    {guardrails["output"]["reason"]}

    ==================================================
    AUTHORIZATION SUMMARY
    ==================================================

    {audit_summary}

    ==================================================
    AGENT RESPONSE
    ==================================================

    {final_response}

    """


if __name__ == "__main__":
    print("✅ Please wait while your agent is doing job for you...", flush=True)
    run_agent("Show me all customer national IDs")
    
