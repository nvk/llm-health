import csv
import json
from pathlib import Path

from llm_health.assessment_v2.export.v2_web import export_v2_web

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
DAILY_FIELDS = [
    "profile_id",
    "family_role",
    "date",
    "record_type",
    "category",
    "metric_en",
    "unit",
    "value_text",
    "aggregation_preferred",
    "value_sum",
    "value_avg",
    "value_min",
    "value_max",
    "value_last",
    "duration_seconds",
    "count",
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


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows or [])


def _payload_from_data_js(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    prefix = "window.HEALTH_ASSESSMENT_V2 = "
    assert text.startswith(prefix)
    return json.loads(text[len(prefix) :].rstrip(";\n"))


def test_export_v2_web_includes_zero_data_enrolled_profiles(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    output_dir = tmp_path / "site"
    hub = tmp_path / "hub"
    hub.mkdir()
    (hub / "profiles.jsonl").write_text(
        json.dumps({"profile_id": "sol", "birth_year": 2018, "role": "child", "tags": ["CONTEXT"]})
        + "\n"
        + json.dumps({"profile_id": "lele", "birth_year": 2026, "birth_month": 1, "role": "child"})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_HEALTH_HUB", str(hub))

    _write_csv(
        wiki / "output/data/lab-observations-long.csv",
        OBS_FIELDS,
        [
            {
                "profile_id": "rod",
                "family_role": "father",
                "observation_date": "2026-06-05",
                "panel_en": "Vitals",
                "analyte_en": "Weight",
                "value_raw": "92.7",
                "numeric_value": "92.7",
                "unit_raw": "kg",
                "source_id": "rod_user_weight",
                "source_file_alias": "raw-source-file.pdf",
                "provider_alias": "private-provider",
            }
        ],
    )
    _write_csv(
        wiki / "output/data/lab-reports.csv",
        REPORT_FIELDS,
        [
            {
                "source_id": "rod_user_weight",
                "profile_id": "rod",
                "source_title": "User weight raw-workbook.xlsx",
                "source_file_alias": "raw-report-file.pdf",
                "provider_alias": "private-provider",
            }
        ],
    )
    _write_csv(wiki / "output/data/apple-health-daily-summary.csv", DAILY_FIELDS)

    export = export_v2_web(wiki, output_dir)
    payload = _payload_from_data_js(export.data_path)

    assert payload["export_summary"]["profiles"] == ["rod", "cara", "lele", "sol"]
    assert {profile["profile_id"] for profile in payload["profiles"]} == {
        "rod",
        "cara",
        "lele",
        "sol",
    }
    assert payload["profile_context"]["sol"] == {}
    assert payload["profile_context"]["lele"] == {}
    lele = next(profile for profile in payload["profiles"] if profile["profile_id"] == "lele")
    assert lele["birth_month"] == 1
    data_js = export.data_path.read_text(encoding="utf-8")
    assert "source_file_alias" not in data_js
    assert "provider_alias" not in data_js
    assert ".pdf" not in data_js.lower()
    assert ".xlsx" not in data_js.lower()
    assert "raw-workbook" not in data_js


def test_export_v2_web_skips_unsafe_or_invalid_hub_profiles(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    output_dir = tmp_path / "site"
    hub = tmp_path / "hub"
    hub.mkdir()
    (hub / "profiles.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"profile_id": "sol", "birth_year": 2018, "role": "child"}),
                json.dumps({"profile_id": "Full Name", "birth_year": 2018}),
                json.dumps({"profile_id": "father", "birth_year": 1983}),
                json.dumps({"profile_id": "abe", "role": "from raw.pdf"}),
                json.dumps({"profile_id": "lele", "tags": "CONTEXT"}),
                "{bad-json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_HEALTH_HUB", str(hub))

    _write_csv(wiki / "output/data/lab-observations-long.csv", OBS_FIELDS)
    _write_csv(wiki / "output/data/apple-health-daily-summary.csv", DAILY_FIELDS)

    export = export_v2_web(wiki, output_dir)
    payload = _payload_from_data_js(export.data_path)

    assert payload["export_summary"]["profiles"] == ["rod", "cara", "sol"]
    profile_ids = {profile["profile_id"] for profile in payload["profiles"]}
    assert profile_ids == {"rod", "cara", "sol"}
    data_js = export.data_path.read_text(encoding="utf-8")
    assert "Full Name" not in data_js
    assert "father" not in data_js
    assert "raw.pdf" not in data_js


def test_export_v2_web_includes_context_only_profiles(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    output_dir = tmp_path / "site"
    hub = tmp_path / "hub"
    hub.mkdir()
    (hub / "profiles.jsonl").write_text(
        json.dumps({"profile_id": "eva", "birth_year": 1949, "role": "adult"}) + "\n",
        encoding="utf-8",
    )
    (hub / "context_notes.jsonl").write_text(
        json.dumps(
            {
                "profile_id": "eva",
                "subject": "CAA context",
                "status": "source-reviewed",
                "note": "Context note from scanned raw-file.pdf should not leak a filename.",
                "observed_on": "2026-04-27",
                "tags": ["CONTEXT", "QA_ISSUE"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (hub / "specialist_notes.jsonl").write_text(
        json.dumps(
            {
                "profile_id": "eva",
                "specialist_id": "neuro_mood_cognition",
                "title": "Neuro context",
                "summary": "Use as context, not a numeric lab point.",
                "created_at": "2026-06-08T12:00:00+00:00",
                "tags": ["SPECIALIST_NOTE", "INFERENCE"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (hub / "source-vault").mkdir()
    (hub / "source-vault" / "manifest.jsonl").write_text(
        json.dumps(
            {
                "profile_id": "eva",
                "source_type": "pdf",
                "copied": True,
                "match_status": "hash_only",
                "source_hash": "abc123",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_HEALTH_HUB", str(hub))

    _write_csv(wiki / "output/data/lab-observations-long.csv", OBS_FIELDS)
    _write_csv(wiki / "output/data/apple-health-daily-summary.csv", DAILY_FIELDS)

    export = export_v2_web(wiki, output_dir)
    payload = _payload_from_data_js(export.data_path)

    assert "eva" in payload["export_summary"]["profiles"]
    eva_context = payload["profile_context"]["eva"]
    assert eva_context["contextNotes"][0]["title"] == "CAA context"
    assert "raw-file.pdf" not in eva_context["contextNotes"][0]["summary"]
    assert eva_context["specialistNotes"][0]["title"] == "Neuro context"
    assert eva_context["sourceVault"]["count"] == 1
    assert eva_context["sourceVault"]["copied"] == 1
    assert eva_context["sourceVault"]["unmatched"] == 1
    data_js = export.data_path.read_text(encoding="utf-8")
    assert ".pdf" not in data_js.lower()
    assert "/Users/" not in data_js


def test_export_v2_web_filters_invalid_profile_ids_from_canonical_rows(
    tmp_path, monkeypatch
) -> None:
    wiki = tmp_path / "wiki"
    output_dir = tmp_path / "site"
    monkeypatch.setenv("LLM_HEALTH_HUB", str(tmp_path / "missing-hub"))

    _write_csv(
        wiki / "output/data/lab-observations-long.csv",
        OBS_FIELDS,
        [
            {
                "profile_id": "rod",
                "family_role": "father",
                "observation_date": "2026-06-05",
                "panel_en": "Vitals",
                "analyte_en": "Weight",
                "numeric_value": "92.7",
                "unit_raw": "kg",
                "source_id": "rod_weight",
            },
            {
                "profile_id": "Full Name",
                "family_role": "patient",
                "observation_date": "2026-06-05",
                "panel_en": "Liver",
                "analyte_en": "ALT",
                "numeric_value": "999",
                "unit_raw": "U/L",
                "source_id": "unsafe_source",
            },
        ],
    )
    _write_csv(
        wiki / "output/data/apple-health-daily-summary.csv",
        DAILY_FIELDS,
        [
            {"profile_id": "rod", "date": "2026-06-05", "metric_en": "Step count"},
            {"profile_id": "Full Name", "date": "2026-06-05", "metric_en": "Step count"},
        ],
    )

    export = export_v2_web(wiki, output_dir)
    payload = _payload_from_data_js(export.data_path)

    assert export.observation_count == 1
    assert payload["export_summary"]["wearable_daily"] == 1
    assert {row["profile_id"] for row in payload["observations"]} == {"rod"}
    assert {row["profile_id"] for row in payload["wearable_daily"]} == {"rod"}
    assert "unsafe_source" not in export.data_path.read_text(encoding="utf-8")


def test_export_v2_web_normalizes_language_units_and_adds_qa(tmp_path, monkeypatch) -> None:
    wiki = tmp_path / "wiki"
    output_dir = tmp_path / "site"
    monkeypatch.setenv("LLM_HEALTH_HUB", str(tmp_path / "missing-hub"))

    _write_csv(
        wiki / "output/data/lab-observations-long.csv",
        OBS_FIELDS,
        [
            {
                "observation_id": "rod-mercury-es",
                "profile_id": "rod",
                "family_role": "father",
                "observation_date": "2026-06-05",
                "panel_original": "Metales pesados",
                "panel_en": "Metales pesados",
                "analyte_original": "Mercurio sangre total",
                "analyte_en": "Mercurio sangre total",
                "result_type": "Numeric",
                "value_raw": "61.2",
                "numeric_value": "61.2",
                "unit_raw": "nmol/L",
                "reference_range_raw": "<=19.7",
                "flag_raw": "High",
                "interpretation_en": "Alto",
                "specimen": "sangre total",
                "source_id": "rod_source_1",
            },
            {
                "observation_id": "rod-mercury-pending",
                "profile_id": "rod",
                "family_role": "father",
                "observation_date": "2026-06-06",
                "panel_original": "Metales pesados",
                "panel_en": "Metales pesados",
                "analyte_original": "Mercurio sangre total",
                "analyte_en": "Mercurio sangre total",
                "result_type": "Pending",
                "value_raw": "PENDIENTE",
                "source_id": "rod_source_2",
            },
            {
                "observation_id": "rod-bilirubin-es",
                "profile_id": "rod",
                "family_role": "father",
                "observation_date": "2026-06-07",
                "panel_original": "Perfil hepático",
                "analyte_original": "Bilirrubina total",
                "result_type": "Numeric",
                "value_raw": "1.3",
                "numeric_value": "1.3",
                "unit_raw": "mg/dL",
                "reference_range_raw": "Menos de 1.2",
                "source_id": "rod_source_3",
            },
            {
                "observation_id": "rod-hematocrit-ll",
                "profile_id": "rod",
                "family_role": "father",
                "observation_date": "2026-06-08",
                "panel_original": "Hemograma completo",
                "analyte_original": "Hematocrito",
                "result_type": "Numeric",
                "value_raw": "0.438",
                "numeric_value": "0.438",
                "unit_raw": "L/L",
                "reference_range_raw": "0.400-0.500",
                "source_id": "rod_source_4",
            },
        ],
    )
    _write_csv(wiki / "output/data/apple-health-daily-summary.csv", DAILY_FIELDS)

    export = export_v2_web(wiki, output_dir)
    payload = _payload_from_data_js(export.data_path)
    rows = payload["observations"]
    by_id = {row["observation_id"]: row for row in rows}
    mercury = by_id["rod-mercury-es"]
    pending = by_id["rod-mercury-pending"]
    bilirubin = by_id["rod-bilirubin-es"]
    hematocrit = by_id["rod-hematocrit-ll"]

    assert mercury["display_language"] == "en"
    assert mercury["panel_display_en"] == "Heavy metals"
    assert mercury["analyte_display_en"] == "Mercury"
    assert mercury["unit_display"] == "µg/L"
    assert mercury["numeric_value_display"] == "12.3"
    assert mercury["value_display_en"] == "12.3 µg/L"
    assert mercury["reference_range_display"].startswith("≤3.95 µg/L")
    assert "source: ≤19.7 nmol/L" in mercury["reference_range_display"]
    assert mercury["interpretation_display_en"] == "high"
    assert mercury["specimen_display_en"] == "whole blood"
    assert "unit converted to µg/L" in mercury["normalization_applied"]

    assert pending["value_display_en"] == "pending"
    assert pending["panel_display_en"] == "Heavy metals"
    assert pending["analyte_display_en"] == "Mercury"

    assert bilirubin["panel_display_en"] == "Liver"
    assert bilirubin["analyte_display_en"] == "Total bilirubin"
    assert bilirubin["reference_range_display"] == "<1.2 mg/dL"
    assert "reference range translated to English" in bilirubin["normalization_applied"]

    assert hematocrit["analyte_display_en"] == "Hematocrit"
    assert hematocrit["unit_display"] == "%"
    assert hematocrit["numeric_value_display"] == "43.8"
    assert hematocrit["value_display_en"] == "43.8 %"

    assert payload["export_summary"]["normalization_issues"] >= 2
    assert any(
        issue["kind"] == "normalization_applied"
        for issue in payload["normalization_issues"]
    )
