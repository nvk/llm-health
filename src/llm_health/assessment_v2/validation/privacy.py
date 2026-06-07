"""Simple privacy guard patterns for generated text artifacts."""

from __future__ import annotations

import re

FORBIDDEN_PATTERNS = [
    re.compile(r"\bHealth Number\b", re.IGNORECASE),
    re.compile(r"\bDate of Birth\b", re.IGNORECASE),
    re.compile(r"\bDOB\b", re.IGNORECASE),
    re.compile(r"/Users/[^\s)]+"),
    re.compile(r"sourceName", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
]


def privacy_hits(text: str) -> list[str]:
    """Return pattern labels that matched generated text."""

    return [pattern.pattern for pattern in FORBIDDEN_PATTERNS if pattern.search(text)]
