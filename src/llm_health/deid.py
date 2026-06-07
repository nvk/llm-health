from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from llm_health.core.privacy import assert_safe_text

DeidMethod = Literal["replace", "mask", "hash"]

_BACKEND = "local-regex-v0"

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "PATH",
        re.compile(r"(?:/Users/[^\s,;]+|\\Users\\[^\s,;]+|[A-Za-z]:\\[^\s,;]+)", re.IGNORECASE),
    ),
    ("PATH", re.compile(r"\bMobile Documents\b", re.IGNORECASE)),
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    (
        "PHONE",
        re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\d)"),
    ),
    ("ID", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("DATE", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    ("DATE", re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")),
    (
        "FILE",
        re.compile(r"\b[^\s/\\]+\.(?:pdf|xml|cda|xlsx?|csv)\b", re.IGNORECASE),
    ),
)

_PERSON_CONTEXT = re.compile(
    r"\b(?:Patient|Name|Doctor|Provider|Clinician|Dr)\s*:\s*"
    r"(?P<person>[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){1,3})\b"
)


@dataclass(frozen=True)
class DeidEntity:
    kind: str
    start: int
    end: int
    value_hash: str
    replacement: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DeidResult:
    text: str
    entities: tuple[DeidEntity, ...]
    backend: str = _BACKEND

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    def to_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "entity_count": self.entity_count,
            "entities": [entity.to_dict() for entity in self.entities],
            "text": self.text,
        }


def _value_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def _replacement(kind: str, value: str, method: DeidMethod) -> str:
    kind = kind.upper()
    if method == "mask":
        return f"[{kind}]"
    digest = _value_hash(value)
    if method in {"replace", "hash"}:
        return f"[{kind}_{digest}]"
    raise ValueError(f"unknown de-id method: {method}")


def _add_entity(
    entities: list[DeidEntity], kind: str, start: int, end: int, text: str, method: DeidMethod
) -> None:
    if start >= end:
        return
    value = text[start:end]
    entities.append(
        DeidEntity(
            kind=kind.upper(),
            start=start,
            end=end,
            value_hash=_value_hash(value),
            replacement=_replacement(kind, value, method),
        )
    )


def extract_entities(text: str, *, method: DeidMethod = "replace") -> tuple[DeidEntity, ...]:
    """Find common identifiers without returning raw matched values."""

    entities: list[DeidEntity] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            _add_entity(entities, kind, match.start(), match.end(), text, method)
    for match in _PERSON_CONTEXT.finditer(text):
        _add_entity(entities, "PERSON", match.start("person"), match.end("person"), text, method)

    # Prefer longer/earlier matches and skip overlaps. This keeps /Users/.../file.pdf as one PATH,
    # not a PATH plus nested FILE.
    entities.sort(key=lambda item: (item.start, -(item.end - item.start)))
    accepted: list[DeidEntity] = []
    occupied: list[tuple[int, int]] = []
    for entity in entities:
        if any(entity.start < end and entity.end > start for start, end in occupied):
            continue
        accepted.append(entity)
        occupied.append((entity.start, entity.end))
    return tuple(sorted(accepted, key=lambda item: item.start))


def deidentify_text(text: str, *, method: DeidMethod = "replace") -> DeidResult:
    """Return redacted text and safe entity metadata.

    Raw input is intentionally not passed through the durable-artifact privacy guard until after
    replacements are complete, because this adapter's job is to clean raw text before staging.
    """

    entities = extract_entities(text, method=method)
    redacted = text
    for entity in sorted(entities, key=lambda item: item.start, reverse=True):
        redacted = redacted[: entity.start] + entity.replacement + redacted[entity.end :]
    assert_safe_text(redacted, field_name="deidentified_text")
    return DeidResult(text=redacted, entities=entities)


def load_text_input(value: str) -> str:
    """Read a text file if it exists; otherwise treat the argument as literal text."""

    path = Path(value).expanduser()
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8", errors="replace")
    return value


def stage_deidentified_text(
    text: str, root: Path, *, method: DeidMethod = "replace"
) -> tuple[Path, Path, DeidResult]:
    """Write redacted text plus safe metadata into a staging directory.

    The original source path/value is never stored. The filename is based on the redacted payload,
    not the raw source.
    """

    result = deidentify_text(text, method=method)
    digest = hashlib.sha256(result.text.encode("utf-8")).hexdigest()[:16]
    staging = root / "deid-staging"
    staging.mkdir(parents=True, exist_ok=True)
    text_path = staging / f"deid_{digest}.txt"
    meta_path = staging / f"deid_{digest}.json"
    text_path.write_text(result.text.rstrip() + "\n", encoding="utf-8")
    metadata = {
        "backend": result.backend,
        "entity_count": result.entity_count,
        "entities": [entity.to_dict() for entity in result.entities],
        "method": method,
        "staging": "redacted-only",
    }
    assert_safe_text(json.dumps(metadata, sort_keys=True), field_name="deid_metadata")
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return text_path, meta_path, result


def render_extract(result: DeidResult) -> str:
    lines = [f"backend: {result.backend}", f"entities: {result.entity_count}"]
    for entity in result.entities:
        lines.append(
            f"- {entity.kind} {entity.start}-{entity.end} replacement={entity.replacement} "
            f"hash={entity.value_hash}"
        )
    return "\n".join(lines)
