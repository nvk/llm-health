from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from llm_health.core.privacy import validate_profile_alias

from .models import GenomicSource, VariantCall

NO_CALLS = {"", "--", "NN", "00", "NA", "N/A", "NOTDETERMINED"}


@dataclass(frozen=True)
class GenotypeImportResult:
    source: GenomicSource
    variants: list[VariantCall]
    comments: list[str]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect_source_kind(comments: list[str], requested: str) -> str:
    if requested != "auto":
        return requested
    joined = "\n".join(comments).lower()
    if "23andme" in joined or "23and me" in joined:
        return "23andme"
    if "ancestry" in joined:
        return "ancestrydna"
    return "raw_genotype"


def _detect_build(comments: list[str]) -> str:
    joined = "\n".join(comments).lower()
    if "grch38" in joined or "build 38" in joined:
        return "GRCh38"
    if "grch37" in joined or "build 37" in joined or "human genome 19" in joined:
        return "GRCh37"
    return "unknown"


def _split_row(line: str) -> list[str]:
    if "\t" in line:
        return [part.strip() for part in line.split("\t")]
    if "," in line:
        return [part.strip() for part in line.split(",")]
    return line.split()


def _call_status(genotype: str) -> str:
    if genotype.strip().upper().replace(" ", "") in NO_CALLS:
        return "no_call"
    return "called"


def _alleles(genotype: str) -> list[str]:
    cleaned = genotype.strip().upper().replace(" ", "")
    if cleaned in NO_CALLS:
        return []
    if "/" in cleaned or "|" in cleaned:
        sep = "/" if "/" in cleaned else "|"
        return [part for part in cleaned.split(sep) if part]
    return list(cleaned)


def _parse_rows(lines) -> tuple[list[str], list[tuple[str, str, int | None, str, list[str]]], int]:
    comments: list[str] = []
    rows: list[tuple[str, str, int | None, str, list[str]]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            comments.append(line[:300])
            continue
        parts = _split_row(line)
        if len(parts) < 4:
            continue
        rsid, chrom, position_raw, genotype = parts[:4]
        if rsid.lower() in {"rsid", "snp", "marker"}:
            continue
        if not rsid.lower().startswith("rs"):
            continue
        try:
            pos = int(position_raw)
        except ValueError:
            pos = None
        if rsid.lower() in seen:
            duplicate_count += 1
        seen.add(rsid.lower())
        flags: list[str] = []
        if len(genotype.strip()) > 2:
            flags.append("complex_or_indel_like_call")
        rows.append((rsid, chrom, pos, genotype, flags))
    return comments, rows, duplicate_count


def _build_result(
    *,
    profile: str,
    file_sha256: str,
    rows: list[tuple[str, str, int | None, str, list[str]]],
    comments: list[str],
    duplicate_count: int,
    source_kind: str,
    clinical_grade: bool,
) -> GenotypeImportResult:
    if not rows:
        raise ValueError("no rsID genotype rows found")

    called_count = sum(1 for _, _, _, genotype, _ in rows if _call_status(genotype) == "called")
    no_call_count = len(rows) - called_count
    source = GenomicSource(
        profile_id=profile,
        source_kind=_detect_source_kind(comments, source_kind),
        file_sha256=file_sha256,
        marker_count=len(rows),
        called_count=called_count,
        no_call_count=no_call_count,
        duplicate_marker_count=duplicate_count,
        genome_build=_detect_build(comments),
        clinical_grade=clinical_grade,
    )
    variants = [
        VariantCall(
            profile_id=profile,
            source_id=source.source_id or "",
            rsid=rsid,
            chrom=chrom,
            pos=pos,
            reported_genotype=genotype,
            normalized_alleles=_alleles(genotype),
            genome_build=source.genome_build,
            call_status=_call_status(genotype),
            quality_flags=flags,
        )
        for rsid, chrom, pos, genotype, flags in rows
    ]
    return GenotypeImportResult(source=source, variants=variants, comments=comments)


def parse_raw_genotype_text(
    content: str | bytes,
    *,
    profile_id: str,
    source_kind: str = "auto",
    clinical_grade: bool = False,
) -> GenotypeImportResult:
    """Parse 23andMe/Ancestry-style raw genotype text without receiving a file path."""

    profile = validate_profile_alias(profile_id)
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    text = data.decode("utf-8", errors="replace")
    comments, rows, duplicate_count = _parse_rows(text.splitlines())
    return _build_result(
        profile=profile,
        file_sha256=_sha256_bytes(data),
        rows=rows,
        comments=comments,
        duplicate_count=duplicate_count,
        source_kind=source_kind,
        clinical_grade=clinical_grade,
    )


def parse_raw_genotype_file(
    path: str | Path,
    *,
    profile_id: str,
    source_kind: str = "auto",
    clinical_grade: bool = False,
) -> GenotypeImportResult:
    """Parse a small 23andMe/Ancestry-style raw genotype TSV without storing file paths."""

    profile = validate_profile_alias(profile_id)
    input_path = Path(path)
    if not input_path.exists() or not input_path.is_file():
        raise FileNotFoundError("genotype input was not found or is not a regular file")

    with input_path.open("r", encoding="utf-8", errors="replace") as handle:
        comments, rows, duplicate_count = _parse_rows(handle)
    return _build_result(
        profile=profile,
        file_sha256=_sha256_file(input_path),
        rows=rows,
        comments=comments,
        duplicate_count=duplicate_count,
        source_kind=source_kind,
        clinical_grade=clinical_grade,
    )
