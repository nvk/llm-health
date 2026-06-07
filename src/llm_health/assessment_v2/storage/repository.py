"""Query layer for the Panel app."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd

Rollup = Literal["daily", "weekly", "monthly"]


@dataclass(frozen=True)
class DateFilter:
    label: str
    start: date | None
    end: date | None


class HealthRepository:
    """Small DuckDB-backed query facade for dashboard components."""

    def __init__(self, duckdb_path: Path):
        self.duckdb_path = duckdb_path

    @property
    def available(self) -> bool:
        return self.duckdb_path.exists()

    def _connect(self):
        import duckdb

        if not self.available:
            raise FileNotFoundError(f"DuckDB database not found: {self.duckdb_path}")
        return duckdb.connect(str(self.duckdb_path), read_only=True)

    def table_counts(self) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame(columns=["table", "rows"])
        with self._connect() as con:
            tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
            rows = []
            for table in tables:
                rows.append(
                    {
                        "table": table,
                        "rows": con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0],
                    }
                )
        return pd.DataFrame(rows).sort_values("table")

    def profile_summary(self, profile: str) -> dict[str, object]:
        if not self.available:
            return {"profile": profile, "available": False}
        with self._connect() as con:
            lab = con.execute(
                """
                SELECT count(*) AS rows, min(TRY_CAST(observation_date AS DATE)),
                       max(TRY_CAST(observation_date AS DATE))
                FROM lab_observations WHERE profile_id = ?
                """,
                [profile],
            ).fetchone()
            wearable = con.execute(
                """
                SELECT count(*) AS rows, min(date), max(date)
                FROM wearable_normalized WHERE profile_id = ?
                """,
                [profile],
            ).fetchone()
            labs_latest = con.execute(
                """
                SELECT event_date, sum(observation_count)
                FROM lab_events WHERE profile_id = ?
                GROUP BY event_date ORDER BY event_date DESC LIMIT 1
                """,
                [profile],
            ).fetchone()
            qa = con.execute("SELECT count(*) FROM qa_issues").fetchone()[0]
        return {
            "profile": profile,
            "available": True,
            "lab_rows": int(lab[0] or 0),
            "lab_start": lab[1],
            "lab_end": lab[2],
            "wearable_rows": int(wearable[0] or 0),
            "wearable_start": wearable[1],
            "wearable_end": wearable[2],
            "latest_lab_date": labs_latest[0] if labs_latest else None,
            "latest_lab_observations": int(labs_latest[1]) if labs_latest else 0,
            "qa_issues": int(qa or 0),
        }

    def lab_categories(self, profile: str | None = None) -> list[str]:
        if not self.available:
            return []
        where = "WHERE TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL"
        params: list[object] = []
        if profile:
            where += " AND profile_id = ?"
            params.append(profile)
        with self._connect() as con:
            rows = con.execute(
                f"""
                WITH categories AS (
                  SELECT
                    coalesce(nullif(panel_en, ''), 'Other') AS category,
                    lower(coalesce(nullif(panel_en, ''), 'Other')) AS category_key,
                    count(*) AS observation_count
                  FROM lab_observations {where}
                  GROUP BY 1, 2
                ),
                ranked AS (
                  SELECT *, row_number() OVER (
                    PARTITION BY category_key
                    ORDER BY observation_count DESC, category
                  ) AS rn
                  FROM categories
                )
                SELECT category
                FROM ranked
                WHERE rn = 1
                ORDER BY lower(category)
                """,
                params,
            ).fetchall()
        return [row[0] for row in rows]

    def lab_metrics(self, profile: str | None = None) -> list[str]:
        if not self.available:
            return []
        where = "WHERE TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL"
        params: list[object] = []
        if profile:
            where += " AND profile_id = ?"
            params.append(profile)
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT DISTINCT analyte_en
                FROM lab_observations {where}
                ORDER BY analyte_en
                """,
                params,
            ).fetchall()
        return [row[0] for row in rows if row[0]]

    def lab_metrics_for_category(self, profile: str, category: str | None) -> list[str]:
        if not self.available:
            return []
        params: list[object] = [profile]
        category_clause = _category_clause(category, params)
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT DISTINCT analyte_en
                FROM lab_observations
                WHERE profile_id = ?
                  AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
                  {category_clause}
                ORDER BY analyte_en
                """,
                params,
            ).fetchall()
        return [row[0] for row in rows if row[0]]

    def lab_context_metrics(self, profile: str) -> list[str]:
        """Return cross-domain context series available from de-identified vitals."""

        if not self.available:
            return []
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT DISTINCT
                  CASE
                    WHEN lower(analyte_en) = 'weight' THEN 'Weight (kg)'
                    WHEN lower(analyte_en) = 'bmi' THEN 'BMI'
                    WHEN lower(analyte_en) = 'waist circumference'
                      THEN 'Waist circumference (cm)'
                    WHEN lower(analyte_en) IN ('heart rate', 'pulse')
                      THEN 'Heart rate (bpm)'
                  END AS metric
                FROM lab_observations
                WHERE profile_id = ?
                  AND coalesce(nullif(panel_en, ''), 'Other') = 'Vitals'
                  AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
                ORDER BY metric
                """,
                [profile],
            ).fetchall()
        preferred_order = [
            "Weight (kg)",
            "BMI",
            "Waist circumference (cm)",
            "Heart rate (bpm)",
        ]
        available = {row[0] for row in rows if row[0]}
        return [metric for metric in preferred_order if metric in available]

    def lab_context_series(
        self, profile: str, metrics: list[str], window: DateFilter
    ) -> pd.DataFrame:
        """Return vitals/context series in the same schema as lab timelines."""

        if not self.available or not metrics:
            return pd.DataFrame()
        placeholders = ", ".join(["?"] * len(metrics))
        params: list[object] = [profile]
        date_clause = _date_clause("TRY_CAST(observation_date AS DATE)", window, params)
        params.extend(metrics)
        with self._connect() as con:
            return con.execute(
                f"""
                WITH context_rows AS (
                  SELECT
                    TRY_CAST(observation_date AS DATE) AS date,
                    CASE
                      WHEN lower(analyte_en) = 'weight' THEN 'Weight (kg)'
                      WHEN lower(analyte_en) = 'bmi' THEN 'BMI'
                      WHEN lower(analyte_en) = 'waist circumference'
                        THEN 'Waist circumference (cm)'
                      WHEN lower(analyte_en) IN ('heart rate', 'pulse')
                        THEN 'Heart rate (bpm)'
                    END AS metric,
                    CASE
                      WHEN lower(analyte_en) = 'weight' THEN 'kg'
                      WHEN lower(analyte_en) = 'waist circumference' THEN 'cm'
                      WHEN lower(analyte_en) IN ('heart rate', 'pulse') THEN 'bpm'
                      ELSE unit_raw
                    END AS unit,
                    CASE
                      WHEN lower(analyte_en) = 'weight'
                        AND lower(coalesce(unit_raw, '')) IN ('lb', 'lbs', 'pound', 'pounds')
                        THEN TRY_CAST(numeric_value AS DOUBLE) * 0.45359237
                      WHEN lower(analyte_en) = 'waist circumference'
                        AND lower(coalesce(unit_raw, '')) IN ('in', 'inch', 'inches')
                        THEN TRY_CAST(numeric_value AS DOUBLE) * 2.54
                      ELSE TRY_CAST(numeric_value AS DOUBLE)
                    END AS value,
                    source_id,
                    flag_raw,
                    reference_range_raw
                  FROM lab_observations
                  WHERE profile_id = ?
                    AND coalesce(nullif(panel_en, ''), 'Other') = 'Vitals'
                    AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
                    {date_clause}
                )
                SELECT date, metric, unit, value, source_id, flag_raw, reference_range_raw,
                       'CONTEXT' AS category,
                       metric || ' · CONTEXT' AS series
                FROM context_rows
                WHERE metric IN ({placeholders})
                  AND value IS NOT NULL
                ORDER BY date, metric, source_id
                """,
                params,
            ).df()

    def wearable_metrics(self, profile: str | None = None) -> list[str]:
        if not self.available:
            return []
        where = "WHERE chart_value IS NOT NULL"
        params: list[object] = []
        if profile:
            where += " AND profile_id = ?"
            params.append(profile)
        with self._connect() as con:
            rows = con.execute(
                f"""
                SELECT DISTINCT metric_en
                FROM wearable_normalized {where}
                ORDER BY metric_en
                """,
                params,
            ).fetchall()
        return [row[0] for row in rows if row[0]]

    def coverage(self, profile: str) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT category, metric_en, unit, min(date) AS first_date, max(date) AS latest_date,
                       count(*) AS days, sum(record_count) AS source_records
                FROM wearable_normalized
                WHERE profile_id = ?
                GROUP BY category, metric_en, unit
                ORDER BY category, metric_en
                """,
                [profile],
            ).df()

    def lab_series_multi(
        self, profile: str, metrics: list[str], window: DateFilter
    ) -> pd.DataFrame:
        if not self.available or not metrics:
            return pd.DataFrame()
        placeholders = ", ".join(["?"] * len(metrics))
        params: list[object] = [profile, *metrics]
        date_clause = _date_clause("TRY_CAST(observation_date AS DATE)", window, params)
        with self._connect() as con:
            return con.execute(
                f"""
                SELECT TRY_CAST(observation_date AS DATE) AS date, analyte_en AS metric,
                       unit_raw AS unit, TRY_CAST(numeric_value AS DOUBLE) AS value,
                       source_id, flag_raw, reference_range_raw,
                       coalesce(nullif(panel_en, ''), 'Other') AS category,
                       analyte_en || CASE WHEN coalesce(unit_raw, '') <> ''
                         THEN ' (' || unit_raw || ')' ELSE '' END AS series
                FROM lab_observations
                WHERE profile_id = ? AND analyte_en IN ({placeholders})
                  AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
                  {date_clause}
                ORDER BY date, metric, source_id
                """,
                params,
            ).df()

    def lab_series_for_category(
        self, profile: str, category: str | None, window: DateFilter
    ) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        params: list[object] = [profile]
        category_clause = _category_clause(category, params)
        date_clause = _date_clause("TRY_CAST(observation_date AS DATE)", window, params)
        with self._connect() as con:
            return con.execute(
                f"""
                SELECT TRY_CAST(observation_date AS DATE) AS date, analyte_en AS metric,
                       unit_raw AS unit, TRY_CAST(numeric_value AS DOUBLE) AS value,
                       source_id, flag_raw, reference_range_raw,
                       coalesce(nullif(panel_en, ''), 'Other') AS category,
                       analyte_en || CASE WHEN coalesce(unit_raw, '') <> ''
                         THEN ' (' || unit_raw || ')' ELSE '' END AS series
                FROM lab_observations
                WHERE profile_id = ?
                  AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
                  {category_clause}
                  {date_clause}
                ORDER BY lower(category), metric, date, source_id
                """,
                params,
            ).df()

    def lab_series(self, profile: str, metric: str, window: DateFilter) -> pd.DataFrame:
        if not self.available or not metric:
            return pd.DataFrame()
        params: list[object] = [profile, metric]
        date_clause = _date_clause("TRY_CAST(observation_date AS DATE)", window, params)
        with self._connect() as con:
            return con.execute(
                f"""
                SELECT TRY_CAST(observation_date AS DATE) AS date, analyte_en, unit_raw AS unit,
                       TRY_CAST(numeric_value AS DOUBLE) AS value, source_id, flag_raw,
                       reference_range_raw
                FROM lab_observations
                WHERE profile_id = ? AND analyte_en = ?
                  AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
                  {date_clause}
                ORDER BY date, source_id
                """,
                params,
            ).df()

    def lab_category_recent(
        self, profile: str, category: str | None, limit: int = 500
    ) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        params: list[object] = [profile]
        category_clause = _category_clause(category, params)
        params.append(limit)
        with self._connect() as con:
            return con.execute(
                f"""
                SELECT TRY_CAST(observation_date AS DATE) AS date, analyte_en, unit_raw AS unit,
                       TRY_CAST(numeric_value AS DOUBLE) AS value, flag_raw, source_id
                FROM lab_observations
                WHERE profile_id = ?
                  AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
                  {category_clause}
                ORDER BY date DESC, analyte_en
                LIMIT ?
                """,
                params,
            ).df()

    def wearable_series_multi(
        self, profile: str, metrics: list[str], rollup: Rollup, window: DateFilter
    ) -> pd.DataFrame:
        if not self.available or not metrics:
            return pd.DataFrame()
        table, date_col = {
            "daily": ("wearable_normalized", "date"),
            "weekly": ("wearable_weekly", "period_start"),
            "monthly": ("wearable_monthly", "period_start"),
        }[rollup]
        placeholders = ", ".join(["?"] * len(metrics))
        params: list[object] = [profile, *metrics]
        date_clause = _date_clause(date_col, window, params)
        with self._connect() as con:
            return con.execute(
                f"""
                SELECT {date_col} AS date, metric_en AS metric, unit, chart_value AS value,
                       record_count, aggregation_preferred,
                       metric_en || CASE WHEN coalesce(unit, '') <> ''
                         THEN ' (' || unit || ')' ELSE '' END AS series
                FROM {table}
                WHERE profile_id = ? AND metric_en IN ({placeholders})
                  AND chart_value IS NOT NULL
                  {date_clause}
                ORDER BY {date_col}, metric_en
                """,
                params,
            ).df()

    def wearable_series(
        self, profile: str, metric: str, rollup: Rollup, window: DateFilter
    ) -> pd.DataFrame:
        if not self.available or not metric:
            return pd.DataFrame()
        table, date_col = {
            "daily": ("wearable_normalized", "date"),
            "weekly": ("wearable_weekly", "period_start"),
            "monthly": ("wearable_monthly", "period_start"),
        }[rollup]
        params: list[object] = [profile, metric]
        date_clause = _date_clause(date_col, window, params)
        with self._connect() as con:
            return con.execute(
                f"""
                SELECT {date_col} AS date, metric_en, unit, chart_value AS value,
                       record_count, aggregation_preferred
                FROM {table}
                WHERE profile_id = ? AND metric_en = ? AND chart_value IS NOT NULL
                  {date_clause}
                ORDER BY {date_col}
                """,
                params,
            ).df()

    def context_windows(self, profile: str, limit: int = 300) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT event_date, source_id, window_days, context_metric, unit,
                       round(value_avg, 3) AS value_avg, days_with_data, latest_context_date, tags
                FROM context_windows
                WHERE profile_id = ?
                ORDER BY event_date DESC, window_days, context_metric
                LIMIT ?
                """,
                [profile, limit],
            ).df()

    def domain_status(self, profile: str) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT domain, status, priority, primary_tag, summary, evidence, data_needed
                FROM domain_status
                WHERE profile_id = ?
                ORDER BY sort_order
                """,
                [profile],
            ).df()

    def review_queue(self, profile: str) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT domain, status, priority, tag, review_item, evidence, data_needed
                FROM review_queue
                WHERE profile_id = ?
                ORDER BY sort_order
                """,
                [profile],
            ).df()

    def what_changed(self, profile: str, limit: int = 20) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT change_type, statement, latest_date
                FROM what_changed
                WHERE profile_id = ?
                ORDER BY latest_date DESC, statement
                LIMIT ?
                """,
                [profile, limit],
            ).df()

    def latest_lab_flags(self, profile: str, limit: int = 12) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT TRY_CAST(observation_date AS DATE) AS date, analyte_en, panel_en,
                       TRY_CAST(numeric_value AS DOUBLE) AS value, unit_raw AS unit,
                       flag_raw, reference_range_raw, source_id
                FROM lab_observations
                WHERE profile_id = ?
                  AND flag_raw IS NOT NULL AND trim(flag_raw) <> ''
                ORDER BY TRY_CAST(observation_date AS DATE) DESC, analyte_en
                LIMIT ?
                """,
                [profile, limit],
            ).df()

    def activity_snapshot(self, profile: str) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                WITH latest AS (
                  SELECT max(date) AS latest_date
                  FROM wearable_normalized
                  WHERE profile_id = ?
                ),
                metrics(record_type, label, unit) AS (
                  VALUES
                    ('HKQuantityTypeIdentifierStepCount', 'Steps/day', 'count'),
                    ('HKQuantityTypeIdentifierDistanceWalkingRunning', 'Distance/day', 'km'),
                    ('HKQuantityTypeIdentifierActiveEnergyBurned', 'Active kcal/day', 'Cal')
                ),
                windows(window_days) AS (VALUES (30), (90), (365))
                SELECT
                  m.label,
                  w.window_days,
                  m.unit,
                  round(avg(d.value_sum), 2) AS avg_per_day,
                  count(d.value_sum) AS days_with_data,
                  max(d.date) AS latest_date
                FROM metrics m
                CROSS JOIN windows w
                CROSS JOIN latest l
                LEFT JOIN wearable_normalized d
                  ON d.profile_id = ?
                 AND d.record_type = m.record_type
                 AND d.date BETWEEN l.latest_date - (w.window_days - 1) * INTERVAL '1 day'
                                AND l.latest_date
                GROUP BY m.label, w.window_days, m.unit
                ORDER BY m.label, w.window_days
                """,
                [profile, profile],
            ).df()

    def latest_lab_events(self, profile: str, limit: int = 8) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT event_date, source_id, observation_count, numeric_count, source_flag_count
                FROM lab_events
                WHERE profile_id = ?
                ORDER BY event_date DESC, source_id
                LIMIT ?
                """,
                [profile, limit],
            ).df()

    def inference_events(self, profile: str) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT tag, subject_area, event_date, statement, confidence, review_status,
                       inputs, caveats
                FROM inference_events
                WHERE profile_id = ?
                ORDER BY
                  CASE tag
                    WHEN 'QA_ISSUE' THEN 0
                    WHEN 'INFERENCE' THEN 1
                    WHEN 'WEARABLE_CONTEXT' THEN 2
                    WHEN 'DATA_GAP' THEN 3
                    ELSE 4
                  END,
                  event_date DESC NULLS LAST
                """,
                [profile],
            ).df()

    def qa_issues(self) -> pd.DataFrame:
        if not self.available:
            return pd.DataFrame()
        with self._connect() as con:
            return con.execute(
                """
                SELECT severity, table_name, row_ref, metric, message, action, tag
                FROM qa_issues
                ORDER BY severity DESC, table_name, metric, row_ref
                """
            ).df()

    def latest_window(self, profile: str) -> DateFilter:
        if not self.available:
            return DateFilter("All", None, None)
        with self._connect() as con:
            row = con.execute(
                """
                SELECT max(d) FROM (
                  SELECT max(TRY_CAST(observation_date AS DATE)) AS d
                  FROM lab_observations WHERE profile_id = ?
                  UNION ALL
                  SELECT max(date) AS d FROM wearable_normalized WHERE profile_id = ?
                )
                """,
                [profile, profile],
            ).fetchone()
        return DateFilter("All", None, row[0] if row else None)


def make_date_filter(label: str, latest: date | None) -> DateFilter:
    if label == "All" or latest is None:
        return DateFilter(label, None, latest)
    if label == "30d":
        return DateFilter(label, latest - timedelta(days=29), latest)
    if label == "90d":
        return DateFilter(label, latest - timedelta(days=89), latest)
    if label == "18mo":
        return DateFilter(label, latest - timedelta(days=548), latest)
    if label == "YTD":
        return DateFilter(label, date(latest.year, 1, 1), latest)
    return DateFilter(label, None, latest)


def _date_clause(column: str, window: DateFilter, params: list[object]) -> str:
    clause = ""
    if window.start is not None:
        clause += f" AND {column} >= ?"
        params.append(window.start)
    if window.end is not None:
        clause += f" AND {column} <= ?"
        params.append(window.end)
    return clause


def _category_clause(category: str | None, params: list[object]) -> str:
    if not category:
        return ""
    params.append(category)
    return " AND lower(coalesce(nullif(panel_en, ''), 'Other')) = lower(?)"
