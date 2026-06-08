from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import shutil
import subprocess
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from llm_health.core.models import stable_id
from llm_health.core.privacy import assert_safe_payload, validate_profile_alias

SOURCE_VAULT_SCHEMA = "llm-health-source-vault-v1"
SOURCE_AUDIT_SCHEMA = "llm-health-source-audit-v1"
VAULT_DIRNAME = "source-vault"
BLOBS_DIRNAME = "blobs"
AUDITS_DIRNAME = "audits"
MANIFEST_NAME = "manifest.jsonl"
VAULT_META_NAME = "vault.json"

SOURCE_SUFFIX_TYPES = {
    ".pdf": "pdf",
    ".xml": "xml",
    ".cda": "cda",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".csv": "csv",
}

OCR_RISK_RE = re.compile(
    r"ocr|text extraction|ambiguous|corrected|inferred|impossible|drops leading|"
    r"concatenated|unit inferred",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[<>]?-?\d+(?:[.,]\d+)?(?![A-Za-z0-9_])")
SOURCE_TOKEN_RE = re.compile(r"\b[A-Za-z]{2}\d{4}\b|\b\d{2}-\d{8}\b|\b\d{8,10}\b")
YMD_RE = re.compile(r"\b(20\d{2}|19\d{2})[-_/ .](0?[1-9]|1[0-2])[-_/ .](0?[1-9]|[12]\d|3[01])\b")
DMY_RE = re.compile(r"\b(0?[1-9]|[12]\d|3[01])[-_/ .](0?[1-9]|1[0-2])[-_/ .](20\d{2}|19\d{2})\b")
COMPACT_DMY_RE = re.compile(r"(?<!\d)([0-3]\d)([01]\d)((?:19|20)\d{2})(?!\d)")
MONTH_DMY_RE = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\s+([0-3]?\d)(?:st|nd|rd|th)?[,]?\s+((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[a-z0-9]+")
MONTHS = {
    "jan": "01",
    "january": "01",
    "feb": "02",
    "february": "02",
    "mar": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "may": "05",
    "jun": "06",
    "june": "06",
    "jul": "07",
    "july": "07",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "september": "09",
    "oct": "10",
    "october": "10",
    "nov": "11",
    "november": "11",
    "dec": "12",
    "december": "12",
}


@dataclass(frozen=True)
class SourceVaultRecord:
    record_id: str
    source_hash: str
    byte_size: int
    source_type: str
    profile_id: str | None = None
    source_id: str | None = None
    copied: bool = False
    blob_key: str | None = None
    match_status: str = "unmatched"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    tags: list[str] = field(default_factory=lambda: ["SOURCE_VAULT"])

    def __post_init__(self) -> None:
        if self.profile_id is not None:
            object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source_hash": self.source_hash,
            "byte_size": self.byte_size,
            "source_type": self.source_type,
            "profile_id": self.profile_id,
            "source_id": self.source_id,
            "copied": self.copied,
            "blob_key": self.blob_key,
            "match_status": self.match_status,
            "created_at": self.created_at,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceVaultRecord:
        return cls(**data)


@dataclass(frozen=True)
class SourceCatalogSummary:
    scanned_files: int
    cataloged: int
    copied: int
    matched: int
    skipped: int
    vault_path: Path


@dataclass(frozen=True)
class ExtractionSummary:
    method: str
    status: str
    char_count: int = 0
    line_count: int = 0
    number_count: int = 0
    marker_hit_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "status": self.status,
            "char_count": self.char_count,
            "line_count": self.line_count,
            "number_count": self.number_count,
            "marker_hit_count": self.marker_hit_count,
            "error": self.error,
        }


@dataclass(frozen=True)
class SourceAuditResult:
    schema: str
    generated_at: str
    profile_id: str | None
    focus: str
    source_count: int
    row_count: int
    medium_row_count: int
    review_row_count: int
    missing_source_count: int
    extraction_source_count: int
    validation_issue_count: int
    sources: list[dict[str, Any]]
    review_rows: list[dict[str, Any]]
    validation_issues: list[dict[str, Any]]
    audit_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generated_at": self.generated_at,
            "profile_id": self.profile_id,
            "focus": self.focus,
            "source_count": self.source_count,
            "row_count": self.row_count,
            "medium_row_count": self.medium_row_count,
            "review_row_count": self.review_row_count,
            "missing_source_count": self.missing_source_count,
            "extraction_source_count": self.extraction_source_count,
            "validation_issue_count": self.validation_issue_count,
            "sources": self.sources,
            "review_rows": self.review_rows,
            "validation_issues": self.validation_issues,
            "audit_path": str(self.audit_path) if self.audit_path else None,
        }


def vault_root(store_root: Path) -> Path:
    return store_root.expanduser() / VAULT_DIRNAME


def init_source_vault(store_root: Path) -> Path:
    root = vault_root(store_root)
    (root / BLOBS_DIRNAME).mkdir(parents=True, exist_ok=True)
    (root / AUDITS_DIRNAME).mkdir(parents=True, exist_ok=True)
    manifest = root / MANIFEST_NAME
    manifest.touch(exist_ok=True)
    meta = root / VAULT_META_NAME
    if not meta.exists():
        meta.write_text(
            json.dumps(
                {
                    "schema": SOURCE_VAULT_SCHEMA,
                    "privacy": (
                        "raw blobs are hash-addressed and intentionally excluded from normal "
                        "de-identified HUB archives; manifest stores no raw paths or filenames"
                    ),
                    "blob_naming": "sha256 without extension",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return root


def load_records(store_root: Path) -> list[SourceVaultRecord]:
    root = init_source_vault(store_root)
    records: list[SourceVaultRecord] = []
    for line in (root / MANIFEST_NAME).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(SourceVaultRecord.from_dict(json.loads(line)))
    return records


def upsert_record(store_root: Path, record: SourceVaultRecord) -> bool:
    root = init_source_vault(store_root)
    manifest = root / MANIFEST_NAME
    existing = load_records(store_root)
    changed = False
    replaced = False
    output: list[SourceVaultRecord] = []
    for old in existing:
        same_hash = old.source_hash == record.source_hash
        same_source = bool(old.source_id and record.source_id and old.source_id == record.source_id)
        same_unmatched_hash = same_hash and not old.source_id and not record.source_id
        replace_unmatched_with_matched = same_hash and not old.source_id and bool(record.source_id)
        if same_source or same_unmatched_hash or replace_unmatched_with_matched:
            replaced = True
            if old.to_dict() != record.to_dict():
                changed = True
            if not any(item.record_id == record.record_id for item in output):
                output.append(record)
            else:
                changed = True
        else:
            output.append(old)
    if not replaced:
        output.append(record)
        changed = True
    if changed:
        with manifest.open("w", encoding="utf-8") as handle:
            for row in output:
                handle.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
    return changed


def catalog_sources(
    store_root: Path,
    inputs: Iterable[Path],
    *,
    wiki_root: Path | None = None,
    profile_id: str | None = None,
    copy_raw: bool = False,
) -> SourceCatalogSummary:
    root = init_source_vault(store_root)
    profile = validate_profile_alias(profile_id) if profile_id else None
    source_index = _source_alias_index(wiki_root) if wiki_root else []
    scanned = cataloged = copied = skipped = 0
    matched_source_ids: set[str] = set()
    for source_path in _iter_source_files(inputs):
        scanned += 1
        source_type = SOURCE_SUFFIX_TYPES.get(source_path.suffix.lower())
        if source_type is None:
            skipped += 1
            continue
        digest = _sha256(source_path)
        byte_size = source_path.stat().st_size
        source_matches = _source_matches(source_path, source_index, profile)
        if not source_matches:
            source_matches = [
                {
                    "source_id": None,
                    "profile_id": profile,
                    "match_status": "hash_only",
                }
            ]
        blob_key = digest if copy_raw else None
        if copy_raw:
            shutil.copyfile(source_path, root / BLOBS_DIRNAME / digest)
            copied += 1
        for match in source_matches:
            source_id = match.get("source_id")
            matched_profile = match.get("profile_id")
            record_profile = matched_profile or profile
            match_status = str(match.get("match_status") or "hash_only")
            record = SourceVaultRecord(
                record_id=stable_id("srcvault", source_id or "unmatched", digest),
                source_hash=digest,
                byte_size=byte_size,
                source_type=source_type,
                profile_id=record_profile,
                source_id=source_id,
                copied=copy_raw,
                blob_key=blob_key,
                match_status=match_status,
            )
            upsert_record(store_root, record)
            cataloged += 1
            if source_id:
                matched_source_ids.add(str(source_id))
    return SourceCatalogSummary(scanned, cataloged, copied, len(matched_source_ids), skipped, root)


def audit_ingested_sources(
    store_root: Path,
    wiki_root: Path,
    *,
    profile_id: str | None = None,
    focus: Literal["medium", "all", "missing"] = "medium",
    extract: bool = True,
    persist: bool = True,
) -> SourceAuditResult:
    profile = validate_profile_alias(profile_id) if profile_id else None
    rows = _observation_rows(wiki_root)
    if profile:
        rows = [row for row in rows if row.get("profile_id", "").strip().lower() == profile]
    records_by_source = _records_by_source(load_records(store_root))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("source_id") or "[missing_source_id]"].append(row)

    validation_issues = _validation_issues(rows)
    sources: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    medium_rows = [row for row in rows if _confidence(row) != "high"]
    missing_source_count = 0
    extraction_source_count = 0

    for source_id, source_rows in sorted(grouped.items()):
        source_records = records_by_source.get(source_id, [])
        source_required = any(_requires_source_vault(row) for row in source_rows)
        source_present = bool(source_records) or not source_required
        if not source_records and source_required:
            missing_source_count += 1
        medium_count = sum(1 for row in source_rows if _confidence(row) != "high")
        source_audit_medium_count = sum(
            1
            for row in source_rows
            if _confidence(row) != "high" and _requires_source_vault(row)
        )
        ocr_risk_count = sum(1 for row in source_rows if _ocr_risk(row))
        pending_count = sum(1 for row in source_rows if _result_type(row) == "pending")
        source_validation_issues = [
            issue for issue in validation_issues if issue.get("source_id") == source_id
        ]
        include_source = True
        if focus == "missing" and source_present:
            include_source = False
        if focus == "medium" and not (
            source_audit_medium_count or ocr_risk_count or source_validation_issues
        ):
            include_source = False
        extraction = []
        agreement_score: float | None = None
        if include_source and extract and source_records:
            record = _prefer_blob_record(source_records)
            if record and record.copied and record.blob_key and record.source_type == "pdf":
                blob = vault_root(store_root) / BLOBS_DIRNAME / record.blob_key
                extraction, agreement_score = extract_pdf_summaries(blob, source_rows)
                extraction_source_count += 1
        status = _source_status(
            source_present=source_present,
            source_required=source_required,
            medium_count=medium_count,
            ocr_risk_count=ocr_risk_count,
            validation_issue_count=len(source_validation_issues),
            agreement_score=agreement_score,
        )
        if not include_source:
            continue
        sources.append(
            {
                "source_id": source_id,
                "profile_id": _first_nonempty(source_rows, "profile_id"),
                "row_count": len(source_rows),
                "medium_count": medium_count,
                "ocr_risk_count": ocr_risk_count,
                "pending_count": pending_count,
                "source_present": source_present,
                "source_required": source_required,
                "vault_record_count": len(source_records),
                "extraction": [item.to_dict() for item in extraction],
                "agreement_score": agreement_score,
                "validation_issue_count": len(source_validation_issues),
                "status": status,
            }
        )

    for row in rows:
        should_review = _confidence(row) != "high" or _ocr_risk(row)
        if focus == "all":
            should_review = should_review or not records_by_source.get(row.get("source_id", ""))
        if not should_review:
            continue
        review_rows.append(_review_row(row, records_by_source))

    result = SourceAuditResult(
        schema=SOURCE_AUDIT_SCHEMA,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        profile_id=profile,
        focus=focus,
        source_count=len(grouped),
        row_count=len(rows),
        medium_row_count=len(medium_rows),
        review_row_count=len(review_rows),
        missing_source_count=missing_source_count,
        extraction_source_count=extraction_source_count,
        validation_issue_count=len(validation_issues),
        sources=sources,
        review_rows=review_rows,
        validation_issues=validation_issues,
    )
    if persist:
        audit_path = _write_audit(store_root, result)
        result = SourceAuditResult(**{**result.to_dict(), "audit_path": audit_path})
    return result


def latest_audit(store_root: Path) -> dict[str, Any] | None:
    audits = sorted(
        (init_source_vault(store_root) / AUDITS_DIRNAME).glob("source-audit-*.json"),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )
    if not audits:
        return None
    return json.loads(audits[-1].read_text(encoding="utf-8"))


def extract_pdf_summaries(
    blob_path: Path, rows: list[dict[str, str]]
) -> tuple[list[ExtractionSummary], float | None]:
    summaries: list[ExtractionSummary] = []
    texts: dict[str, str] = {}
    for method, status, text, error in _pdf_extraction_texts(str(blob_path)):
        if status != "ok":
            summaries.append(ExtractionSummary(method, status, error=error))
            continue
        texts[method] = text
        summaries.append(_text_summary(method, text, rows))

    agreement = _number_agreement(texts)
    return summaries, agreement


@lru_cache(maxsize=16)
def _pdf_extraction_texts(blob_path: str) -> tuple[tuple[str, str, str, str | None], ...]:
    path = Path(blob_path)
    outputs: list[tuple[str, str, str, str | None]] = []
    for method, args in {
        "pdftotext-layout": ["pdftotext", "-layout", "-enc", "UTF-8"],
        "pdftotext-raw": ["pdftotext", "-raw", "-enc", "UTF-8"],
    }.items():
        if shutil.which("pdftotext") is None:
            outputs.append((method, "unavailable", "", "pdftotext missing"))
            continue
        try:
            proc = subprocess.run(
                [*args, str(path), "-"],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            outputs.append((method, "error", "", type(exc).__name__))
            continue
        if proc.returncode != 0:
            outputs.append((method, "error", "", "extractor returned nonzero"))
            continue
        outputs.append((method, "ok", proc.stdout or "", None))

    # Optional Python readers. These are useful in dev/source-audit extras, but not required for
    # core or Homebrew v2-core installs.
    optional_readers = [
        ("pypdf", _read_with_pypdf),
        ("pdfplumber", _read_with_pdfplumber),
        ("pymupdf", _read_with_pymupdf),
    ]
    for method, reader in optional_readers:
        text, error = reader(path)
        if error:
            outputs.append((method, "unavailable", "", error))
        else:
            outputs.append((method, "ok", text, None))
    return tuple(outputs)


def render_catalog_summary(summary: SourceCatalogSummary) -> str:
    return "\n".join(
        [
            "# Source vault catalog",
            f"scanned: {summary.scanned_files}",
            f"cataloged: {summary.cataloged}",
            f"matched_to_ingested_sources: {summary.matched}",
            f"copied_raw_blobs: {summary.copied}",
            f"skipped: {summary.skipped}",
            "privacy: manifest stores hashes/source_ids only; "
            "raw paths and filenames are not stored",
        ]
    )


def render_records(records: list[SourceVaultRecord]) -> str:
    if not records:
        return "No source-vault records found."
    lines = ["# Source vault records"]
    for record in sorted(records, key=lambda item: (item.profile_id or "", item.source_id or "")):
        source = record.source_id or "[unmatched]"
        profile = record.profile_id or "[unknown]"
        copied = "copied" if record.copied else "catalog-only"
        lines.append(
            f"- {profile} · {source} · {record.source_type} · "
            f"sha256:{record.source_hash[:12]} · {copied} · {record.match_status}"
        )
    return "\n".join(lines)


def render_audit(result: SourceAuditResult, *, detail_limit: int = 20) -> str:
    lines = [
        "# Source audit",
        f"generated: {result.generated_at}",
        f"profile: {result.profile_id or 'all'}",
        f"focus: {result.focus}",
        f"sources: {result.source_count}",
        f"rows: {result.row_count}",
        f"medium rows: {result.medium_row_count}",
        f"review rows: {result.review_row_count}",
        f"sources missing from vault: {result.missing_source_count}",
        f"sources with extraction pass: {result.extraction_source_count}",
        f"validation issues: {result.validation_issue_count}",
    ]
    if result.audit_path:
        lines.append(f"audit_file: {result.audit_path}")
    if result.sources:
        lines.append("\n## Sources needing attention")
        for source in result.sources[:detail_limit]:
            lines.append(
                f"- {source['profile_id']} · {source['source_id']} · {source['status']} · "
                f"rows {source['row_count']} · medium {source['medium_count']} · "
                f"ocr-risk {source['ocr_risk_count']} · present {source['source_present']}"
            )
            if source.get("agreement_score") is not None:
                lines.append(f"  extractor_number_agreement: {source['agreement_score']:.2f}")
            for extraction in source.get("extraction", [])[:4]:
                lines.append(
                    f"  {extraction['method']}: {extraction['status']}, "
                    f"chars={extraction['char_count']}, numbers={extraction['number_count']}, "
                    f"marker_hits={extraction['marker_hit_count']}"
                )
    if result.review_rows:
        lines.append("\n## Rows needing audit")
        for row in result.review_rows[:detail_limit]:
            lines.append(
                f"- {row['profile_id']} · {row['date']} · {row['source_id']} · "
                f"{row['marker']} · {row['value']} · {row['confidence']} · {row['reason']}"
            )
    if result.validation_issues:
        lines.append("\n## Validation issues")
        for issue in result.validation_issues[:detail_limit]:
            lines.append(
                f"- {issue['profile_id']} · {issue['source_id']} · {issue['check']} · "
                f"{issue['message']}"
            )
    return "\n".join(lines)


def _write_audit(store_root: Path, result: SourceAuditResult) -> Path:
    root = init_source_vault(store_root)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    profile = result.profile_id or "all"
    path = root / AUDITS_DIRNAME / f"source-audit-{profile}-{stamp}.json"
    payload = result.to_dict()
    payload["audit_path"] = None
    assert_safe_payload(payload)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _iter_source_files(inputs: Iterable[Path]) -> Iterable[Path]:
    for raw in inputs:
        path = raw.expanduser()
        if path.is_file():
            yield path
        elif path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file() and item.suffix.lower() in SOURCE_SUFFIX_TYPES:
                    yield item


def _source_alias_index(wiki_root: Path | None) -> list[dict[str, Any]]:
    if wiki_root is None:
        return []
    path = wiki_root.expanduser() / "output" / "data" / "lab-reports.csv"
    if not path.exists():
        return []
    index: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            alias = (row.get("source_file_alias") or "").strip()
            if not alias:
                continue
            alias_parts = [part.strip() for part in alias.split(";") if part.strip()]
            basenames = [Path(part).name.lower() for part in alias_parts if Path(part).name]
            basenames = [item for item in basenames if item]
            alias_dates = set(_date_candidates(alias))
            dates = set(alias_dates)
            report_date = (row.get("report_date") or "").strip()
            collection_date = (row.get("collection_date") or "").strip()
            if report_date:
                dates.add(report_date)
            if collection_date:
                dates.add(collection_date)
            source_text = " ".join(
                [
                    row.get("source_id", ""),
                    row.get("source_title", ""),
                    row.get("source_file_alias", ""),
                ]
            )
            index.append(
                {
                    "source_id": row.get("source_id", ""),
                    "profile_id": row.get("profile_id", ""),
                    "report_date": report_date,
                    "collection_date": collection_date,
                    "alias_dates": alias_dates,
                    "basenames": basenames,
                    "suffixes": {
                        Path(name).suffix.lower() for name in basenames if Path(name).suffix
                    },
                    "dates": dates,
                    "tokens": _source_tokens(source_text),
                    "words": _words(" ".join(Path(name).stem for name in basenames)),
                }
            )
    return index


def _source_matches(
    source_path: Path,
    index: list[dict[str, Any]],
    profile: str | None,
) -> list[dict[str, str]]:
    if not index:
        return []
    raw_name = source_path.name.lower()
    raw_suffix = source_path.suffix.lower()
    raw_dates = _date_candidates(" ".join(source_path.parts[-3:]))
    raw_words = _words(source_path.stem)
    path_profile = _profile_from_path(source_path, {row.get("profile_id", "") for row in index})
    profile_hint = profile or path_profile

    # Exact alias basenames are deterministic and should include all report rows that came from
    # the same physical source file (for example a chart export with many dated rows).
    exact = [
        {**row, "match_status": "matched_wiki_alias"}
        for row in index
        if raw_name in row.get("basenames", [])
        and (not profile_hint or row.get("profile_id") == profile_hint)
    ]
    if exact:
        return _dedupe_matches(exact)

    text = _source_probe_text(source_path) if raw_suffix == ".pdf" else ""
    text_dates = _date_candidates(text[:200_000]) if text else set()
    text_tokens = _source_tokens(text) if text else set()

    scored: list[tuple[int, dict[str, Any], str]] = []
    for row in index:
        suffixes = row.get("suffixes") or set()
        if suffixes and raw_suffix not in suffixes:
            continue
        if profile_hint and row.get("profile_id") != profile_hint:
            continue

        score = 0
        reasons: list[str] = []
        row_dates = set(row.get("dates") or set())
        alias_dates = set(row.get("alias_dates") or set())
        row_tokens = set(row.get("tokens") or set())
        row_words = set(row.get("words") or set())
        report_date = row.get("report_date") or ""
        collection_date = row.get("collection_date") or ""

        word_score = _word_overlap(raw_words, row_words)
        if word_score >= 0.75 and len(raw_words) >= 2:
            score += 65
            reasons.append("filename_words")

        if raw_dates:
            if alias_dates & raw_dates:
                score += 80
                reasons.append("filename_alias_date")
            elif report_date and report_date in raw_dates:
                score += 75
                reasons.append("filename_report_date")
            elif row_dates & raw_dates:
                score += 45
                reasons.append("filename_date")

        token_hits = row_tokens & text_tokens
        if token_hits:
            score += 55
            reasons.append("content_token")
            if report_date and report_date in text_dates:
                score += 45
                reasons.append("content_report_date")
            elif collection_date and collection_date in text_dates:
                score += 20
                reasons.append("content_collection_date")
            elif row_dates & text_dates:
                score += 15
                reasons.append("content_date")

        if score >= 60:
            scored.append((score, row, "+".join(reasons)))

    if not scored and profile_hint and raw_dates:
        # Safe fallback for de-identified reports where only the date/profile survived in the
        # source filename. This is intentionally conservative and only returns unique max scores.
        for row in index:
            if row.get("profile_id") != profile_hint:
                continue
            if raw_suffix not in (row.get("suffixes") or {raw_suffix}):
                continue
            row_dates = set(row.get("dates") or set())
            if row_dates & raw_dates:
                scored.append((50, row, "profile_date_fallback"))

    if not scored:
        return []

    best_score = max(score for score, _, _ in scored)
    best = [(score, row, reason) for score, row, reason in scored if score == best_score]
    return _dedupe_matches(
        [
            {
                "source_id": row.get("source_id", ""),
                "profile_id": row.get("profile_id", ""),
                "match_status": f"matched_wiki_{reason}",
            }
            for score, row, reason in best
            if row.get("source_id")
        ]
    )


def _dedupe_matches(matches: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in matches:
        source_id = str(match.get("source_id") or "")
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        out.append(
            {
                "source_id": source_id,
                "profile_id": str(match.get("profile_id") or ""),
                "match_status": str(match.get("match_status") or "matched_wiki"),
            }
        )
    return out


def _profile_from_path(source_path: Path, profiles: set[str]) -> str | None:
    normalized = {profile.strip().lower() for profile in profiles if profile}
    for part in reversed(source_path.parts):
        token = part.strip().lower()
        if token in normalized:
            return token
    return None


def _source_tokens(text: str) -> set[str]:
    tokens = {token.upper() for token in SOURCE_TOKEN_RE.findall(text or "")}
    expanded = set(tokens)
    for token in tokens:
        if "-" in token:
            expanded.add(token.replace("-", ""))
    return expanded


def _words(text: str) -> set[str]:
    stop = {"pdf", "xlsx", "xls", "csv", "source", "report", "copy"}
    return {word for word in WORD_RE.findall((text or "").lower()) if word not in stop}


def _word_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _date_candidates(text: str) -> set[str]:
    dates: set[str] = set()
    if not text:
        return dates
    normalized = text.replace("_", " ")
    for year, month, day in YMD_RE.findall(normalized):
        dates.add(_iso_date(year, month, day))
    for day, month, year in DMY_RE.findall(normalized):
        dates.add(_iso_date(year, month, day))
    for day, month, year in COMPACT_DMY_RE.findall(normalized):
        dates.add(_iso_date(year, month, day))
    for month_name, day, year in MONTH_DMY_RE.findall(normalized):
        month = MONTHS[month_name.lower()]
        dates.add(_iso_date(year, month, day))
    return dates


def _iso_date(year: str, month: str, day: str) -> str:
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _source_probe_text(source_path: Path) -> str:
    if shutil.which("pdftotext") is None:
        return ""
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(source_path), "-"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def _observation_rows(wiki_root: Path) -> list[dict[str, str]]:
    path = wiki_root.expanduser() / "output" / "data" / "lab-observations-long.csv"
    if not path.exists():
        raise FileNotFoundError("missing de-identified canonical lab observations CSV")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records_by_source(records: list[SourceVaultRecord]) -> dict[str, list[SourceVaultRecord]]:
    out: dict[str, list[SourceVaultRecord]] = defaultdict(list)
    for record in records:
        if record.source_id:
            out[record.source_id].append(record)
    return out


def _prefer_blob_record(records: list[SourceVaultRecord]) -> SourceVaultRecord | None:
    for record in records:
        if record.copied and record.blob_key:
            return record
    return records[0] if records else None


def _text_summary(method: str, text: str, rows: list[dict[str, str]]) -> ExtractionSummary:
    markers = {
        (row.get("analyte_en") or row.get("analyte_original") or "").strip().lower()
        for row in rows
    }
    markers = {marker for marker in markers if len(marker) >= 3}
    lower = text.lower()
    marker_hits = sum(1 for marker in markers if marker in lower)
    numbers = NUMBER_RE.findall(text)
    return ExtractionSummary(
        method=method,
        status="ok",
        char_count=len(text),
        line_count=text.count("\n") + 1 if text else 0,
        number_count=len(numbers),
        marker_hit_count=marker_hits,
    )


@contextlib.contextmanager
def _suppress_native_output() -> Iterable[None]:
    """Silence noisy PDF parser stdout/stderr, including C-extension writes."""

    old_stdout = os.dup(1)
    old_stderr = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            yield
    finally:
        os.dup2(old_stdout, 1)
        os.dup2(old_stderr, 2)
        os.close(old_stdout)
        os.close(old_stderr)
        os.close(devnull)


def _read_with_pypdf(path: Path) -> tuple[str, str | None]:
    try:
        with _suppress_native_output():
            from pypdf import PdfReader  # type: ignore
    except ImportError:
        return "", "pypdf not installed"
    try:
        with _suppress_native_output():
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages), None
    except Exception:
        return "", "pypdf extraction failed"


def _read_with_pdfplumber(path: Path) -> tuple[str, str | None]:
    try:
        with _suppress_native_output():
            import pdfplumber  # type: ignore
    except ImportError:
        return "", "pdfplumber not installed"
    try:
        chunks: list[str] = []
        with _suppress_native_output():
            with pdfplumber.open(str(path)) as pdf:
                for page in pdf.pages:
                    chunks.append(page.extract_text() or "")
                    for table in page.extract_tables() or []:
                        chunks.extend("\t".join(cell or "" for cell in row) for row in table)
        return "\n".join(chunks), None
    except Exception:
        return "", "pdfplumber extraction failed"


def _read_with_pymupdf(path: Path) -> tuple[str, str | None]:
    try:
        with _suppress_native_output():
            import fitz  # type: ignore
    except ImportError:
        return "", "pymupdf not installed"
    try:
        with _suppress_native_output():
            doc = fitz.open(str(path))
            return "\n".join(page.get_text("text") for page in doc), None
    except Exception:
        return "", "pymupdf extraction failed"


def _number_agreement(texts: dict[str, str]) -> float | None:
    token_sets = [set(NUMBER_RE.findall(text)) for text in texts.values() if text]
    token_sets = [tokens for tokens in token_sets if tokens]
    if len(token_sets) < 2:
        return None
    scores: list[float] = []
    for i, left in enumerate(token_sets):
        for right in token_sets[i + 1 :]:
            union = left | right
            if union:
                scores.append(len(left & right) / len(union))
    return sum(scores) / len(scores) if scores else None


def _validation_issues(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("profile_id", ""),
            row.get("source_id", ""),
            row.get("observation_date", ""),
        )
        groups[key].append(row)
    for (profile, source_id, date), group in groups.items():
        analytes = {(_marker_key(row)): row for row in group}
        issue = _bilirubin_issue(profile, source_id, date, analytes)
        if issue:
            issues.append(issue)
        issue = _hematocrit_issue(profile, source_id, date, analytes)
        if issue:
            issues.append(issue)
    return issues


def _bilirubin_issue(
    profile: str, source_id: str, date: str, analytes: dict[str, dict[str, str]]
) -> dict[str, Any] | None:
    total = _row_float(analytes.get("total bilirubin"))
    direct = _row_float(analytes.get("direct bilirubin"))
    indirect = _row_float(analytes.get("indirect bilirubin"))
    if total is None or direct is None or indirect is None:
        return None
    diff = abs((direct + indirect) - total)
    if diff <= max(0.15, abs(total) * 0.12):
        return None
    return {
        "profile_id": profile,
        "source_id": source_id,
        "date": date,
        "check": "bilirubin_sum",
        "message": "direct + indirect bilirubin does not reconcile with total",
        "difference": round(diff, 3),
        "tag": "QA_ISSUE",
    }


def _hematocrit_issue(
    profile: str, source_id: str, date: str, analytes: dict[str, dict[str, str]]
) -> dict[str, Any] | None:
    hct = _row_float(analytes.get("hematocrit"))
    rbc = _row_float(analytes.get("rbc"))
    mcv = _row_float(analytes.get("mcv"))
    if hct is None or rbc is None or mcv is None:
        return None
    expected_percent = rbc * mcv / 10.0
    expected = expected_percent / 100.0 if hct <= 2 and expected_percent > 10 else expected_percent
    diff = abs(expected - hct)
    tolerance = max(0.015, abs(hct) * 0.05) if hct <= 2 else max(1.5, abs(hct) * 0.05)
    if diff <= tolerance:
        return None
    return {
        "profile_id": profile,
        "source_id": source_id,
        "date": date,
        "check": "hematocrit_rbc_mcv",
        "message": "hematocrit does not reconcile with RBC × MCV / 10",
        "difference": round(diff, 3),
        "tag": "QA_ISSUE",
    }


def _marker_key(row: dict[str, str]) -> str:
    marker = (row.get("analyte_en") or row.get("analyte_original") or "").strip().lower()
    marker = marker.replace("whole blood", "").strip()
    return marker


def _row_float(row: dict[str, str] | None) -> float | None:
    if not row:
        return None
    raw = (row.get("numeric_value") or row.get("value_raw") or "").strip().replace(",", "")
    if raw.startswith(("<", ">")):
        raw = raw[1:].strip()
    try:
        return float(raw)
    except ValueError:
        return None


def _review_row(
    row: dict[str, str], records_by_source: dict[str, list[SourceVaultRecord]]
) -> dict[str, Any]:
    reasons = []
    if _confidence(row) != "high":
        reasons.append("medium_confidence")
    if _ocr_risk(row):
        reasons.append("ocr_or_inference_note")
    if _requires_source_vault(row) and not records_by_source.get(row.get("source_id", "")):
        reasons.append("source_not_in_vault")
    value = row.get("value_raw") or row.get("numeric_value") or "[blank]"
    unit = row.get("unit_raw") or row.get("ucum_unit") or ""
    return {
        "profile_id": row.get("profile_id", ""),
        "date": row.get("observation_date", ""),
        "source_id": row.get("source_id", ""),
        "marker": row.get("analyte_en") or row.get("analyte_original") or "Unknown",
        "value": f"{value} {unit}".strip(),
        "confidence": _confidence(row),
        "reason": "+".join(reasons) or "review",
        "tag": "QA_ISSUE",
    }


def _source_status(
    *,
    source_present: bool,
    source_required: bool,
    medium_count: int,
    ocr_risk_count: int,
    validation_issue_count: int,
    agreement_score: float | None,
) -> str:
    if not source_required and not validation_issue_count and not ocr_risk_count:
        return "no_source_expected"
    if not source_present:
        return "source_missing"
    if validation_issue_count:
        return "qa_validation_issue"
    if medium_count or ocr_risk_count:
        return "needs_visual_review"
    if agreement_score is not None and agreement_score < 0.70:
        return "extractor_disagreement"
    return "source_available"


def _requires_source_vault(row: dict[str, str]) -> bool:
    source_id = (row.get("source_id") or "").strip().lower()
    alias = (row.get("source_file_alias") or "").strip().lower()
    title = (row.get("source_title") or "").strip().lower()
    if alias.startswith("user-provided/"):
        return False
    if "user-provided" in title:
        return False
    if "_user_" in source_id or source_id.endswith("_user_weight"):
        return False
    return True


def _confidence(row: dict[str, str]) -> str:
    return (row.get("confidence") or "").strip().lower() or "unknown"


def _result_type(row: dict[str, str]) -> str:
    return (row.get("result_type") or "").strip().lower()


def _ocr_risk(row: dict[str, str]) -> bool:
    return bool(OCR_RISK_RE.search(row.get("notes") or ""))


def _first_nonempty(rows: list[dict[str, str]], key: str) -> str:
    for row in rows:
        if row.get(key):
            return row[key]
    return ""
