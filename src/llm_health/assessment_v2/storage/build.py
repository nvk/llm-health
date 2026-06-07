"""Build local Parquet/DuckDB tables from de-identified wiki outputs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm_health.assessment_v2.paths import ensure_dir
from llm_health.assessment_v2.storage.briefing import build_briefing_tables
from llm_health.assessment_v2.storage.derived import build_derived_tables


@dataclass(frozen=True)
class WikiTableSpec:
    """A de-identified wiki CSV that can become a local canonical table."""

    table: str
    relative_csv: str
    required: bool = True
    large_record_level: bool = False


WIKI_TABLES: tuple[WikiTableSpec, ...] = (
    WikiTableSpec("lab_observations", "output/data/lab-observations-long.csv"),
    WikiTableSpec("lab_reports", "output/data/lab-reports.csv"),
    WikiTableSpec("wearable_daily", "output/data/apple-health-daily-summary.csv"),
    WikiTableSpec("wearable_activity_summaries", "output/data/apple-health-activity-summaries.csv"),
    WikiTableSpec("wearable_workouts", "output/data/apple-health-workouts.csv"),
    WikiTableSpec("wearable_source_aliases", "output/data/apple-health-source-aliases.csv"),
    WikiTableSpec("wearable_characteristics", "output/data/apple-health-characteristics.csv"),
    WikiTableSpec(
        "wearable_records",
        "output/data/apple-health-records.csv",
        large_record_level=True,
    ),
)


@dataclass(frozen=True)
class BuiltTable:
    """Summary of a built local table."""

    table: str
    input_csv: str
    output_parquet: str
    row_count: int
    skipped: bool = False
    reason: str | None = None


def _import_duckdb():
    try:
        import duckdb  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("DuckDB is required. Install the project dependencies first.") from exc
    return duckdb


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _safe_source_query(
    spec: WikiTableSpec, input_literal: str, columns: set[str] | None = None
) -> str:
    """Return an import query with privacy-safe normalizations.

    The source CSVs are already de-identified, but package-generated artifacts should still avoid
    carrying absolute paths or raw-ish device/source labels forward.
    """

    csv_scan = f"read_csv_auto({input_literal}, all_varchar=true, union_by_name=true)"
    if spec.table in {"lab_observations", "lab_reports"}:
        # The canonical CSVs can preserve local audit aliases for wiki-internal use. The package
        # store/archive should not carry raw-source-looking filenames or provider labels forward.
        columns = columns or set()
        exclusions = [name for name in ("source_file_alias", "provider_alias") if name in columns]
        if exclusions:
            excluded = ", ".join(exclusions)
            imported = f"SELECT * EXCLUDE ({excluded}) FROM {csv_scan}"
        else:
            imported = f"SELECT * FROM {csv_scan}"
        replacements = [
            f"{_scrub_source_sql(name)} AS {name}"
            for name in ("source_title", "notes")
            if name in columns and name not in exclusions
        ]
        if not replacements:
            return imported
        return (
            "WITH imported AS ("
            f"{imported}"
            ") SELECT * REPLACE ("
            f"{', '.join(replacements)}"
            ") FROM imported"
        )
    if spec.table != "wearable_source_aliases":
        return f"SELECT * FROM {csv_scan}"

    # Keep the source alias table useful while removing brand/device-looking labels from the
    # durable v2 database/parquet copy.
    return (
        "SELECT * REPLACE ("
        "replace(replace(source_kind, 'iPhone', 'phone'), 'Apple Watch', 'watch') "
        "AS source_kind"
        f") FROM {csv_scan}"
    )


def _scrub_source_sql(column: str) -> str:
    # Remove raw-source-looking filenames from package-generated DuckDB/Parquet text fields while
    # preserving enough source context for grouping and audit notes.
    pattern = r"[^\s/\\;]+\.(pdf|xml|cda|xlsx?|csv)"
    return f"regexp_replace({column}, {_quote_literal(pattern)}, '[source-file]', 'gi')"


def _csv_columns(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            return {column.strip() for column in next(reader) if column.strip()}
        except StopIteration:
            return set()


def build_from_wiki(
    wiki_root: Path,
    data_dir: Path,
    duckdb_path: Path,
    *,
    include_record_level: bool = False,
) -> list[BuiltTable]:
    """Build Parquet tables and DuckDB views from existing de-identified wiki CSVs."""

    duckdb = _import_duckdb()
    wiki_root = wiki_root.expanduser().resolve()
    data_dir = ensure_dir(data_dir.expanduser())
    parquet_dir = ensure_dir(data_dir / "parquet")
    duckdb_path = duckdb_path.expanduser()
    ensure_dir(duckdb_path.parent)
    duckdb_path.unlink(missing_ok=True)

    built: list[BuiltTable] = []
    con = duckdb.connect(str(duckdb_path))
    try:
        for spec in WIKI_TABLES:
            input_csv = wiki_root / spec.relative_csv
            output_parquet = parquet_dir / f"{spec.table}.parquet"
            if spec.large_record_level and not include_record_level:
                built.append(
                    BuiltTable(
                        table=spec.table,
                        input_csv=spec.relative_csv,
                        output_parquet=f"parquet/{spec.table}.parquet",
                        row_count=0,
                        skipped=True,
                        reason="record-level Apple Health table skipped by default",
                    )
                )
                continue
            if not input_csv.exists():
                if spec.required:
                    raise FileNotFoundError(f"required wiki CSV not found: {input_csv}")
                built.append(
                    BuiltTable(
                        table=spec.table,
                        input_csv=spec.relative_csv,
                        output_parquet=f"parquet/{spec.table}.parquet",
                        row_count=0,
                        skipped=True,
                        reason="missing optional CSV",
                    )
                )
                continue

            # all_varchar preserves de-identified source text and avoids schema drift across labs.
            input_literal = _quote_literal(str(input_csv))
            output_literal = _quote_literal(str(output_parquet))
            temp_table = _quote_ident(f"__import_{spec.table}")
            con.execute(
                f"CREATE OR REPLACE TEMP TABLE {temp_table} AS "
                f"{_safe_source_query(spec, input_literal, _csv_columns(input_csv))}"
            )
            con.execute(f"COPY (SELECT * FROM {temp_table}) TO {output_literal} (FORMAT PARQUET)")
            row_count = con.execute(f"SELECT count(*) FROM {temp_table}").fetchone()[0]
            con.execute(
                f"CREATE OR REPLACE TABLE {_quote_ident(spec.table)} AS SELECT * FROM {temp_table}"
            )
            built.append(
                BuiltTable(
                    table=spec.table,
                    input_csv=spec.relative_csv,
                    output_parquet=f"parquet/{spec.table}.parquet",
                    row_count=int(row_count),
                )
            )

        derived = build_derived_tables(con)
        for table in derived:
            built.append(
                BuiltTable(
                    table=table.table,
                    input_csv="derived",
                    output_parquet="duckdb-table",
                    row_count=table.row_count,
                )
            )
        briefing = build_briefing_tables(con)
        for table in briefing:
            built.append(
                BuiltTable(
                    table=table.table,
                    input_csv="briefing",
                    output_parquet="duckdb-table",
                    row_count=table.row_count,
                )
            )
        _write_manifest(data_dir / "build-manifest.json", built, duckdb_path)
        return built
    finally:
        con.close()


def _write_manifest(path: Path, built: list[BuiltTable], duckdb_path: Path) -> None:
    try:
        safe_duckdb_path = str(duckdb_path.resolve().relative_to(path.parent.resolve()))
    except ValueError:
        safe_duckdb_path = duckdb_path.name
    payload: dict[str, Any] = {
        "duckdb_path": safe_duckdb_path,
        "tables": [table.__dict__ for table in built],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
