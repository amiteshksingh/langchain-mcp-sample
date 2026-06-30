from __future__ import annotations

from datetime import datetime, timezone


def add_numbers(a: float, b: float) -> float:
    return a + b


def get_utc_time() -> str:
    return datetime.now(timezone.utc).isoformat()


def explain_text(text: str) -> str:
    return f"Explain {text}"
