from __future__ import annotations

import os
print("CONFIG FILE LOADED", flush=True)

from dataclasses import dataclass

from dotenv import load_dotenv



@dataclass(frozen=True)
class Settings:
    provider: str
    hf_api_key: str
    hf_base_url: str
    hf_model: str
    google_api_key: str
    google_base_url: str
    google_model: str
    github_token: str
    github_base_url: str
    github_model: str
    ollama_base_url: str
    ollama_model: str
    temperature: float
    timeout_seconds: int
    rag_enabled: bool
    rag_source_file: str
    rag_db_dir: str
    rag_embedding_model: str
    rag_top_k: int
    rag_chunk_size: int
    rag_chunk_overlap: int
    mcp_server_url: str



def load_settings() -> Settings:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "google").strip().lower()
    if provider not in {"huggingface", "google", "github", "ollama"}:
        raise ValueError("LLM_PROVIDER must be one of 'huggingface', 'google', 'github', or 'ollama'.")

    temperature = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    timeout_seconds = int(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    rag_enabled = os.getenv("RAG_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    rag_top_k = int(os.getenv("RAG_TOP_K", "3"))
    rag_chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "700"))
    rag_chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))

    return Settings(
        provider=provider,
        hf_api_key=os.getenv("HF_API_KEY", ""),
        hf_base_url=os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1"),
        hf_model=os.getenv("HF_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct"),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        github_base_url=os.getenv("GITHUB_BASE_URL", "https://models.github.ai/inference"),
        github_model=os.getenv("GITHUB_MODEL", "meta/Llama-4-Scout-17B-16E-Instruct"),
        google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        google_base_url=os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
        google_model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct"),
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        rag_enabled=rag_enabled,
        rag_source_file=os.getenv("RAG_SOURCE_FILE", "data/sensitive.txt"),
        rag_db_dir=os.getenv("RAG_DB_DIR", "data/vector_db_google"),
        rag_embedding_model=os.getenv("RAG_EMBEDDING_MODEL", ""),
        rag_top_k=rag_top_k,
        rag_chunk_size=rag_chunk_size,
        rag_chunk_overlap=rag_chunk_overlap,
        mcp_server_url=os.getenv("MCP_SERVER_URL", ""),
    )
