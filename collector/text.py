"""Text helpers for bounded Prometheus info labels."""

from __future__ import annotations


def label_text(value: str, max_length: int = 300) -> str:
    text = " ".join(value.split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"
