from __future__ import annotations

from pathlib import Path
import shutil

from .config import Settings
# THIS IS FOR HUGGINGFACE EMBEDDINGS ONLY. Google embeddings are lazy-loaded in rag_engine.py

# ✅ Load documents (lightweight, safe)
def _load_source_documents(source_file: Path):
    # ✅ Lazy import
    from langchain_core.documents import Document

    if not source_file.exists():
        raise FileNotFoundError(
            f"RAG source file not found: {source_file}. "
            "Create the file or set RAG_SOURCE_FILE in .env."
        )

    text = source_file.read_text(encoding="utf-8")

    if not text.strip():
        raise ValueError(
            f"RAG source file is empty: {source_file}. "
            "Add text content to index."
        )

    return [Document(page_content=text, metadata={"source": str(source_file)})]


# ✅ Lazy embedding loader (CRITICAL FIX)
def _get_embeddings(settings: Settings):
    print("⚡ Initializing embeddings...", flush=True)

    # ✅ Import happens ONLY when this function is called
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=settings.rag_embedding_model,
        cache_folder=settings.rag_db_dir + "/hf_cache"
    )


# ✅ Vector DB builder (heavy — controlled)
def ensure_vector_db(settings: Settings) -> None:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma

    source_file = Path(settings.rag_source_file)
    db_dir = Path(settings.rag_db_dir)

    db_dir.mkdir(parents=True, exist_ok=True)

    embeddings = _get_embeddings(settings)
    docs = _load_source_documents(source_file)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )

    chunks = splitter.split_documents(docs)

    # ✅ IMPORTANT FIX: avoid rebuilding every time
    if not any(db_dir.iterdir()):
        print("📦 Building vector DB...", flush=True)

        Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=str(db_dir),
        )

        print("✅ Vector DB created", flush=True)
    else:
        print("✅ Vector DB already exists, skipping rebuild", flush=True)


# ✅ Retrieval (lazy + fast after init)
def retrieve_relevant_context(query: str, settings: Settings):
    from langchain_community.vectorstores import Chroma

    if not settings.rag_enabled:
        return []

    source_file = Path(settings.rag_source_file)
    db_dir = Path(settings.rag_db_dir)

    if not source_file.exists():
        return []

    # ✅ Build DB only if needed
    if not db_dir.exists() or not any(db_dir.iterdir()):
        ensure_vector_db(settings)

    embeddings = _get_embeddings(settings)

    vector_db = Chroma(
        persist_directory=str(db_dir),
        embedding_function=embeddings,
    )

    matches = vector_db.similarity_search(query, k=settings.rag_top_k)

    # ✅ Return list (avoid your earlier bug)
    return [doc.page_content.strip() for doc in matches if doc.page_content.strip()]