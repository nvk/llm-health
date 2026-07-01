"""Export the Health Assessment v2 static review dashboard."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

from llm_health.assessment_v2.export.old_web import (
    _float_or_none,
    _profile_context,
    _read_csv_dicts,
)
from llm_health.assessment_v2.normalization import normalize_observation_rows
from llm_health.config import resolve_store_path
from llm_health.core.models import EnrolledProfile
from llm_health.core.privacy import PrivacyError, assert_safe_payload, validate_profile_alias
from llm_health.genomics import GenomicsStore
from llm_health.genomics.pipeline import genomics_review_payload
from llm_health.stores import LocalHealthStore


@dataclass(frozen=True)
class V2WebExport:
    """Summary of a generated v2 static dashboard export."""

    output_dir: Path
    data_path: Path
    observation_count: int
    report_count: int
    wearable_daily_count: int
    latest_weights: dict[str, float]


def export_v2_web(wiki_root: Path, output_dir: Path) -> V2WebExport:
    """Generate a local static UX build from canonical de-identified wiki CSVs."""

    wiki_root = wiki_root.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    observations_csv = wiki_root / "output/data/lab-observations-long.csv"
    reports_csv = wiki_root / "output/data/lab-reports.csv"
    wearable_daily_csv = wiki_root / "output/data/apple-health-daily-summary.csv"

    observations, normalization_issues = normalize_observation_rows(
        _safe_profile_rows(_read_csv_dicts(observations_csv))
    )
    observations = _scrub_private_source_fields(observations)
    reports = _merge_source_note_paths(
        _safe_profile_rows(_read_optional_csv_dicts(reports_csv)), wiki_root, output_dir
    )
    reports = _scrub_private_source_fields(reports)
    wearable_daily = _safe_profile_rows(_read_optional_csv_dicts(wearable_daily_csv))
    profile_context = _profile_context(observations)
    _merge_local_health_context(profile_context)
    genomics = _local_genomics_payloads(profile_context)
    profiles = _profile_payloads(observations, wearable_daily, profile_context, genomics)
    for profile in profiles:
        profile_context.setdefault(profile["profile_id"], {})

    _copy_static_assets(output_dir)
    payload: dict[str, Any] = {
        "generated": date.today().isoformat(),
        "source": "canonical de-identified wiki CSV exports plus alias-only llm-health enrollments",
        "observations": observations,
        "normalization_issues": normalization_issues,
        "reports": reports,
        "wearable_daily": wearable_daily,
        "profile_context": profile_context,
        "genomics": genomics,
        "profiles": profiles,
        "export_summary": {
            "observations": len(observations),
            "normalization_issues": len(normalization_issues),
            "reports": len(reports),
            "wearable_daily": len(wearable_daily),
            "profiles": [profile["profile_id"] for profile in profiles],
            "genomics_profiles": sorted(genomics),
        },
    }

    data_path = output_dir / "data.js"
    data_path.write_text(
        "window.HEALTH_ASSESSMENT_V2 = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )

    return V2WebExport(
        output_dir=output_dir,
        data_path=data_path,
        observation_count=len(observations),
        report_count=len(reports),
        wearable_daily_count=len(wearable_daily),
        latest_weights={
            profile: context["currentWeightKg"]
            for profile, context in profile_context.items()
            if _float_or_none(str(context.get("currentWeightKg", ""))) is not None
        },
    )


def _copy_static_assets(output_dir: Path) -> None:
    """Copy the packaged static board assets.

    The v3 UI is a prebuilt React/Mantine bundle.  The legacy hand-rolled v2 files
    remain packaged as a fallback/source reference, but exported dashboards should
    use the polished bundle when it is present.
    """

    package = "llm_health.assessment_v2"
    static_root = resources.files(package).joinpath("web_static_v3")
    if not static_root.is_dir():
        static_root = resources.files(package).joinpath("web_static")

    for stale in ("index.html",):
        (output_dir / stale).unlink(missing_ok=True)
    shutil.rmtree(output_dir / "assets", ignore_errors=True)

    with resources.as_file(static_root) as source_root:
        source_root_path = Path(source_root)
        for source in source_root_path.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(source_root_path)
            target = output_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

    # Compatibility: the standalone upstream v2 contract checks for these
    # filenames. The v3 index does not reference them, but keeping inert copies
    # lets old filesystem smoke tests and scripts continue to pass.
    if static_root.name == "web_static_v3":
        legacy_root = resources.files(package).joinpath("web_static")
        for asset_name in ("app.js", "styles.css"):
            source = legacy_root.joinpath(asset_name)
            with resources.as_file(source) as source_path:
                shutil.copyfile(source_path, output_dir / asset_name)


def _safe_profile_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    safe_rows: list[dict[str, str]] = []
    for row in rows:
        try:
            validate_profile_alias(str(row.get("profile_id", "")))
        except ValueError:
            continue
        safe_rows.append(row)
    return safe_rows


def _scrub_private_source_fields(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop raw-source filename/provider fields before writing dashboard data.js.

    The UI needs stable de-identified ``source_id`` and optional source-note links,
    not raw filenames or provider labels from source CSVs.
    """

    blocked = {"source_file_alias", "provider_alias"}
    scrubbed: list[dict[str, Any]] = []
    for row in rows:
        safe_row: dict[str, Any] = {}
        for key, value in row.items():
            if key in blocked:
                continue
            safe_row[key] = _scrub_raw_source_text(value)
        scrubbed.append(safe_row)
    return scrubbed


_RAW_SOURCE_TOKEN_RE = re.compile(r"\b[^\s/\\;]+\.(?:pdf|xml|cda|xlsx?|csv)\b", re.IGNORECASE)


def _scrub_raw_source_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return _RAW_SOURCE_TOKEN_RE.sub("[source-file]", value)


def _profile_payloads(
    observations: list[dict[str, str]],
    wearable_daily: list[dict[str, str]],
    profile_context: dict[str, Any],
    genomics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return alias-only profile metadata for UI selectors, including zero-data enrollments."""

    profiles: dict[str, dict[str, Any]] = {}

    def add(profile_id: str | None, **metadata: Any) -> None:
        if not profile_id:
            return
        try:
            alias = validate_profile_alias(str(profile_id))
        except ValueError:
            return
        current = profiles.setdefault(alias, {"profile_id": alias})
        for key, value in metadata.items():
            if value not in (None, "", []):
                current[key] = value

    for row in observations:
        add(row.get("profile_id"), role=row.get("family_role"))
    for row in wearable_daily:
        add(row.get("profile_id"), role=row.get("family_role"))
    for profile_id in profile_context:
        add(profile_id)
    for profile_id in (genomics or {}):
        add(profile_id, tags=["CONTEXT", "INFERENCE"])
    for profile in _enrolled_profiles_from_hub():
        add(
            profile.get("profile_id"),
            birth_year=profile.get("birth_year"),
            birth_month=profile.get("birth_month"),
            role=profile.get("role"),
            tags=profile.get("tags") or ["CONTEXT"],
        )

    order = {"rod": 0, "cara": 1}
    return sorted(
        profiles.values(),
        key=lambda row: (order.get(row["profile_id"], 50), row["profile_id"]),
    )


def _enrolled_profiles_from_hub() -> list[dict[str, Any]]:
    """Read alias-only enrolled profiles from the configured llm-health HUB, if present."""

    try:
        store_path = resolve_store_path()
    except Exception:
        return []
    path = store_path / "profiles.jsonl"
    if not path.exists():
        return []
    profiles: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        profile_data = {
            key: row.get(key)
            for key in ("profile_id", "birth_year", "birth_month", "role", "tags", "created_at")
            if row.get(key) is not None
        }
        if "tags" in profile_data and not isinstance(profile_data["tags"], list):
            continue
        try:
            profile = EnrolledProfile.from_dict(profile_data)
        except (AttributeError, TypeError, ValueError):
            continue
        profiles.append(
            {
                "profile_id": profile.profile_id,
                "birth_year": profile.birth_year,
                "birth_month": profile.birth_month,
                "role": profile.role,
                "tags": profile.tags,
            }
        )
    return profiles


def _local_genomics_payloads(profile_context: dict[str, Any]) -> dict[str, Any]:
    """Return rendered, alias-scoped genomics review payloads for the static board.

    The Assessment UI should not read raw genotype files or dense calls.  This export
    uses the same local genomics review pipeline as the standalone genomics GUI and
    carries only source summaries, QC notes, patient summaries, and matched review
    cards into ``data.js``.
    """

    try:
        store_path = resolve_store_path()
    except Exception:
        return {}
    genomics_root = store_path / "genomics"
    if not genomics_root.exists():
        return {}

    store = LocalHealthStore(store_path)
    genomics_store = GenomicsStore(store_path)
    profiles = {
        source.profile_id for source in genomics_store.sources()
    } | {inference.profile_id for inference in genomics_store.inferences()}
    payloads: dict[str, Any] = {}
    for profile in sorted(profiles):
        if not store.profile_exists(profile):
            continue
        try:
            payload = genomics_review_payload(store, profile, limit=80)
        except (PrivacyError, ValueError):
            continue
        _trim_genomics_source_fingerprints(payload)
        if not _artifact_is_safe(payload):
            continue
        payloads[profile] = payload
        context = profile_context.setdefault(profile, {})
        context["genomicsSummary"] = _compact_genomics_context(payload)
    return payloads


def _trim_genomics_source_fingerprints(payload: dict[str, Any]) -> None:
    sources = payload.get("sources", {}).get("sources", [])
    if not isinstance(sources, list):
        return
    for source in sources:
        if isinstance(source, dict):
            source.pop("file_sha256", None)


def _compact_genomics_context(payload: dict[str, Any]) -> dict[str, Any]:
    patient_summary = payload.get("patient_summary") or {}
    sources = payload.get("sources") or {}
    crossrefs = payload.get("crossrefs") or {}
    return {
        "source_count": int(sources.get("count") or 0),
        "marker_count": int(sources.get("variant_count") or 0),
        "card_count": int(crossrefs.get("count") or 0),
        "lead": _safe_artifact_text(patient_summary.get("lead")),
        "tags": _safe_tags(patient_summary.get("tags")) or ["CONTEXT"],
    }


def _merge_local_health_context(profile_context: dict[str, Any]) -> None:
    """Merge alias-only llm-health HUB artifacts into the dashboard context.

    The Assessment board is primarily a longitudinal lab/wearable chart, but new
    family profiles often start with records, self-reports, specialist notes, or
    raw-source-vault catalog entries before any numeric lab rows exist.  Exposing
    a small, privacy-scanned artifact summary keeps those profiles from looking
    empty while preserving the rule that raw source names/paths never enter
    ``data.js``.
    """

    context_notes = _read_hub_jsonl("context_notes.jsonl")
    specialist_notes = _read_hub_jsonl("specialist_notes.jsonl")
    hereditary_risks = _read_hub_jsonl("hereditary_risk_notes.jsonl")
    family_relationships = _read_hub_jsonl("family_relationships.jsonl")
    family_history = _read_hub_jsonl("family_history_events.jsonl")
    quick_review_cards = _read_hub_jsonl("quick_review_cards.jsonl")
    diagnostic_gaps = _read_hub_jsonl("diagnostic_gaps.jsonl")
    research_jobs = _read_hub_jsonl("research_jobs.jsonl")
    source_vault_rows = _read_source_vault_manifest()

    for row in context_notes:
        profile = _safe_alias(row.get("profile_id"))
        if not profile:
            continue
        _append_profile_artifact(
            profile_context,
            profile,
            "contextNotes",
            {
                "kind": "context",
                "date": _date_part(row.get("observed_on") or row.get("created_at")),
                "title": _safe_artifact_text(row.get("subject")),
                "status": _safe_artifact_text(row.get("status")),
                "summary": _safe_artifact_text(row.get("note")),
                "tags": _safe_tags(row.get("tags")) or ["CONTEXT"],
            },
        )

    for row in family_relationships:
        profile = _safe_alias(row.get("profile_id"))
        relative = _safe_alias(row.get("relative_id"))
        if not profile or not relative:
            continue
        relationship = {
            "profile_id": profile,
            "relative_id": relative,
            "relation": _safe_artifact_text(row.get("relation")),
            "degree": row.get("degree") if isinstance(row.get("degree"), int) else None,
            "lineage": _safe_artifact_text(row.get("lineage")),
            "shared_household": row.get("shared_household"),
            "date": _date_part(row.get("created_at")),
            "tags": _safe_tags(row.get("tags")) or ["FAMILY_HISTORY"],
        }
        _append_profile_artifact(
            profile_context,
            profile,
            "familyRelationships",
            relationship,
        )
        _append_profile_artifact(
            profile_context,
            relative,
            "familyRelationships",
            relationship,
        )

    for row in family_history:
        profile = _safe_alias(row.get("profile_id"))
        if not profile:
            continue
        related = [_safe_alias(item) for item in row.get("related_profile_ids", []) or []]
        related = [item for item in related if item]
        history_item = {
            "kind": "family_history",
            "date": _date_part(row.get("created_at")),
            "title": _safe_artifact_text(row.get("condition")),
            "status": _safe_artifact_text(row.get("status")),
            "evidence": _safe_artifact_text(row.get("evidence")),
            "onset_age": row.get("onset_age") if isinstance(row.get("onset_age"), int) else None,
            "profile_id": profile,
            "related_profile_ids": related,
            "summary": _safe_artifact_text(row.get("note")),
            "tags": _safe_tags(row.get("tags")) or ["FAMILY_HISTORY"],
        }
        _append_profile_artifact(profile_context, profile, "familyHistory", history_item)
        for related_profile in related:
            _append_profile_artifact(
                profile_context,
                related_profile,
                "familyHistory",
                history_item,
            )

    for row in specialist_notes:
        profile = _safe_alias(row.get("profile_id"))
        if not profile:
            continue
        _append_profile_artifact(
            profile_context,
            profile,
            "specialistNotes",
            {
                "kind": "specialist",
                "date": _date_part(row.get("created_at")),
                "title": _safe_artifact_text(row.get("title")),
                "status": _safe_artifact_text(row.get("specialist_id")),
                "summary": _safe_artifact_text(row.get("summary")),
                "tags": _safe_tags(row.get("tags")) or ["SPECIALIST_NOTE", "INFERENCE"],
            },
        )

    for row in quick_review_cards:
        profile = _safe_alias(row.get("profile_id"))
        if not profile:
            continue
        _append_profile_artifact(
            profile_context,
            profile,
            "quickReviewCards",
            {
                "kind": "quick_review",
                "date": _date_part(row.get("created_at")),
                "title": _safe_artifact_text(row.get("title")),
                "status": _safe_artifact_text(row.get("lane")),
                "summary": _safe_artifact_text(row.get("summary")),
                "priority": _safe_float(row.get("priority")),
                "tags": _safe_tags(row.get("tags")) or ["INFERENCE"],
            },
        )

    for row in diagnostic_gaps:
        profile = _safe_alias(row.get("profile_id"))
        if not profile:
            continue
        candidate_names = [
            _safe_artifact_text(candidate.get("name"))
            for candidate in row.get("candidates", []) or []
            if isinstance(candidate, dict) and candidate.get("name")
        ][:8]
        context_questions = [
            _safe_artifact_text(question)
            for question in row.get("context_questions", []) or []
            if question
        ][:8]
        _append_profile_artifact(
            profile_context,
            profile,
            "diagnosticGaps",
            {
                "kind": "diagnostic_gap",
                "date": _date_part(row.get("created_at")),
                "title": _safe_artifact_text(row.get("title")),
                "status": _safe_artifact_text(row.get("status")),
                "summary": _safe_artifact_text(row.get("rationale")),
                "gap_type": _safe_artifact_text(row.get("gap_type")),
                "priority": _safe_float(row.get("priority")),
                "candidate_tests": candidate_names,
                "context_questions": context_questions,
                "tags": _safe_tags(row.get("tags")) or ["DATA_GAP", "TEST_CANDIDATE"],
            },
        )

    for row in research_jobs:
        profile = _safe_alias(row.get("profile_id"))
        if not profile:
            continue
        _append_profile_artifact(
            profile_context,
            profile,
            "researchJobs",
            {
                "kind": "research_job",
                "date": _date_part(row.get("created_at")),
                "title": _safe_artifact_text(row.get("topic")),
                "status": _safe_artifact_text(row.get("status")),
                "summary": _safe_artifact_text(row.get("rationale")),
                "priority": _safe_float(row.get("priority")),
                "lenses": [
                    _safe_artifact_text(lens)
                    for lens in row.get("lenses", []) or []
                    if _safe_artifact_text(lens)
                ][:8],
                "tags": ["INFERENCE"],
            },
        )

    for row in hereditary_risks:
        profile = _safe_alias(row.get("profile_id"))
        if not profile:
            continue
        _append_profile_artifact(
            profile_context,
            profile,
            "hereditaryRisks",
            {
                "kind": "hereditary",
                "date": _date_part(row.get("created_at")),
                "title": _safe_artifact_text(row.get("title")),
                "status": f"priority {float(row.get('priority') or 0):.2f}",
                "summary": _safe_artifact_text(row.get("summary")),
                "tags": _safe_tags(row.get("tags")) or ["FAMILY_HISTORY", "INFERENCE"],
            },
        )

    source_summary: dict[str, dict[str, Any]] = {}
    for row in source_vault_rows:
        profile = _safe_alias(row.get("profile_id"))
        if not profile:
            continue
        summary = source_summary.setdefault(
            profile,
            {"count": 0, "copied": 0, "unmatched": 0, "types": {}},
        )
        summary["count"] += 1
        if row.get("copied"):
            summary["copied"] += 1
        if row.get("match_status") in {"hash_only", "unmatched", None, ""}:
            summary["unmatched"] += 1
        source_type = _safe_artifact_text(row.get("source_type")) or "source"
        summary["types"][source_type] = summary["types"].get(source_type, 0) + 1
        created = _date_part(row.get("created_at"))
        if created:
            summary["first_date"] = min(created, summary.get("first_date", created))
            summary["latest_date"] = max(created, summary.get("latest_date", created))

    for profile, summary in source_summary.items():
        context = profile_context.setdefault(profile, {})
        if _artifact_is_safe(summary):
            context["sourceVault"] = summary


def _read_hub_jsonl(filename: str) -> list[dict[str, Any]]:
    try:
        store_path = resolve_store_path()
    except Exception:
        return []
    path = store_path / filename
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _read_source_vault_manifest() -> list[dict[str, Any]]:
    try:
        store_path = resolve_store_path()
    except Exception:
        return []
    path = store_path / "source-vault" / "manifest.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _safe_alias(value: Any) -> str | None:
    try:
        return validate_profile_alias(str(value or ""))
    except ValueError:
        return None


def _append_profile_artifact(
    profile_context: dict[str, Any],
    profile: str,
    key: str,
    artifact: dict[str, Any],
) -> None:
    if not _artifact_is_safe(artifact):
        return
    context = profile_context.setdefault(profile, {})
    bucket = context.setdefault(key, [])
    if isinstance(bucket, list):
        bucket.append(artifact)


def _artifact_is_safe(artifact: dict[str, Any]) -> bool:
    try:
        assert_safe_payload(artifact)
    except PrivacyError:
        return False
    return True


def _safe_artifact_text(value: Any) -> str:
    text = _scrub_raw_source_text(str(value or "")).strip()
    text = re.sub(r"/Users/[^\s]+", "[source-path]", text, flags=re.IGNORECASE)
    text = re.sub(r"\\Users\\[^\s]+", "[source-path]", text, flags=re.IGNORECASE)
    text = re.sub(r"Mobile Documents", "[source-path]", text, flags=re.IGNORECASE)
    return text


def _safe_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        tag = _safe_artifact_text(item).strip()
        if tag and re.fullmatch(r"[A-Z0-9_ -]{2,40}", tag):
            tags.append(tag)
    return tags[:8]


def _date_part(value: Any) -> str:
    text = _safe_artifact_text(value)
    return text[:10] if text else ""


def _safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_optional_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _merge_source_note_paths(
    reports: list[dict[str, str]], wiki_root: Path, output_dir: Path
) -> list[dict[str, str]]:
    """Attach source-note links relative to the v2 static export directory."""

    legacy_paths = _legacy_source_note_paths(wiki_root)
    for report in reports:
        source_id = report.get("source_id", "")
        note_path = _absolute_existing_note_path(legacy_paths.get(source_id), wiki_root)
        if not note_path:
            note_path = _generic_source_note_path(report, wiki_root)
        if not note_path and "_user_weight_" in source_id:
            note_path = _user_weight_note_path(report, wiki_root)
        if note_path:
            report["source_note_path"] = os.path.relpath(note_path, output_dir)
    return reports


def _legacy_source_note_paths(wiki_root: Path) -> dict[str, str]:
    legacy_data_js = wiki_root / "output/projects/assessment-timeline-web-view/data.js"
    if not legacy_data_js.exists():
        return {}
    text = legacy_data_js.read_text(encoding="utf-8").strip()
    prefix = "window.HEALTH_ASSESSMENT_DATA = "
    if not text.startswith(prefix):
        return {}
    if text.endswith(";"):
        text = text[:-1]
    try:
        payload = json.loads(text[len(prefix) :])
    except json.JSONDecodeError:
        return {}
    return {
        report["source_id"]: report["source_note_path"]
        for report in payload.get("reports", [])
        if report.get("source_id") and report.get("source_note_path")
    }


def _absolute_existing_note_path(relative_path: str | None, wiki_root: Path) -> Path | None:
    if not relative_path:
        return None
    legacy_web_dir = wiki_root / "output/projects/assessment-timeline-web-view"
    candidate = (legacy_web_dir / relative_path).resolve()
    return candidate if candidate.exists() else None


def _user_weight_note_path(report: dict[str, str], wiki_root: Path) -> Path | None:
    date_s = report.get("collection_date") or report.get("report_date")
    profile = report.get("profile_id")
    if not date_s or not profile:
        return None
    notes_dir = wiki_root / "raw/notes"
    candidates = sorted(notes_dir.glob(f"{date_s}-{profile}-user-reported-weight-*.md"))
    return candidates[-1] if candidates else None


def _generic_source_note_path(report: dict[str, str], wiki_root: Path) -> Path | None:
    source_id = report.get("source_id")
    if not source_id:
        return None
    needles = (f'source_id: "{source_id}"', f"source_id: {source_id}")
    notes_dir = wiki_root / "raw/notes"
    for note in sorted(notes_dir.glob("*.md"), reverse=True):
        try:
            text = note.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(needle in text for needle in needles):
            return note
    return None
