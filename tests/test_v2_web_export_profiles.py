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
