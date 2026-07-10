from __future__ import annotations

from pathlib import Path
from typing import List

from app.config import Settings

print("RAG_ENGINE LOADED", flush=True)
_embeddings = None


def get_google_embeddings(settings: Settings):
    """
    Lazy Google embedding initialization.
    This avoids importing HuggingFace / transformers / torch.
    """
    global _embeddings

    if _embeddings is None:
        print("⚡ Initializing Google embeddings...", flush=True)

        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for Google embeddings")

        _embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.rag_embedding_model,
            google_api_key=settings.google_api_key,
        )

        print("✅ Google embeddings initialized", flush=True)

    return _embeddings

from pathlib import Path
import json


def load_source_documents(settings):
    """
    Load all TXT files from the data directory
    and attach metadata from metadata.json

    data/
      ├── sensitive.txt
      ├── public.txt
      └── metadata.json
    """

    from langchain_core.documents import Document

    data_dir = Path("data")

    metadata_file = data_dir / "metadata.json"

    if not metadata_file.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {metadata_file}"
        )

    metadata_map = json.loads(
        metadata_file.read_text(encoding="utf-8")
    )

    documents = []

    for txt_file in data_dir.glob("*.txt"):

        text = txt_file.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            print(
                f"Skipping empty file: {txt_file.name}"
            )
            continue

        metadata = metadata_map.get(
            txt_file.name,
            {}
        )

        document = Document(
            page_content=text,
            metadata={
                "source": str(txt_file),
                "fileName": txt_file.name,
                **metadata
            }
        )

        documents.append(document)

    print(
        f"Loaded {len(documents)} document(s)"
    )

    return documents


def load_source_documents_single_file(settings: Settings):
    """
    Load source text as LangChain Document.
    Lazy imports keep startup fast.
    """
    from langchain_core.documents import Document

    source_file = Path(settings.rag_source_file)

    if not source_file.exists():
        raise FileNotFoundError(
            f"RAG source file not found: {source_file}. "
            "Create the file or update RAG_SOURCE_FILE in .env."
        )

    text = source_file.read_text(encoding="utf-8")

    if not text.strip():
        raise ValueError(
            f"RAG source file is empty: {source_file}. "
            "Add content before indexing."
        )

    return [
        Document(
            page_content=text,
            metadata={"source": str(source_file)}
        )
    ]


def rebuild_vector_db_google(settings: Settings) -> None:
    """
    Rebuild Chroma DB using Google embeddings.
    Use this whenever changing embedding provider/model/chunking/source file.
    """
    import shutil

    from langchain_community.vectorstores import Chroma
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    source_file = Path(settings.rag_source_file)
    db_dir = Path(settings.rag_db_dir)

    print("📦 Rebuilding Google vector DB...", flush=True)
    print(f"Source file : {source_file}", flush=True)
    print(f"Vector DB   : {db_dir}", flush=True)
    print(f"Embed model : {settings.rag_embedding_model}", flush=True)

    if db_dir.exists():
        print("🧹 Removing old vector DB directory...", flush=True)
        shutil.rmtree(db_dir)

    db_dir.mkdir(parents=True, exist_ok=True)

    embeddings = get_google_embeddings(settings)
    docs = load_source_documents(settings)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )

    chunks = splitter.split_documents(docs)

    print(f"✂️ Created {len(chunks)} chunk(s)", flush=True)

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(db_dir),
    )

    print("✅ Google vector DB rebuilt successfully", flush=True)


def ensure_vector_db_exists(settings: Settings) -> None:
    """
    Runtime guard. It does NOT rebuild if DB already exists.
    """
    db_dir = Path(settings.rag_db_dir)

    if not db_dir.exists() or not any(db_dir.iterdir()):
        print("⚠️ Vector DB missing/empty. Building now...", flush=True)
        rebuild_vector_db_google(settings)
    else:
        print("✅ Existing vector DB found; skipping rebuild", flush=True)


def query_rag(question: str, settings: Settings, user_context: dict) -> List[str]:
    """
    Retrieve relevant context using Google embeddings + Chroma.
    Returns list[str], not one combined string.
    This avoids the previous '307 character chunks' bug.
    """
    from langchain_community.vectorstores import Chroma

    if not settings.rag_enabled:
        return []

    source_file = Path(settings.rag_source_file)

    if not source_file.exists():
        print(f"⚠️ RAG source file not found: {source_file}", flush=True)
        return []

    ensure_vector_db_exists(settings)

    embeddings = get_google_embeddings(settings)

    vector_db = Chroma(
        persist_directory=str(settings.rag_db_dir),
        embedding_function=embeddings,
    )

    matches = vector_db.similarity_search(
        question,
        k=settings.rag_top_k,
    )

    
    from app.pbac import evaluate_document_access

    authorized_docs = []

    for doc in matches:

        allowed = evaluate_document_access(
            doc.metadata,
            user_context
        )

        if allowed:

            print(
                f"✅ PBAC ALLOW: "
                f"{doc.metadata.get('fileName')}"
            )

            authorized_docs.append(doc)

        else:

            print(
                f"❌ PBAC DENY: "
                f"{doc.metadata.get('fileName')}"
            )

    return authorized_docs


    #chunks = [
    #    doc.page_content.strip()
    #    for doc in matches
    #    if doc.page_content and doc.page_content.strip()
    #]

    #return matches

def build_chroma_where_filter(raw_filter: dict) -> dict:
    """
    Converts a simple PBAC filter dictionary into a valid Chroma where filter.

    Example input:
        {
            "classification": "SENSITIVE",
            "caseId": "CASE-ABC-1001",
            "customerName": None
        }

    Output:
        {
            "$and": [
                {"classification": {"$eq": "SENSITIVE"}},
                {"caseId": {"$eq": "CASE-ABC-1001"}}
            ]
        }
    """

    conditions = []

    for key, value in raw_filter.items():

        # Chroma filter should not include None values
        if value is None:
            continue

        # Avoid empty strings also
        if isinstance(value, str) and not value.strip():
            continue

        conditions.append(
            {
                key: {
                    "$eq": value
                }
            }
        )

    if not conditions:
        return {}

    if len(conditions) == 1:
        return conditions[0]

    return {
        "$and": conditions
    }

# -------------------------------------------------------------------
# Secure RAG tool.
#
# This is the key part of your demo:
#   1. Call PBAC first
#   2. Convert decision into metadata filters
#   3. Retrieve only authorized chunks
#   4. Apply masking obligation if needed
# -------------------------------------------------------------------
def search_kyc_knowledge_base(
    query: str,
    settings: Settings,
    user_context: dict,
    customer_name: str | None = None,
) -> str:
    """
    Securely searches the KYC knowledge base.

    This function demonstrates:
      - Authorization before retrieval
      - Metadata-based filtering
      - Sensitive output masking
      - Audit-style trace
    """

    from pathlib import Path
    from langchain_community.vectorstores import Chroma

    if not settings.rag_enabled:
        return "RAG is disabled."

    source_file = Path(settings.rag_source_file)

    if not source_file.exists():
        print(f"⚠️ RAG source file not found: {source_file}", flush=True)
        return f"RAG source file not found: {source_file}"

    ensure_vector_db_exists(settings)

    embeddings = get_google_embeddings(settings)

    vector_db = Chroma(
        persist_directory=str(settings.rag_db_dir),
        embedding_function=embeddings,
    )

    # ---------------------------------------------------------
    # 1. PBAC authorization before retrieval
    # ---------------------------------------------------------
    from app.pbac import pbac_decision_for_rag
    requested_customer = user_context.get("customerName")
    authz = pbac_decision_for_rag(
        user_context=user_context,
        action="READ_KYC_DOCUMENTS",
        requested_customer=requested_customer,
    )

    if authz.get("decision") == "DENY":
        return (
            "ACCESS DENIED\n"
            f"Reason: {authz.get('reason', 'Not authorized')}"
        )

    # ---------------------------------------------------------
    # 2. Metadata-based retrieval
    # ---------------------------------------------------------
    retrieved_docs = []

    allowed_filters = authz.get("allowedFilters", [])

    if not allowed_filters:
        return (
            "No authorized filters returned by PBAC policy.\n"
            f"PBAC decision: {authz}"
        )

    for allowed_filter in allowed_filters:

        chroma_filter = build_chroma_where_filter(allowed_filter)

        print(f"PBAC raw filter: {allowed_filter}", flush=True)
        print(f"Chroma filter: {chroma_filter}", flush=True)

        if chroma_filter:
            results = vector_db.similarity_search(
                query=query,
                k=3,
                filter=chroma_filter,
            )
        else:
            # If no valid filter was generated, skip defensively.
            print(
                "⚠️ Skipping empty PBAC filter to avoid unrestricted search.",
                flush=True
            )
            continue

        retrieved_docs.extend(results)

    # ---------------------------------------------------------
    # 3. Defensive post-retrieval validation
    # ---------------------------------------------------------
    safe_docs = []

    for doc in retrieved_docs:
        classification = doc.metadata.get("classification")
        case_id = doc.metadata.get("caseId")
        customer = doc.metadata.get("customerName")

        # Normalize classification to avoid case mismatch
        classification_normalized = str(classification or "").upper()

        if classification_normalized == "PUBLIC":
            safe_docs.append(doc)
            continue

        if (
            classification_normalized in ["SENSITIVE", "RESTRICTED"]
            and case_id == user_context.get("caseAssignment")
            and customer == customer_name
        ):
            safe_docs.append(doc)

    if not safe_docs:
        return (
            "No authorized KYC documents were found for this query.\n"
            f"PBAC decision: {authz}"
        )

    # ---------------------------------------------------------
    # 4. Mask sensitive output if required by PBAC obligation
    # ---------------------------------------------------------
    from app.pbac import mask_sensitive_text
    context_blocks = []

    obligations = authz.get("obligations", [])

    for doc in safe_docs:
        content = doc.page_content

        if "maskPII" in obligations:
            content = mask_sensitive_text(content)

        context_blocks.append(
            f"""
--- AUTHORIZED DOCUMENT ---
Document: {doc.metadata.get("documentName", doc.metadata.get("fileName", "Unknown"))}
Classification: {doc.metadata.get("classification")}
Case ID: {doc.metadata.get("caseId")}
Customer: {doc.metadata.get("customerName")}

{content}
"""
        )

    # ---------------------------------------------------------
    # 5. Audit trace
    # ---------------------------------------------------------
    audit_line = f"""
--- AUDIT TRACE ---
User: {user_context.get("userId")}
Role: {user_context.get("userRole")}
Agent: {user_context.get("agentId")}
Action: READ_KYC_DOCUMENTS
Decision: {authz.get("decision")}
Obligations: {authz.get("obligations")}
Reason: {authz.get("reason")}
"""

    return "\n".join(context_blocks) + "\n" + audit_line

# -------------------------------------------------------------------
# Load KYC demo documents with metadata.
# Metadata is critical for PBAC / secure RAG filtering.
# -------------------------------------------------------------------
def load_kyc_documents() -> List[Document]:
    from langchain_core.documents import Document
    docs = []
    with open("data/public.txt", "r", encoding="utf-8") as f:
        docs.append(
            Document(
                page_content=f.read(),
                metadata={
                    "documentName": "public.txt",
                    "classification": "PUBLIC",
                    "caseId": "GENERAL",
                    "customerName": "GENERAL",
                    "containsPII": False,
                },
            )
        )

    with open("data/sensitive.txt", "r", encoding="utf-8") as f:
        docs.append(
            Document(
                page_content=f.read(),
                metadata={
                    "documentName": "sensitive.txt",
                    "classification": "SENSITIVE",
                    "caseId": "CASE-ABC-1001",
                    "customerName": "ABC Corp",
                    "containsPII": True,
                },
            )
        )

    return docs
