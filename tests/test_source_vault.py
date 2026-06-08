from __future__ import annotations

import csv
from pathlib import Path

from llm_health.source_vault import (
    audit_ingested_sources,
    catalog_sources,
    init_source_vault,
    load_records,
    render_audit,
)

OBS_FIELDS = [
    "observation_id",
    "profile_id",
    "family_role",
    "observation_date",
    "collection_date",
    "report_date",
    "source_id",
    "source_title",
    "source_file_alias",
    "provider_alias",
    "language_original",
    "panel_original",
    "panel_en",
    "analyte_original",
    "analyte_en",
    "loinc_code",
    "loinc_mapping_status",
    "result_type",
    "value_raw",
    "numeric_value",
    "comparator",
    "unit_raw",
    "ucum_unit",
    "reference_range_raw",
    "flag_raw",
    "interpretation_en",
    "specimen",
    "method",
    "confidence",
    "notes",
]
REPORT_FIELDS = [
    "source_id",
    "profile_id",
    "family_role",
    "provider_alias",
    "source_title",
    "collection_date",
    "report_date",
    "language",
    "status",
    "source_file_alias",
    "notes",
]


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_source_vault_catalog_hashes_without_storing_raw_path_or_name(tmp_path: Path) -> None:
    store = tmp_path / "hub"
    wiki = tmp_path / "wiki"
    raw = tmp_path / "input" / "rod-source-a.pdf"
    raw.parent.mkdir()
    raw.write_bytes(b"fake pdf bytes with ALT 61")
    _write_csv(
        wiki / "output/data/lab-reports.csv",
        REPORT_FIELDS,
        [
            {
                "source_id": "rod_fixture_source",
                "profile_id": "rod",
                "source_file_alias": "rod/rod-source-a.pdf",
            }
        ],
    )

    init_source_vault(store)
    summary = catalog_sources(store, [raw.parent], wiki_root=wiki, copy_raw=True)
    assert summary.scanned_files == 1
    assert summary.cataloged == 1
    assert summary.copied == 1
    assert summary.matched == 1

    records = load_records(store)
    assert len(records) == 1
    assert records[0].source_id == "rod_fixture_source"
    manifest = (store / "source-vault" / "manifest.jsonl").read_text()
    assert "rod-source-a" not in manifest
    assert str(raw.parent) not in manifest
    assert (store / "source-vault" / "blobs" / records[0].source_hash).exists()


def test_source_audit_flags_medium_rows_and_validation(tmp_path: Path) -> None:
    store = tmp_path / "hub"
    wiki = tmp_path / "wiki"
    _write_csv(
        wiki / "output/data/lab-observations-long.csv",
        OBS_FIELDS,
        [
            {
                "observation_id": "obs1",
                "profile_id": "rod",
                "observation_date": "2026-01-01",
                "source_id": "rod_fixture_source",
                "panel_en": "Liver",
                "analyte_en": "Total bilirubin",
                "value_raw": "2.1",
                "numeric_value": "2.1",
                "unit_raw": "mg/dL",
                "result_type": "Numeric",
                "confidence": "medium",
                "notes": "Page OCR order ambiguous",
            },
            {
                "observation_id": "obs2",
                "profile_id": "rod",
                "observation_date": "2026-01-01",
                "source_id": "rod_fixture_source",
                "panel_en": "Liver",
                "analyte_en": "Direct Bilirubin",
                "value_raw": "0.3",
                "numeric_value": "0.3",
                "unit_raw": "mg/dL",
                "result_type": "Numeric",
                "confidence": "high",
            },
            {
                "observation_id": "obs3",
                "profile_id": "rod",
                "observation_date": "2026-01-01",
                "source_id": "rod_fixture_source",
                "panel_en": "Liver",
                "analyte_en": "Indirect Bilirubin",
                "value_raw": "0.4",
                "numeric_value": "0.4",
                "unit_raw": "mg/dL",
                "result_type": "Numeric",
                "confidence": "high",
            },
        ],
    )

    result = audit_ingested_sources(store, wiki, profile_id="rod", focus="medium", persist=True)
    assert result.medium_row_count == 1
    assert result.review_row_count == 1
    assert result.validation_issue_count == 1
    assert result.sources[0]["status"] in {"source_missing", "qa_validation_issue"}
    rendered = render_audit(result)
    assert "Rows needing audit" in rendered
    assert "bilirubin_sum" in rendered


def test_source_audit_does_not_require_vault_for_user_provided_context(tmp_path: Path) -> None:
    store = tmp_path / "hub"
    wiki = tmp_path / "wiki"
    _write_csv(
        wiki / "output/data/lab-observations-long.csv",
        OBS_FIELDS,
        [
            {
                "observation_id": "obs-user",
                "profile_id": "rod",
                "observation_date": "2026-01-02",
                "source_id": "rod_user_weight_2026-01-02",
                "source_title": "User-provided current weight",
                "source_file_alias": "user-provided/weight-context-2026-01-02",
                "panel_en": "Anthropometrics",
                "analyte_en": "Weight",
                "value_raw": "92",
                "numeric_value": "92",
                "unit_raw": "kg",
                "result_type": "Numeric",
                "confidence": "medium",
                "notes": "Self-reported context.",
            }
        ],
    )

    result = audit_ingested_sources(store, wiki, profile_id="rod", focus="medium", persist=False)
    assert result.missing_source_count == 0
    assert result.sources == []
    assert result.review_rows[0]["reason"] == "medium_confidence"
