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


def load_source_documents(settings: Settings):
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


def query_rag(question: str, settings: Settings) -> List[str]:
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

    chunks = [
        doc.page_content.strip()
        for doc in matches
        if doc.page_content and doc.page_content.strip()
    ]

    return chunks