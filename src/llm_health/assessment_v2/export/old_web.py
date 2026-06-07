"""Export the legacy static web-view payload from canonical de-identified CSVs."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OldWebExport:
    output_path: Path
    observation_count: int
    report_count: int
    latest_weights: dict[str, float]


def export_old_web_data_js(wiki_root: Path, old_web_dir: Path | None = None) -> OldWebExport:
    """Regenerate legacy ``data.js`` from the canonical CSVs."""

    wiki_root = wiki_root.expanduser().resolve()
    old_web_dir = old_web_dir or wiki_root / "output/projects/assessment-timeline-web-view"
    old_web_dir = old_web_dir.expanduser().resolve()
    observations_csv = wiki_root / "output/data/lab-observations-long.csv"
    reports_csv = wiki_root / "output/data/lab-reports.csv"
    output_path = old_web_dir / "data.js"

    observations = _read_csv_dicts(observations_csv)
    reports = _read_csv_dicts(reports_csv)
    reports = _merge_report_note_paths(reports, output_path, wiki_root)
    profile_context = _profile_context(observations)

    payload: dict[str, Any] = {
        "generated": date.today().isoformat(),
        "source": "../../data/lab-observations-long.csv",
        "observations": observations,
        "reports": reports,
        "profile_context": profile_context,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "window.HEALTH_ASSESSMENT_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    return OldWebExport(
        output_path=output_path,
        observation_count=len(observations),
        report_count=len(reports),
        latest_weights={
            profile: context["currentWeightKg"]
            for profile, context in profile_context.items()
            if "currentWeightKg" in context
        },
    )


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _merge_report_note_paths(
    reports: list[dict[str, str]], existing_data_js: Path, wiki_root: Path
) -> list[dict[str, str]]:
    existing_note_paths: dict[str, str] = {}
    if existing_data_js.exists():
        try:
            existing_payload = _read_existing_data_js(existing_data_js)
            existing_note_paths = {
                report["source_id"]: report["source_note_path"]
                for report in existing_payload.get("reports", [])
                if report.get("source_id") and report.get("source_note_path")
            }
        except (json.JSONDecodeError, ValueError, KeyError):
            existing_note_paths = {}

    for report in reports:
        source_id = report.get("source_id", "")
        note_path = existing_note_paths.get(source_id)
        if not note_path:
            note_path = _generic_source_note_path(report, wiki_root, existing_data_js.parent)
        if not note_path and "_user_weight_" in source_id:
            note_path = _user_weight_note_path(report, wiki_root, existing_data_js.parent)
        if note_path:
            report["source_note_path"] = note_path
    return reports


def _read_existing_data_js(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    prefix = "window.HEALTH_ASSESSMENT_DATA = "
    if not text.startswith(prefix):
        raise ValueError("unsupported data.js assignment")
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text[len(prefix) :])


def _user_weight_note_path(
    report: dict[str, str], wiki_root: Path, old_web_dir: Path
) -> str | None:
    date_s = report.get("collection_date") or report.get("report_date")
    profile = report.get("profile_id")
    if not date_s or not profile:
        return None
    notes_dir = wiki_root / "raw/notes"
    candidates = sorted(notes_dir.glob(f"{date_s}-{profile}-user-reported-weight-*.md"))
    if not candidates:
        return None
    return os.path.relpath(candidates[-1], old_web_dir)


def _generic_source_note_path(
    report: dict[str, str], wiki_root: Path, old_web_dir: Path
) -> str | None:
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
            return os.path.relpath(note, old_web_dir)
    return None


def _profile_context(observations: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    context: dict[str, dict[str, Any]] = {
        "rod": {
            "birthYear": 1983,
            "ageContext": "birth year 1983",
            "believedConditions": ["Gilbert syndrome"],
            "supplementContext": (
                "desiccated liver, selenium+iodine, B-complex/B12, electrolytes, Liver-G.I. Detox"
            ),
        },
        "cara": {
            "birthYear": 1983,
            "ageContext": "birth year 1983",
            "supplementContext": (
                "REVIVE organ-meat/herbal supplement; postpartum/lactation context-gated"
            ),
        },
    }
    for profile in list(context):
        weight = _latest_anthropometric(observations, profile, "weight")
        height = _latest_anthropometric(observations, profile, "height")
        if weight:
            context[profile]["currentWeightKg"] = round(weight[1], 1)
            context[profile]["currentWeightDate"] = weight[0]
        if height:
            context[profile]["latestHeightCm"] = round(height[1], 1)
        if weight and height and height[1] > 0:
            context[profile]["bmiEstimate"] = round(weight[1] / ((height[1] / 100) ** 2), 1)
    return context


def _latest_anthropometric(
    observations: list[dict[str, str]], profile: str, analyte: str
) -> tuple[str, float] | None:
    rows: list[tuple[str, str, float]] = []
    for row in observations:
        if row.get("profile_id") != profile:
            continue
        if row.get("analyte_en", "").strip().lower() != analyte:
            continue
        date_s = row.get("observation_date", "")
        value = _float_or_none(row.get("numeric_value"))
        if not date_s or value is None:
            continue
        unit = row.get("unit_raw", "").strip().lower()
        if analyte == "weight" and unit in {"lb", "lbs", "pound", "pounds"}:
            value *= 0.45359237
        if analyte == "height" and unit in {"in", "inch", "inches"}:
            value *= 2.54
        rows.append((date_s, row.get("source_id", ""), value))
    if not rows:
        return None
    latest = sorted(rows, key=lambda item: (item[0], item[1]))[-1]
    return latest[0], latest[2]


def _float_or_none(value: str | None) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except ValueError:
        return None
