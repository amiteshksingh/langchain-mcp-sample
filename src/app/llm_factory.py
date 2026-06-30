from __future__ import annotations

from .config import Settings
print("LLM_FACTORY LOADED", flush=True)

def build_llm(settings: Settings):
    provider = settings.provider.lower()

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=google")

        return ChatGoogleGenerativeAI(
            model=settings.google_model,
            google_api_key=settings.google_api_key,
            temperature=settings.temperature,
        )

    if provider == "github":
        from langchain_openai import ChatOpenAI

        if not settings.github_token:
            raise ValueError("GITHUB_TOKEN is required when LLM_PROVIDER=github")

        return ChatOpenAI(
            model=settings.github_model,
            api_key=settings.github_token,
            base_url=settings.github_base_url,
            temperature=settings.temperature,
            timeout=settings.timeout_seconds,
            max_retries=2,
        )

    if provider == "huggingface":
        from langchain_openai import ChatOpenAI

        if not settings.hf_api_key:
            raise ValueError("HF_API_KEY is required when LLM_PROVIDER=huggingface")

        return ChatOpenAI(
            model=settings.hf_model,
            api_key=settings.hf_api_key,
            base_url=settings.hf_base_url,
            temperature=settings.temperature,
            timeout=settings.timeout_seconds,
            max_retries=2,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.temperature,
            num_predict=300,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")