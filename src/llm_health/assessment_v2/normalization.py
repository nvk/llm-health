"""Language/unit normalization and QA for Assessment v2 exports.

The dashboard should display one review language (English) and one comparable
unit per marker when a conversion is explicitly known. Raw source fields remain
in the de-identified payload for provenance, but UI code should prefer the
*_display fields created here.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

_NUMERIC_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
_NON_ENGLISH_RE = re.compile(
    r"\b(pendiente|bilirrubina|hemat[ií]es|leucocitos|plaquetas|sangre|orina|"
    r"gl[oó]bulos|colesterol|triglic[eé]ridos|metales|pesados|hierro|calcio|"
    r"menos|menor|mayor|qu[ií]mica|hep[aá]tico|an[aá]lisis)\b",
    re.IGNORECASE,
)

PANEL_TRANSLATIONS = {
    "analisis pendientes": "Pending tests",
    "análisis pendientes": "Pending tests",
    "bilirrubinas": "Bilirubins",
    "formula roja": "Red cell formula",
    "metales pesados": "Heavy metals",
    "pruebas pendientes": "Pending tests",
    "quimica sanguinea": "Blood chemistry",
    "química sanguínea": "Blood chemistry",
    "higado": "Liver",
    "hepatico": "Liver",
    "hepático": "Liver",
    "perfil hepatico": "Liver",
    "perfil hepático": "Liver",
    "hemograma": "CBC / Hematology",
    "hemograma completo": "Complete blood count",
    "hematologia": "CBC / Hematology",
    "hematología": "CBC / Hematology",
    "lipidos": "Lipids",
    "perfil lipidico": "Lipids",
    "hormonas": "Hormones",
    "tiroides": "Thyroid",
    "orina": "Urinalysis",
}

MARKER_TRANSLATIONS = {
    "bilirrubina indirecta": "Indirect bilirubin",
    "bilirrubina directa": "Direct bilirubin",
    "bilirrubina total": "Total bilirubin",
    "mercurio": "Mercury",
    "mercurio en sangre": "Mercury",
    "mercurio sangre total": "Mercury",
    "mercurio sangre": "Mercury",
    "mercury whole blood": "Mercury",
    "plomo": "Lead",
    "arsenico": "Arsenic",
    "arsénico": "Arsenic",
    "cadmio": "Cadmium",
    "glucosa": "Glucose",
    "colesterol total": "Total cholesterol",
    "trigliceridos": "Triglycerides",
    "triglicéridos": "Triglycerides",
    "hemoglobina": "Hemoglobin",
    "leucocitos": "WBC",
    "plaquetas": "Platelets",
    "hematocrito": "Hematocrit",
    "peso": "Weight",
    "altura": "Height",
}

VALUE_TRANSLATIONS = {
    "pendiente": "pending",
    "en proceso": "pending",
    "not resulted": "pending",
    "cancelado": "cancelled",
    "cancelled": "cancelled",
}

INTERPRETATION_TRANSLATIONS = {
    "alto": "high",
    "alta": "high",
    "elevado": "high",
    "elevada": "high",
    "bajo": "low",
    "baja": "low",
    "normal": "normal",
    "pendiente": "pending",
}

SPECIMEN_TRANSLATIONS = {
    "sangre": "blood",
    "sangre total": "whole blood",
    "orina": "urine",
    "suero": "serum",
    "plasma": "plasma",
}


@dataclass(frozen=True)
class UnitRule:
    marker_patterns: tuple[str, ...]
    target_unit: str
    factors: dict[str, float]
    rationale: str


UNIT_RULES = [
    UnitRule(
        marker_patterns=("mercury", "mercurio"),
        target_unit="µg/L",
        factors={"µg/l": 1.0, "ng/ml": 1.0, "nmol/l": 0.200592, "µmol/l": 200.592},
        rationale="Hg atomic mass 200.592 g/mol; blood mercury often appears as nmol/L or µg/L.",
    ),
    UnitRule(
        marker_patterns=("lead", "plomo"),
        target_unit="µg/dL",
        factors={"µg/dl": 1.0, "µg/l": 0.1, "nmol/l": 0.02072, "µmol/l": 20.72},
        rationale="Pb atomic mass about 207.2 g/mol; blood lead commonly displayed as µg/dL.",
    ),
    UnitRule(
        marker_patterns=("cadmium", "cadmio"),
        target_unit="µg/L",
        factors={"µg/l": 1.0, "ng/ml": 1.0, "nmol/l": 0.112414, "µmol/l": 112.414},
        rationale="Cd atomic mass about 112.414 g/mol.",
    ),
    UnitRule(
        marker_patterns=("arsenic", "arsenico", "arsénico"),
        target_unit="µg/L",
        factors={"µg/l": 1.0, "ng/ml": 1.0, "nmol/l": 0.0749216, "µmol/l": 74.9216},
        rationale="As atomic mass about 74.9216 g/mol.",
    ),
    UnitRule(
        marker_patterns=("bilirubin", "bilirrubina"),
        target_unit="mg/dL",
        factors={"mg/dl": 1.0, "µmol/l": 1 / 17.104},
        rationale="Bilirubin conventional conversion: 1 mg/dL ≈ 17.104 µmol/L.",
    ),
    UnitRule(
        marker_patterns=("hematocrit", "hematocrito", "hct"),
        target_unit="%",
        factors={"%": 1.0, "l/l": 100.0},
        rationale="Hematocrit L/L is a volume fraction; multiply by 100 to display percent.",
    ),
    UnitRule(
        marker_patterns=("hemoglobin", "hemoglobina"),
        target_unit="g/dL",
        factors={"g/dl": 1.0, "g/l": 0.1},
        rationale="Mass concentration conversion: 1 g/dL = 10 g/L.",
    ),
    UnitRule(
        marker_patterns=("mchc",),
        target_unit="g/dL",
        factors={"g/dl": 1.0, "g/l": 0.1},
        rationale="Mass concentration conversion: 1 g/dL = 10 g/L.",
    ),
    UnitRule(
        marker_patterns=(
            "neutrophils %",
            "lymphocytes %",
            "monocytes %",
            "eosinophils %",
            "basophils %",
        ),
        target_unit="%",
        factors={"%": 1.0},
        rationale="Differential percentages are unitless fractions displayed as percent.",
    ),
    UnitRule(
        marker_patterns=("nucleated rbc",),
        target_unit="10^3/µL",
        factors={"10^3/µl": 1.0, "10^9/l": 1.0},
        rationale="Cell-count convention: 1 x10^3/µL = 1 x10^9/L.",
    ),
    UnitRule(
        marker_patterns=(
            "wbc",
            "leukocyte",
            "leucocyte",
            "neutrophils",
            "lymphocytes",
            "monocytes",
            "eosinophils",
            "basophils",
        ),
        target_unit="10^3/µL",
        factors={"10^3/µl": 1.0, "10^9/l": 1.0},
        rationale="Cell-count convention: 1 x10^3/µL = 1 x10^9/L.",
    ),
    UnitRule(
        marker_patterns=("platelet", "plaquetas"),
        target_unit="10^3/µL",
        factors={"10^3/µl": 1.0, "10^9/l": 1.0},
        rationale="Cell-count convention: 1 x10^3/µL = 1 x10^9/L.",
    ),
    UnitRule(
        marker_patterns=("rbc", "erythrocyte", "red blood"),
        target_unit="10^6/µL",
        factors={"10^6/µl": 1.0, "10^12/l": 1.0},
        rationale="Cell-count convention: 1 x10^6/µL = 1 x10^12/L.",
    ),
    UnitRule(
        marker_patterns=("tsh",),
        target_unit="µIU/mL",
        factors={"µiu/ml": 1.0, "miu/l": 1.0},
        rationale="Thyroid convention: 1 mIU/L = 1 µIU/mL.",
    ),
    UnitRule(
        marker_patterns=("fsh", "lh"),
        target_unit="mIU/mL",
        factors={"miu/ml": 1.0},
        rationale="Spanish mUI/mL and English mIU/mL denote milli-international units per mL.",
    ),
    UnitRule(
        marker_patterns=("ceruloplasmin",),
        target_unit="mg/L",
        factors={"mg/l": 1.0, "g/l": 1000.0},
        rationale="Mass concentration conversion: 1 g/L = 1000 mg/L.",
    ),
    UnitRule(
        marker_patterns=("weight", "body mass", "peso"),
        target_unit="kg",
        factors={"kg": 1.0, "lb": 0.45359237, "lbs": 0.45359237},
        rationale="Exact international avoirdupois pound conversion: 1 lb = 0.45359237 kg.",
    ),
    UnitRule(
        marker_patterns=("height", "altura"),
        target_unit="cm",
        factors={"cm": 1.0, "in": 2.54, "inch": 2.54, "inches": 2.54},
        rationale="International inch conversion: 1 in = 2.54 cm.",
    ),
]


def normalize_observation_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return rows with English/canonical display fields plus aggregate QA issues."""

    normalized = [normalize_observation_row(row) for row in rows]
    issues = normalization_issues(normalized)
    return normalized, issues


def normalize_observation_row(row: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = dict(row)
    warnings: list[str] = []
    applied: list[str] = []

    panel = _english_text(row.get("panel_en"), row.get("panel_original"), PANEL_TRANSLATIONS)
    marker = _english_text(row.get("analyte_en"), row.get("analyte_original"), MARKER_TRANSLATIONS)
    marker = _normalize_marker_display(marker)
    value_raw = _translate_value(row.get("value_raw"))
    interpretation = _english_text(
        row.get("interpretation_en"), row.get("interpretation_en"), INTERPRETATION_TRANSLATIONS
    )
    specimen = _english_text(row.get("specimen"), row.get("specimen"), SPECIMEN_TRANSLATIONS)

    source_unit = row.get("unit_raw") or row.get("ucum_unit") or ""
    unit_display, unit_key = canonical_unit(source_unit)
    numeric = _float_or_none(row.get("numeric_value"))
    factor = 1.0
    rule = _rule_for_marker(marker or row.get("analyte_en") or row.get("analyte_original") or "")
    if rule and unit_key in rule.factors:
        factor = rule.factors[unit_key]
        if unit_display != rule.target_unit or factor != 1.0:
            applied.append(f"unit converted to {rule.target_unit}")
            unit_display = rule.target_unit
    elif unit_display != (source_unit or ""):
        applied.append("unit symbol normalized")

    display_numeric = numeric * factor if numeric is not None else None
    value_display = _value_display(row, value_raw, display_numeric, unit_display)
    ref_display = _reference_display(
        row.get("reference_range_raw"), source_unit, unit_display, factor
    )

    if _is_non_english(row.get("panel_en")) or _is_non_english(row.get("panel_original")):
        applied.append("panel translated to English")
    if _is_non_english(row.get("analyte_en")) or _is_non_english(row.get("analyte_original")):
        applied.append("marker translated to English")
    if _is_non_english(row.get("value_raw")) or _is_non_english(row.get("interpretation_en")):
        applied.append("result/status translated to English")
    if _is_non_english(row.get("reference_range_raw")):
        applied.append("reference range translated to English")
    if numeric is not None and not unit_display and not _is_unitless_marker(marker):
        warnings.append("numeric result lacks a display unit")
    if rule and unit_key and unit_key not in rule.factors:
        warnings.append(f"no approved conversion from {source_unit} to {rule.target_unit}")
    if not panel:
        warnings.append("missing English panel")
    if not marker:
        warnings.append("missing English marker")

    out.update(
        {
            "display_language": "en",
            "panel_display_en": panel
            or row.get("panel_en")
            or row.get("panel_original")
            or "Other",
            "analyte_display_en": marker
            or row.get("analyte_en")
            or row.get("analyte_original")
            or "Unknown marker",
            "value_display_en": value_display,
            "numeric_value_display": _number_string(display_numeric),
            "unit_display": unit_display,
            "reference_range_display": ref_display,
            "interpretation_display_en": interpretation,
            "specimen_display_en": specimen,
            "normalization_status": "review" if warnings else "ok",
            "normalization_applied": "; ".join(dict.fromkeys(applied)),
            "normalization_warnings": "; ".join(dict.fromkeys(warnings)),
        }
    )
    return out


def normalization_issues(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        warnings = str(row.get("normalization_warnings") or "")
        applied = str(row.get("normalization_applied") or "")
        if warnings:
            issues.append(
                _issue(
                    "normalization_warning",
                    "warning",
                    row,
                    warnings,
                    "Review source row before trend/inference use.",
                )
            )
        if applied:
            issues.append(
                _issue(
                    "normalization_applied",
                    "info",
                    row,
                    applied,
                    "Displayed in English/canonical units; raw source fields remain "
                    "available in data.js.",
                )
            )

    by_marker: dict[tuple[str, str, str], set[str]] = {}
    for row in rows:
        if not row.get("numeric_value_display"):
            continue
        key = (
            str(row.get("profile_id") or ""),
            str(row.get("analyte_display_en") or ""),
            str(row.get("specimen_display_en") or ""),
        )
        by_marker.setdefault(key, set()).add(str(row.get("unit_display") or ""))
    for (profile, marker, specimen), units in sorted(by_marker.items()):
        cleaned = sorted(u for u in units if u)
        if len(cleaned) > 1:
            issues.append(
                {
                    "kind": "mixed_display_units",
                    "severity": "warning",
                    "profile_id": profile,
                    "marker": marker,
                    "specimen": specimen,
                    "message": f"{marker} still has mixed display units: {', '.join(cleaned)}",
                    "action": "Add an approved marker-specific conversion before overlaying "
                    "or resolving across units.",
                }
            )
    return issues


def canonical_unit(unit: str | None) -> tuple[str, str]:
    text = (unit or "").strip()
    if not text:
        return "", ""
    text = text.replace("μ", "µ")
    text = re.sub("umol", "µmol", text, flags=re.IGNORECASE)
    text = re.sub("ug", "µg", text, flags=re.IGNORECASE)
    text = re.sub("uiu", "µIU", text, flags=re.IGNORECASE)
    text = re.sub("uui", "µIU", text, flags=re.IGNORECASE)
    text = re.sub("µui", "µIU", text, flags=re.IGNORECASE)
    text = re.sub("mui", "mIU", text, flags=re.IGNORECASE)
    text = re.sub("ul", "µL", text, flags=re.IGNORECASE)
    compact = re.sub(r"\s+", "", text)
    lower = compact.lower()
    display_map = {
        "u/l": "U/L",
        "iu/l": "IU/L",
        "µg/l": "µg/L",
        "ng/ml": "ng/mL",
        "µg/dl": "µg/dL",
        "mg/dl": "mg/dL",
        "g/dl": "g/dL",
        "g/l": "g/L",
        "mg/l": "mg/L",
        "mmol/l": "mmol/L",
        "µmol/l": "µmol/L",
        "nmol/l": "nmol/L",
        "miu/l": "mIU/L",
        "miu/ml": "mIU/mL",
        "µiu/ml": "µIU/mL",
        "µui/ml": "µIU/mL",
        "10^3/µl": "10^3/µL",
        "10^6/µl": "10^6/µL",
        "10^9/l": "10^9/L",
        "10^12/l": "10^12/L",
        "pg/ml": "pg/mL",
        "pg/dl": "pg/dL",
        "ng/dl": "ng/dL",
        "l/l": "L/L",
        "kg": "kg",
        "lb": "lb",
        "lbs": "lb",
        "cm": "cm",
        "in": "in",
        "inch": "in",
        "inches": "in",
        "%": "%",
    }
    return display_map.get(lower, compact), lower


def _issue(
    kind: str, severity: str, row: dict[str, Any], message: str, action: str
) -> dict[str, Any]:
    return {
        "kind": kind,
        "severity": severity,
        "profile_id": row.get("profile_id", ""),
        "row_ref": row.get("observation_id") or row.get("source_id") or "",
        "marker": row.get("analyte_display_en") or row.get("analyte_en") or "",
        "date": row.get("observation_date")
        or row.get("collection_date")
        or row.get("report_date")
        or "",
        "message": message,
        "action": action,
    }


def _english_text(value: str | None, fallback: str | None, translations: dict[str, str]) -> str:
    first_nonempty = ""
    for candidate in (value, fallback):
        text = (candidate or "").strip()
        if not text:
            continue
        if not first_nonempty:
            first_nonempty = text
        translated = _translate_text(text, translations)
        if translated:
            return translated
        if not _is_non_english(text):
            return text
    return first_nonempty


def _translate_text(text: str, translations: dict[str, str]) -> str:
    translated = translations.get(_key(text))
    if translated:
        return translated
    if "/" in text:
        parts = [
            _translate_text(part.strip(), translations) or part.strip()
            for part in text.split("/")
        ]
        return " / ".join(part for part in parts if part)
    key = _key(text)
    for source, target in translations.items():
        if source in key:
            return target
    return ""


def _translate_value(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    translated = VALUE_TRANSLATIONS.get(_key(text))
    return translated or text


def _normalize_marker_display(marker: str) -> str:
    text = marker.strip()
    if re.search(r"\bmercury\b", text, re.IGNORECASE):
        return "Mercury"
    if re.search(r"\blead\b", text, re.IGNORECASE):
        return "Lead"
    if re.search(r"\barsenic\b", text, re.IGNORECASE):
        return "Arsenic"
    if re.search(r"\bcadmium\b", text, re.IGNORECASE):
        return "Cadmium"
    return text


def _rule_for_marker(marker: str) -> UnitRule | None:
    needle = _key(marker)
    for rule in UNIT_RULES:
        if any(pattern in needle for pattern in rule.marker_patterns):
            return rule
    return None


def _is_unitless_marker(marker: str) -> bool:
    text = _key(marker)
    if "specific gravity" in text or "body mass index" in text or "bmi" in text:
        return True
    return bool(re.search(r"\bph\b", text))


def _value_display(
    row: dict[str, str], value_raw: str, numeric: float | None, unit_display: str
) -> str:
    if _key(value_raw) in VALUE_TRANSLATIONS.values() or _key(value_raw) in VALUE_TRANSLATIONS:
        return VALUE_TRANSLATIONS.get(_key(value_raw), value_raw)
    comparator = _display_comparator(row.get("comparator") or _leading_comparator(value_raw))
    if numeric is None:
        return value_raw
    return f"{comparator}{_format_number(numeric)}{f' {unit_display}' if unit_display else ''}"


def _reference_display(
    raw: str | None, source_unit: str, target_unit: str, factor: float
) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    text = _display_comparator_text(text)
    source_display, _ = canonical_unit(source_unit)
    if factor != 1.0:
        converted = _NUMERIC_RE.sub(
            lambda match: _format_number(float(match.group(0).replace(",", ".")) * factor), text
        )
        return f"{converted} {target_unit} (source: {text} {source_display})"
    if target_unit and not _contains_unit(text, target_unit):
        return f"{text} {target_unit}"
    return text


def _display_comparator(value: str | None) -> str:
    text = (value or "").strip()
    if text in {"≤", "<="}:
        return "≤"
    if text in {"≥", ">="}:
        return "≥"
    if text in {"<", ">"}:
        return text
    return ""


def _leading_comparator(value: str) -> str:
    match = re.match(r"\s*(<=|>=|≤|≥|<|>)", value or "")
    return match.group(1) if match else ""


def _display_comparator_text(value: str) -> str:
    text = value.replace("<=", "≤").replace(">=", "≥")
    text = re.sub(r"\bmenos\s+de\b", "<", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmenor(?:es)?\s+(?:que|a)\b", "<", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmayor(?:es)?\s+(?:que|a)\b", ">", text, flags=re.IGNORECASE)
    text = re.sub(r"\bm[aá]s\s+de\b", ">", text, flags=re.IGNORECASE)
    text = re.sub(r"([<>≤≥])\s+", r"\1", text)
    return text


def _contains_unit(text: str, unit: str) -> bool:
    key = _key(text).replace("/", "")
    unit_key = _key(unit).replace("/", "")
    return unit_key in key


def _format_number(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    if abs(value) >= 1:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _number_string(value: float | None) -> str:
    return "" if value is None else _format_number(value)


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", ".")
    match = _NUMERIC_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _is_non_english(value: str | None) -> bool:
    return bool(value and _NON_ENGLISH_RE.search(value))


def _key(value: str | None) -> str:
    text = (value or "").strip().lower().replace("μ", "µ")
    text = text.replace("umol", "µmol").replace("ug", "µg")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text
