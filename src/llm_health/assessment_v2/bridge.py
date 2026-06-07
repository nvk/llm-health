from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from llm_health.core.models import Observation
from llm_health.core.privacy import validate_profile_alias


@dataclass(frozen=True)
class V2ImportResult:
    profile_id: str
    imported_count: int
    latest_date: str | None
    source_ids: list[str]


def canonical_observations_csv(wiki_root: str | Path) -> Path:
    return Path(wiki_root).expanduser() / "output" / "data" / "lab-observations-long.csv"


def rows_from_wiki_csv(wiki_root: str | Path) -> list[dict[str, str]]:
    path = canonical_observations_csv(wiki_root)
    if not path.exists():
        raise FileNotFoundError(f"Missing de-identified v2 canonical observations CSV: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def latest_source_rows(rows: Iterable[dict[str, str]], profile_id: str) -> list[dict[str, str]]:
    profile = validate_profile_alias(profile_id)
    profile_rows = [row for row in rows if row.get("profile_id", "").strip().lower() == profile]
    dated = [row for row in profile_rows if row.get("observation_date")]
    if not dated:
        return []
    latest_date = max(row["observation_date"] for row in dated)
    latest_source_ids = {
        row.get("source_id", "") for row in dated if row.get("observation_date") == latest_date
    }
    return [row for row in dated if row.get("source_id", "") in latest_source_ids]


def observations_from_v2_rows(rows: Iterable[dict[str, str]]) -> list[Observation]:
    observations: list[Observation] = []
    for row in rows:
        profile = validate_profile_alias(row.get("profile_id", ""))
        numeric = _parse_float(row.get("numeric_value") or row.get("value_raw"))
        result_type = (row.get("result_type") or "").strip().lower()
        flag = row.get("flag_raw") or None
        if numeric is None and (
            "pending" in result_type or "pending" in (row.get("value_raw") or "").lower()
        ):
            flag = flag or "pending"
        kwargs = {
            "profile_id": profile,
            "marker": (row.get("analyte_en") or row.get("analyte_original") or "Unknown").strip(),
            "value": numeric,
            "unit": (row.get("ucum_unit") or row.get("unit_raw") or None),
            "category": (
                row.get("panel_en") or row.get("panel_original") or "uncategorized"
            ).strip(),
            "observed_on": (
                row.get("observation_date") or row.get("collection_date") or ""
            ).strip(),
            "flag": flag,
            "reference_range": _clean(row.get("reference_range_raw")),
            "comparator": _clean(row.get("comparator")),
            "specimen": _clean(row.get("specimen")),
            "interpretation": _clean(row.get("interpretation_en")),
            "source_id": (row.get("source_id") or "v2_canonical").strip(),
            "note": "Imported from de-identified v2 canonical observation row.",
        }
        observation_id = (row.get("observation_id") or "").strip()
        if observation_id:
            kwargs["observation_id"] = observation_id
        observations.append(Observation(**kwargs))
    return observations


def latest_observations_from_wiki(wiki_root: str | Path, profile_id: str) -> list[Observation]:
    rows = rows_from_wiki_csv(wiki_root)
    return observations_from_v2_rows(latest_source_rows(rows, profile_id))


def import_latest_for_profile(
    wiki_root: str | Path, profile_id: str
) -> tuple[V2ImportResult, list[Observation]]:
    observations = latest_observations_from_wiki(wiki_root, profile_id)
    latest_date = max((obs.observed_on for obs in observations if obs.observed_on), default=None)
    source_ids = sorted({obs.source_id for obs in observations})
    return (
        V2ImportResult(
            profile_id=validate_profile_alias(profile_id),
            imported_count=len(observations),
            latest_date=latest_date,
            source_ids=source_ids,
        ),
        observations,
    )


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip().replace(",", "")
    if not text:
        return None
    if text.startswith("<") or text.startswith(">"):
        text = text[1:].strip()
    try:
        return float(text)
    except ValueError:
        return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
