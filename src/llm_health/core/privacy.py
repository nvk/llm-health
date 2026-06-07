from __future__ import annotations

import re
from dataclasses import fields, is_dataclass
from pathlib import PurePath
from typing import Any

DEFAULT_PROFILE_ALIASES = {"rod", "cara"}
ALLOWED_PROFILE_ALIASES = DEFAULT_PROFILE_ALIASES
_PROFILE_ALIAS_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
_RESERVED_PROFILE_ALIASES = {
    "father",
    "mother",
    "parent",
    "child",
    "son",
    "daughter",
    "kid",
    "patient",
    "profile",
    "user",
}

_PATH_PATTERNS = [
    re.compile(r"/Users/[^\s]+", re.IGNORECASE),
    re.compile(r"\\Users\\[^\s]+", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\[^\s]+"),
    re.compile(r"Mobile Documents", re.IGNORECASE),
]
_RAW_FILE_PATTERN = re.compile(r"\b[^\s/\\]+\.(pdf|xml|cda|xlsx?|csv)\b", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


class PrivacyError(ValueError):
    """Raised when generated/stored health content appears to contain private identifiers."""


def validate_profile_alias(profile_id: str) -> str:
    normalized = profile_id.strip().lower()
    if normalized in _RESERVED_PROFILE_ALIASES or not _PROFILE_ALIAS_PATTERN.fullmatch(
        normalized
    ):
        raise PrivacyError(
            "profile_id must be an alias-like token: lower-case letter first, "
            "2-32 chars, letters/digits/_/-, and not a family role"
        )
    return normalized


def assert_safe_text(value: str, *, field_name: str = "text") -> None:
    """Block source paths, raw filenames, and obvious identifiers in durable text."""

    for pattern in _PATH_PATTERNS:
        if pattern.search(value):
            raise PrivacyError(f"{field_name} appears to contain a private source path")
    if _RAW_FILE_PATTERN.search(value):
        raise PrivacyError(f"{field_name} appears to contain a raw source filename")
    if _EMAIL_PATTERN.search(value):
        raise PrivacyError(f"{field_name} appears to contain an email address")


def assert_safe_payload(payload: Any, *, field_name: str = "payload") -> None:
    """Recursively check dataclasses, dicts, lists, and strings for unsafe text."""

    if payload is None or isinstance(payload, (int, float, bool)):
        return
    if isinstance(payload, PurePath):
        raise PrivacyError(f"{field_name} must not contain filesystem paths")
    if isinstance(payload, str):
        assert_safe_text(payload, field_name=field_name)
        return
    if is_dataclass(payload):
        for f in fields(payload):
            assert_safe_payload(getattr(payload, f.name), field_name=f"{field_name}.{f.name}")
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert_safe_payload(str(key), field_name=f"{field_name}.key")
            assert_safe_payload(value, field_name=f"{field_name}.{key}")
        return
    if isinstance(payload, (list, tuple, set)):
        for index, item in enumerate(payload):
            assert_safe_payload(item, field_name=f"{field_name}[{index}]")
