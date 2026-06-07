from llm_health.assessment_v2.normalization import normalize_observation_row


def test_common_unit_aliases_are_canonicalized_for_display() -> None:
    rows = [
        (
            {
                "profile_id": "rod",
                "observation_date": "2026-01-01",
                "panel_en": "CBC / Hematology",
                "analyte_en": "WBC",
                "numeric_value": "6.1",
                "unit_raw": "10^9/L",
            },
            "10^3/µL",
            "6.1 10^3/µL",
        ),
        (
            {
                "profile_id": "rod",
                "observation_date": "2026-01-01",
                "panel_en": "Vitals",
                "analyte_en": "Weight",
                "numeric_value": "205",
                "unit_raw": "lb",
            },
            "kg",
            "93 kg",
        ),
        (
            {
                "profile_id": "cara",
                "observation_date": "2026-01-01",
                "panel_en": "Thyroid",
                "analyte_en": "TSH",
                "numeric_value": "1.7",
                "unit_raw": "μUI/mL",
            },
            "µIU/mL",
            "1.7 µIU/mL",
        ),
        (
            {
                "profile_id": "cara",
                "observation_date": "2026-01-01",
                "panel_en": "CBC / Hematology",
                "analyte_en": "Neutrophils %",
                "numeric_value": "55",
                "unit_raw": "%",
            },
            "%",
            "55 %",
        ),
    ]

    for source, unit, value in rows:
        normalized = normalize_observation_row(source)
        assert normalized["unit_display"] == unit
        assert normalized["value_display_en"] == value
        assert normalized["normalization_status"] == "ok"


def test_unitless_markers_do_not_require_units() -> None:
    normalized = normalize_observation_row(
        {
            "profile_id": "rod",
            "observation_date": "2026-01-01",
            "panel_en": "Urinalysis",
            "analyte_en": "Urine pH",
            "numeric_value": "6.0",
        }
    )

    assert normalized["unit_display"] == ""
    assert normalized["normalization_warnings"] == ""
