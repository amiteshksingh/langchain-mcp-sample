import os

from app.config import load_settings



def test_default_provider(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "huggingface")
    settings = load_settings()
    assert settings.provider == "huggingface"


def test_github_provider(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "github")
    settings = load_settings()
    assert settings.provider == "github"


def test_provider_validation(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "bad-provider")
    try:
        load_settings()
        assert False, "Expected ValueError"
    except ValueError:
        assert True
