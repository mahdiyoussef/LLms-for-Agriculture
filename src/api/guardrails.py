"""Input and output guardrails for untrusted GenAI requests."""

from __future__ import annotations

import re

from fastapi import HTTPException, status


_INJECTION_PATTERNS = (
    r"\b(ignore|disregard|override)\b.{0,80}\b(instructions|system prompt|policy)\b",
    r"\b(reveal|print|show|exfiltrate)\b.{0,80}\b(system prompt|secret|token|password)\b",
    r"\b(tool|function)\s*call\b.{0,50}\bwithout approval\b",
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_ -]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)


def validate_question(question: str, max_length: int = 4000) -> str:
    """Reject empty, oversized, or obvious prompt-injection requests."""
    normalized = " ".join(question.split())
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Question is required")
    if len(normalized) > max_length:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Question is too long")
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in _INJECTION_PATTERNS):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsafe instruction pattern detected")
    return normalized


def redact_secrets(text: str) -> str:
    """Remove common credential-shaped values before returning model output."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text
