"""Upsert de-identified user-provided facts into canonical wiki CSVs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

PROFILE_ROLES = {"rod": "father", "cara": "mother"}


@dataclass(frozen=True)
class AddedWeight:
    profile_id: str
    measurement_date: date
    kg: float
    observation_id: str
    source_id: str
    note_path: Path


def upsert_user_weight(
    wiki_root: Path, profile_id: str, measurement_date: date, kg: float
) -> AddedWeight:
    """Upsert one user-provided weight into canonical de-identified lab/vitals CSVs."""

    profile_id = profile_id.strip().lower()
    if profile_id not in PROFILE_ROLES:
        raise ValueError(f"Unsupported profile: {profile_id!r}")
    if not (20 <= kg <= 400):
        raise ValueError(f"Weight kg looks implausible: {kg!r}")

    wiki_root = wiki_root.expanduser().resolve()
    observations_csv = wiki_root / "output/data/lab-observations-long.csv"
    reports_csv = wiki_root / "output/data/lab-reports.csv"
    if not observations_csv.exists():
        raise FileNotFoundError(f"Missing canonical observations CSV: {observations_csv}")
    if not reports_csv.exists():
        raise FileNotFoundError(f"Missing canonical reports CSV: {reports_csv}")

    date_s = measurement_date.isoformat()
    kg_s = _format_number(kg)
    kg_slug = kg_s.replace(".", "p")
    source_id = f"{profile_id}_user_weight_{date_s}"
    observation_id = f"{profile_id}-user-weight-{date_s}-{kg_slug}kg"
    role = PROFILE_ROLES[profile_id]
    source_file_alias = f"user-provided/weight-context-{date_s}"
    title = f"User-provided current weight ({role} profile; {date_s})"
    note_name = f"{date_s}-{profile_id}-user-reported-weight-{kg_slug}kg.md"
    note_path = wiki_root / "raw/notes" / note_name

    report_row = {
        "source_id": source_id,
        "profile_id": profile_id,
        "family_role": role,
        "provider_alias": "user-provided context",
        "source_title": title,
        "collection_date": date_s,
        "report_date": date_s,
        "language": "en",
        "status": "user-provided-context",
        "source_file_alias": source_file_alias,
        "notes": (
            f"User-provided same-day weight of {kg_s} kg; no external document attached; "
            "de-identified context observation."
        ),
    }
    observation_row = {
        "observation_id": observation_id,
        "profile_id": profile_id,
        "family_role": role,
        "observation_date": date_s,
        "collection_date": date_s,
        "report_date": date_s,
        "source_id": source_id,
        "source_title": title,
        "source_file_alias": source_file_alias,
        "provider_alias": "user-provided context",
        "language_original": "en",
        "panel_original": "Vitals / anthropometrics",
        "panel_en": "Vitals",
        "analyte_original": "Weight",
        "analyte_en": "Weight",
        "loinc_code": "",
        "loinc_mapping_status": "unmapped",
        "result_type": "Numeric",
        "value_raw": kg_s,
        "numeric_value": kg_s,
        "comparator": "",
        "unit_raw": "kg",
        "ucum_unit": "",
        "reference_range_raw": "",
        "flag_raw": "",
        "interpretation_en": "",
        "specimen": "",
        "method": "user-provided measurement",
        "confidence": "medium",
        "notes": (
            "User-reported same-day weight; no external document attached; "
            "direct identifiers omitted."
        ),
    }

    _upsert_csv_row(reports_csv, "source_id", report_row)
    _upsert_csv_row(observations_csv, "source_id", observation_row)
    _write_weight_note(note_path, profile_id, role, measurement_date, kg_s)
    _append_log(wiki_root / "log.md", date_s, profile_id, kg_s)

    return AddedWeight(profile_id, measurement_date, kg, observation_id, source_id, note_path)


def _upsert_csv_row(path: Path, key: str, row: dict[str, str]) -> None:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        rows = list(reader)

    clean_row = {field: row.get(field, "") for field in fieldnames}
    replaced = False
    for index, existing in enumerate(rows):
        if existing.get(key) == clean_row[key]:
            rows[index] = clean_row
            replaced = True
            break
    if not replaced:
        rows.append(clean_row)

    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_weight_note(
    path: Path, profile_id: str, role: str, measurement_date: date, kg_s: str
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    date_s = measurement_date.isoformat()
    path.write_text(
        f"""---
title: {profile_id.title()} user-reported weight {kg_s} kg on {date_s}
source_type: user-provided-context
ingested: {date_s}
updated: {date_s}
tags: [vitals, anthropometrics, weight, user-provided, {profile_id}, deidentified]
quality: 3
confidence: medium
summary: User-provided de-identified weight {kg_s} kg on {date_s}.
---

# {profile_id.title()} user-reported weight {kg_s} kg on {date_s}

The user provided a same-day current weight for `{profile_id}` ({role}):
**{kg_s} kg** on **{date_s}**.

## Dataset handling

- Upserted one de-identified `Vitals` observation row to `output/data/lab-observations-long.csv`.
- Upserted one user-provided source/report record to `output/data/lab-reports.csv`.
- Marked confidence as `medium` because this is a user-provided measurement without
  an attached external document.

## Guardrails

- This is a weight measurement/context point; use it as context alongside
  appropriate clinical review.
- No direct identifiers are stored in this note.
- Full birth date remains intentionally omitted; age context continues to use birth year only.
""",
        encoding="utf-8",
    )


def _append_log(path: Path, date_s: str, profile_id: str, kg_s: str) -> None:
    if not path.exists():
        return
    line = (
        f"## [{date_s}] ingest | Added user-provided {profile_id.title()} current weight "
        f"{kg_s} kg for {date_s} as a de-identified Vitals observation\n"
    )
    text = path.read_text(encoding="utf-8")
    if line not in text:
        path.write_text(text.rstrip() + "\n\n" + line, encoding="utf-8")


def _format_number(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")
