from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from llm_health import __version__
from llm_health.core.privacy import PrivacyError
from llm_health.stores.jsonl import COLLECTIONS

ARCHIVE_SCHEMA = "llm-health-archive-v1"
DEFAULT_ARCHIVE_DIRNAME = "archives"

ROOT_FILE_ALLOWLIST = frozenset({"agreement.json", "manifest.json", *COLLECTIONS.values()})
ROOT_DIR_ALLOWLIST = frozenset({"deid-staging", "v2-web", "v2-data"})
ALWAYS_SKIP_NAMES = frozenset({DEFAULT_ARCHIVE_DIRNAME, ".DS_Store", "Thumbs.db", "__pycache__"})

# Byte-level guard so binary Parquet/DuckDB artifacts cannot silently carry raw source names.
# CSV is intentionally not blocked because canonical generated manifests mention safe CSV exports.
DANGEROUS_BYTES = (
    b"/Users/",
    b"\\Users\\",
    b"Mobile Documents",
    b".pdf",
    b".PDF",
    b".xml",
    b".XML",
    b".cda",
    b".CDA",
    b".xlsx",
    b".XLSX",
    b".xls",
    b".XLS",
    b"source_file_alias",
    b"provider_alias",
)
_EMAIL_BYTES_RE = re.compile(rb"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)


@dataclass(frozen=True)
class ArchiveMember:
    """One file planned or written into a health archive."""

    path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SkippedArchiveMember:
    """One file intentionally excluded from an archive."""

    path: str
    reason: str


@dataclass(frozen=True)
class ArchiveResult:
    """Result of creating or verifying a HUB archive."""

    archive_path: Path
    archive_id: str
    created_at: str
    member_count: int
    skipped_count: int
    size_bytes: int
    members: list[ArchiveMember] = field(default_factory=list)
    skipped: list[SkippedArchiveMember] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ARCHIVE_SCHEMA,
            "archive_id": self.archive_id,
            "created_at": self.created_at,
            "llm_health_version": __version__,
            "archive_path": str(self.archive_path),
            "member_count": self.member_count,
            "skipped_count": self.skipped_count,
            "size_bytes": self.size_bytes,
            "members": [member.__dict__ for member in self.members],
            "skipped": [item.__dict__ for item in self.skipped],
        }


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(path: Path, root: Path) -> str:
    rel = path.resolve().relative_to(root.resolve())
    rel_text = rel.as_posix()
    if rel_text.startswith("../") or rel_text == ".." or rel.is_absolute():
        raise PrivacyError(f"archive member escapes HUB root: {rel_text}")
    return rel_text


def _candidate_files(
    root: Path,
    *,
    include_ui: bool = True,
    include_v2_data: bool = True,
    include_deid_staging: bool = True,
) -> Iterable[Path]:
    """Yield allowlisted HUB files.

    Unknown root folders are ignored by design so future raw/source-vault folders are not archived
    accidentally. The archive is a de-identified HUB snapshot, not a raw-source backup.
    """

    if not root.exists():
        return
    allowed_dirs = set(ROOT_DIR_ALLOWLIST)
    if not include_ui:
        allowed_dirs.discard("v2-web")
    if not include_v2_data:
        allowed_dirs.discard("v2-data")
    if not include_deid_staging:
        allowed_dirs.discard("deid-staging")

    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.name in ALWAYS_SKIP_NAMES:
            continue
        if child.is_file():
            if child.name in ROOT_FILE_ALLOWLIST:
                yield child
            continue
        if child.is_dir() and child.name in allowed_dirs:
            for nested in sorted(child.rglob("*"), key=lambda item: item.as_posix()):
                if any(part in ALWAYS_SKIP_NAMES for part in nested.relative_to(child).parts):
                    continue
                if nested.is_file():
                    yield nested


def _dangerous_hit(path: Path) -> str | None:
    """Return a privacy reason if a candidate file contains raw-source-looking bytes."""

    # Keep the scan simple and deterministic. All candidate files are local and small enough for a
    # byte scan in the current HUB shape; using bytes catches strings embedded in
    # Parquet/DuckDB too.
    data = path.read_bytes()
    for needle in DANGEROUS_BYTES:
        if needle in data:
            return f"contains blocked raw-source marker {needle.decode('utf-8', 'ignore')!r}"
    if _EMAIL_BYTES_RE.search(data):
        return "contains email-looking text"
    return None


def plan_archive_members(
    root: Path,
    *,
    include_ui: bool = True,
    include_v2_data: bool = True,
    include_deid_staging: bool = True,
    strict: bool = False,
) -> tuple[list[ArchiveMember], list[SkippedArchiveMember]]:
    """Return safe archive members plus skipped candidates."""

    root = root.expanduser().resolve()
    members: list[ArchiveMember] = []
    skipped: list[SkippedArchiveMember] = []
    for path in _candidate_files(
        root,
        include_ui=include_ui,
        include_v2_data=include_v2_data,
        include_deid_staging=include_deid_staging,
    ):
        rel = _safe_relative(path, root)
        reason = _dangerous_hit(path)
        if reason:
            skipped.append(SkippedArchiveMember(rel, reason))
            continue
        stat = path.stat()
        members.append(ArchiveMember(rel, stat.st_size, _sha256_file(path)))

    if strict and skipped:
        details = "; ".join(f"{item.path}: {item.reason}" for item in skipped[:5])
        more = f"; +{len(skipped) - 5} more" if len(skipped) > 5 else ""
        raise PrivacyError(f"archive privacy scan failed: {details}{more}")
    return members, skipped


def archive_manifest_payload(
    *,
    root: Path,
    archive_id: str,
    created_at: str,
    members: list[ArchiveMember],
    skipped: list[SkippedArchiveMember],
    mode: str,
) -> dict[str, object]:
    return {
        "schema": ARCHIVE_SCHEMA,
        "archive_id": archive_id,
        "created_at": created_at,
        "llm_health_version": __version__,
        "mode": mode,
        "privacy": (
            "de-identified HUB snapshot; raw source files, local source paths, provider aliases, "
            "and raw source filenames are excluded"
        ),
        "hub_root_label": "resolved llm-health HUB",
        "member_count": len(members),
        "skipped_count": len(skipped),
        "members": [member.__dict__ for member in members],
        "skipped": [item.__dict__ for item in skipped],
    }


def create_archive(
    root: Path,
    *,
    output_dir: Path | None = None,
    include_ui: bool = True,
    include_v2_data: bool = True,
    include_deid_staging: bool = True,
    strict: bool = False,
    mode: Literal["snapshot"] = "snapshot",
) -> ArchiveResult:
    """Create a compressed, privacy-scanned archive of the resolved health HUB."""

    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"HUB does not exist: {root}")

    members, skipped = plan_archive_members(
        root,
        include_ui=include_ui,
        include_v2_data=include_v2_data,
        include_deid_staging=include_deid_staging,
        strict=strict,
    )
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    archive_id = f"llm-health-{_utc_stamp()}"
    destination_dir = (output_dir.expanduser() if output_dir else root / DEFAULT_ARCHIVE_DIRNAME)
    destination_dir.mkdir(parents=True, exist_ok=True)
    archive_path = destination_dir / f"{archive_id}.tar.gz"
    manifest = archive_manifest_payload(
        root=root,
        archive_id=archive_id,
        created_at=created_at,
        members=members,
        skipped=skipped,
        mode=mode,
    )

    with tarfile.open(archive_path, "w:gz") as tar:
        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        info = tarfile.TarInfo("archive-manifest.json")
        info.size = len(manifest_bytes)
        info.mtime = int(datetime.now(UTC).timestamp())
        tar.addfile(info, io.BytesIO(manifest_bytes))
        for member in members:
            tar.add(root / member.path, arcname=member.path, recursive=False)

    return ArchiveResult(
        archive_path=archive_path,
        archive_id=archive_id,
        created_at=created_at,
        member_count=len(members),
        skipped_count=len(skipped),
        size_bytes=archive_path.stat().st_size,
        members=members,
        skipped=skipped,
    )


def list_archives(root: Path, *, output_dir: Path | None = None) -> list[Path]:
    directory = (
        output_dir.expanduser() if output_dir else root.expanduser() / DEFAULT_ARCHIVE_DIRNAME
    )
    if not directory.exists():
        return []
    return sorted(directory.glob("llm-health-*.tar.gz"), key=lambda item: item.name)


def verify_archive(path: Path) -> tuple[dict[str, object], list[str]]:
    """Verify member checksums in an existing archive."""

    path = path.expanduser()
    failures: list[str] = []
    with tarfile.open(path, "r:gz") as tar:
        try:
            manifest_member = tar.getmember("archive-manifest.json")
        except KeyError as exc:
            raise ValueError("archive is missing archive-manifest.json") from exc
        handle = tar.extractfile(manifest_member)
        if handle is None:
            raise ValueError("archive-manifest.json is not readable")
        manifest = json.loads(handle.read().decode("utf-8"))
        for member in manifest.get("members", []):
            rel = member["path"]
            expected = member["sha256"]
            try:
                archived = tar.extractfile(rel)
            except KeyError:
                failures.append(f"missing member: {rel}")
                continue
            if archived is None:
                failures.append(f"unreadable member: {rel}")
                continue
            digest = hashlib.sha256(archived.read()).hexdigest()
            if digest != expected:
                failures.append(f"checksum mismatch: {rel}")
    return manifest, failures
