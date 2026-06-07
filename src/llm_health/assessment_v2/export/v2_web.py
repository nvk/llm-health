"""Export the Health Assessment v2 static review dashboard."""

from __future__ import annotations

import csv
import json
import os
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

    observations = _read_csv_dicts(observations_csv)
    reports = _merge_source_note_paths(_read_csv_dicts(reports_csv), wiki_root, output_dir)
    wearable_daily = _read_optional_csv_dicts(wearable_daily_csv)
    profile_context = _profile_context(observations)

    _copy_static_assets(output_dir)
    payload: dict[str, Any] = {
        "generated": date.today().isoformat(),
        "source": "canonical de-identified wiki CSV exports",
        "observations": observations,
        "reports": reports,
        "wearable_daily": wearable_daily,
        "profile_context": profile_context,
        "export_summary": {
            "observations": len(observations),
            "reports": len(reports),
            "wearable_daily": len(wearable_daily),
            "profiles": sorted(
                {row.get("profile_id", "") for row in observations if row.get("profile_id")}
            ),
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
    static_dir = resources.files("llm_health.assessment_v2").joinpath("web_static")
    for asset_name in ("index.html", "styles.css", "app.js"):
        source = static_dir.joinpath(asset_name)
        with resources.as_file(source) as source_path:
            shutil.copyfile(source_path, output_dir / asset_name)


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
