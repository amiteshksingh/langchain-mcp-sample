from __future__ import annotations

from .config import load_settings
from .rag import ensure_vector_db


def main() -> None:
    settings = load_settings()
    ensure_vector_db(settings)
    print("RAG index created successfully.")
    print(f"Source file: {settings.rag_source_file}")
    print(f"Vector DB dir: {settings.rag_db_dir}")


if __name__ == "__main__":
    main()
