"""Stable reference fingerprints: never serialize raw workflow parameter values."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


def fingerprint(kind: str, value: str) -> str:
    digest = hashlib.sha256((kind + "\0" + value).encode("utf-8", errors="surrogatepass")).hexdigest()
    return f"{kind}:sha256:{digest}"


def is_expression(value: Any) -> bool:
    return isinstance(value, str) and (value.startswith("=") or "{{" in value or "${" in value)


def static_id(value: Any) -> str | None:
    """Normalize legacy numeric IDs; expressions and arbitrary objects stay unknown."""
    if type(value) is int and value >= 0:
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) and not is_expression(value):
        return value
    return None


KNOWN_CONNECTION_TYPES = {"main", "ai_agent", "ai_chain", "ai_document", "ai_embedding", "ai_languageModel",
                          "ai_memory", "ai_outputParser", "ai_retriever", "ai_textSplitter", "ai_tool", "ai_vectorStore"}


def connection_type(value: str) -> str:
    return value if value in KNOWN_CONNECTION_TYPES else fingerprint("connection-type", value)


def display_text(value) -> str:
    """Render invisible controls and lone surrogates visibly in human reports."""
    return "".join(f"\\u{ord(char):04x}" if unicodedata.category(char) in ("Cc", "Cf", "Cs") else char
                   for char in str(value))
