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
from llm_health.core.privacy import validate_profile_alias


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
    profiles = _profile_payloads(observations, wearable_daily, profile_context)
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
        "profiles": profiles,
        "export_summary": {
            "observations": len(observations),
            "normalization_issues": len(normalization_issues),
            "reports": len(reports),
            "wearable_daily": len(wearable_daily),
            "profiles": [profile["profile_id"] for profile in profiles],
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
