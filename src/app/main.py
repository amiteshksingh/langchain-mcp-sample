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





def run_demo(input_text: str = "Artificial Intelligence") -> str:
    
    print("🚀 Starting demo...", flush=True)
    from langchain_core.prompts import ChatPromptTemplate
    from app.config import load_settings
    from app.llm_factory import build_llm
    from app.rag_engine import query_rag
    from app.rag_engine import search_kyc_knowledge_base

    settings = load_settings()

    print(
        f"✅ Settings loaded: provider={settings.provider}, "
        f"rag_db={settings.rag_db_dir}, "
        f"embedding={settings.rag_embedding_model}",
        flush=True,
    )

    llm = build_llm(settings)
    #Setting user context for RAG query
    
    #user_context = {
    #    "userId": "amitesh",
    #    "department": "IAM",
    #    "country": "IN",
    #    "clearance": "public"
    #}

    
    # -------------------------------------------------------------------
    # Demo user context.
    #
    # Change user_role to "COMPLIANCE_OFFICER" to show unmasked access.
    # Change user_role to "BRANCH_USER" to show denials.
    # -------------------------------------------------------------------
    user_context = {
        "userId": "sarah.analyst@bank.com",
        "userRole": "KYC_ANALYST",
        "department": "Financial Crime Compliance",
        "caseAssignment": "CASE-ABC-1001",
        "purposeOfUse": "KYC_REVIEW",
        "agentId": "kyc-review-agent",
        "userName": "ABC Corp"
    }


    question = input_text
    #question = """
    #Summarize customer ABC Corp KYC profile.

    #1. Use available tools to retrieve customer risk profile.
    #2. Search the knowledge base for KYC information.
    #3. Apply authorization controls.
    #4. Mask sensitive information where required.
    #5. Provide a concise analyst summary.
    #"""
    customer_name = user_context["userName"]
    # If you want MCP, enable this:
    #question = asyncio.run(_build_llm_input_from_mcp(input_text))
    question = asyncio.run(call_agent_with_mcp(customer_name))

    print(f"Question: {question}", flush=True)
    print("\n===== USER CONTEXT =====", flush=True)
    print(user_context)
    #context_chunks = query_rag(question, settings, user_context)
    context_chunks = search_kyc_knowledge_base(question, settings=settings, user_context=user_context)

    if context_chunks:
        print(f"RAG retrieved {len(context_chunks)} document(s).", flush=True)
        print(f"Document Content:\n{context_chunks}", flush=True)
        #for index, doc in enumerate(context_chunks, start=1):
        #    print(f"\n--- Document #{index} ---", flush=True)
        #    print(f"Document Content:\n{doc.page_content}", flush=True)
        #    print(f"Document Metadata:\n{doc.metadata}", flush=True)
        #    print("-" * 20, flush=True)
    else:
        print("RAG retrieved 0 documents.", flush=True)

    #context_text = "\n\n".join(
    #    f"Context {idx + 1}:\n{doc.page_content}"
    #    for idx, doc in enumerate(context_chunks)
    #)

    context_text = context_chunks

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""
                You are a secure KYC analyst assistant.

                You must follow these rules:

                1. Use MCP tools when customer risk profile or sensitive customer attributes are requested.
                2. Use search_kyc_knowledge_base when KYC documents, CDD guidance, or ABC Corp profile must be searched.
                3. Never claim that PlainID PDP retrieves data.
                4. Authorization must happen before data retrieval.
                5. The retrieval layer enforces filters and obligations.
                6. The LLM must only summarize data returned by authorized tools.
                7. If masking is applied, do not attempt to reconstruct masked values.
                8. Include a short "Authorization Summary" in final answer.

                Current user context:
                - userId: {user_context["userId"]}
                - userRole: {user_context["userRole"]}
                - department: {user_context["department"]}
                - caseAssignment: {user_context["caseAssignment"]}
                - purposeOfUse: {user_context["purposeOfUse"]}
                - agentId: {user_context["agentId"]}
                """
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
    print("✅ Please wait while your agent is doing job for you...", flush=True)
    #run_demo("What is Customer Due Diligence?")
    run_demo("Show me all customer national IDs")
