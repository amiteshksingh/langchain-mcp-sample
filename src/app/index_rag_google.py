from __future__ import annotations

from app.config import load_settings
from app.rag_engine import rebuild_vector_db_google


def main() -> None:
    print("📦 Starting Google RAG index rebuild...", flush=True)

    settings = load_settings()

    rebuild_vector_db_google(settings)

    print("✅ RAG index created successfully.", flush=True)
    print(f"Source file : {settings.rag_source_file}", flush=True)
    print(f"Vector DB   : {settings.rag_db_dir}", flush=True)
    print(f"Embedding   : {settings.rag_embedding_model}", flush=True)


if __name__ == "__main__":
    main()