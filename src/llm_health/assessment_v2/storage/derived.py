"""Derived optimized tables for dashboard queries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DerivedTable:
    """Summary of a derived/optimized table."""

    table: str
    row_count: int


def build_derived_tables(con) -> list[DerivedTable]:
    """Create optimized rollup, lab-event, context-window, and QA tables."""

    statements = [
        _wearable_normalized_sql(),
        _wearable_weekly_sql(),
        _wearable_monthly_sql(),
        _lab_events_sql(),
        _context_windows_sql(),
        _qa_issues_sql(),
        _inference_events_sql(),
    ]
    for sql in statements:
        con.execute(sql)
    tables = [
        "wearable_normalized",
        "wearable_weekly",
        "wearable_monthly",
        "lab_events",
        "context_windows",
        "qa_issues",
        "inference_events",
    ]
    return [
        DerivedTable(
            table=table, row_count=int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        )
        for table in tables
    ]


def _wearable_normalized_sql() -> str:
    return """
CREATE OR REPLACE TABLE wearable_normalized AS
SELECT
  profile_id,
  family_role,
  TRY_CAST(date AS DATE) AS date,
  record_type,
  category,
  metric_en,
  unit,
  value_text,
  aggregation_preferred,
  TRY_CAST(value_sum AS DOUBLE) AS value_sum,
  TRY_CAST(value_avg AS DOUBLE) AS value_avg,
  TRY_CAST(value_min AS DOUBLE) AS value_min,
  TRY_CAST(value_max AS DOUBLE) AS value_max,
  TRY_CAST(value_last AS DOUBLE) AS value_last,
  TRY_CAST(duration_seconds AS DOUBLE) AS duration_seconds,
  TRY_CAST(count AS BIGINT) AS record_count,
  CASE
    WHEN aggregation_preferred = 'sum' THEN TRY_CAST(value_sum AS DOUBLE)
    WHEN TRY_CAST(value_avg AS DOUBLE) IS NOT NULL THEN TRY_CAST(value_avg AS DOUBLE)
    ELSE TRY_CAST(value_last AS DOUBLE)
  END AS chart_value
FROM wearable_daily
WHERE TRY_CAST(date AS DATE) IS NOT NULL
"""


def _wearable_weekly_sql() -> str:
    return """
CREATE OR REPLACE TABLE wearable_weekly AS
SELECT
  profile_id,
  family_role,
  date_trunc('week', date)::DATE AS period_start,
  max(date)::DATE AS period_end,
  record_type,
  category,
  metric_en,
  unit,
  aggregation_preferred,
  sum(value_sum) AS value_sum,
  avg(value_avg) AS value_avg,
  min(value_min) AS value_min,
  max(value_max) AS value_max,
  arg_max(value_last, date) AS value_last,
  sum(duration_seconds) AS duration_seconds,
  sum(record_count) AS record_count,
  count(*) AS days_with_data,
  CASE
    WHEN aggregation_preferred = 'sum' THEN sum(value_sum)
    WHEN avg(value_avg) IS NOT NULL THEN avg(value_avg)
    ELSE arg_max(value_last, date)
  END AS chart_value
FROM wearable_normalized
GROUP BY
  profile_id, family_role, date_trunc('week', date), record_type, category, metric_en, unit,
  aggregation_preferred
"""


def _wearable_monthly_sql() -> str:
    return """
CREATE OR REPLACE TABLE wearable_monthly AS
SELECT
  profile_id,
  family_role,
  date_trunc('month', date)::DATE AS period_start,
  max(date)::DATE AS period_end,
  record_type,
  category,
  metric_en,
  unit,
  aggregation_preferred,
  sum(value_sum) AS value_sum,
  avg(value_avg) AS value_avg,
  min(value_min) AS value_min,
  max(value_max) AS value_max,
  arg_max(value_last, date) AS value_last,
  sum(duration_seconds) AS duration_seconds,
  sum(record_count) AS record_count,
  count(*) AS days_with_data,
  CASE
    WHEN aggregation_preferred = 'sum' THEN sum(value_sum)
    WHEN avg(value_avg) IS NOT NULL THEN avg(value_avg)
    ELSE arg_max(value_last, date)
  END AS chart_value
FROM wearable_normalized
GROUP BY
  profile_id, family_role, date_trunc('month', date), record_type, category, metric_en, unit,
  aggregation_preferred
"""


def _lab_events_sql() -> str:
    return """
CREATE OR REPLACE TABLE lab_events AS
SELECT
  profile_id,
  family_role,
  TRY_CAST(observation_date AS DATE) AS event_date,
  source_id,
  any_value(source_title) AS source_title,
  count(*) AS observation_count,
  count_if(TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL) AS numeric_count,
  count_if(flag_raw IS NOT NULL AND trim(flag_raw) <> '') AS source_flag_count
FROM lab_observations
WHERE TRY_CAST(observation_date AS DATE) IS NOT NULL
GROUP BY profile_id, family_role, TRY_CAST(observation_date AS DATE), source_id
"""


def _context_windows_sql() -> str:
    return """
CREATE OR REPLACE TABLE context_windows AS
WITH metric_allowlist(record_type, context_metric) AS (
  VALUES
    ('HKQuantityTypeIdentifierStepCount', 'steps_avg_per_day'),
    ('HKQuantityTypeIdentifierDistanceWalkingRunning', 'distance_km_avg_per_day'),
    ('HKQuantityTypeIdentifierActiveEnergyBurned', 'active_kcal_avg_per_day'),
    ('HKQuantityTypeIdentifierFlightsClimbed', 'flights_avg_per_day'),
    ('HKQuantityTypeIdentifierWalkingSpeed', 'walking_speed_avg'),
    ('HKQuantityTypeIdentifierWalkingStepLength', 'walking_step_length_avg'),
    ('HKQuantityTypeIdentifierWalkingDoubleSupportPercentage', 'double_support_avg'),
    ('HKQuantityTypeIdentifierWalkingAsymmetryPercentage', 'walking_asymmetry_avg'),
    ('HKQuantityTypeIdentifierAppleWalkingSteadiness', 'walking_steadiness_avg'),
    ('HKQuantityTypeIdentifierBodyMass', 'apple_body_mass_avg')
),
windows(window_days) AS (VALUES (7), (30), (90)),
joined AS (
  SELECT
    e.profile_id,
    e.family_role,
    e.event_date,
    e.source_id,
    w.window_days,
    m.context_metric,
    d.record_type,
    d.metric_en,
    d.unit,
    d.aggregation_preferred,
    d.date,
    CASE
      WHEN d.aggregation_preferred = 'sum' THEN d.value_sum
      WHEN d.value_avg IS NOT NULL THEN d.value_avg
      ELSE d.value_last
    END AS context_value
  FROM lab_events e
  CROSS JOIN windows w
  JOIN metric_allowlist m ON true
  LEFT JOIN wearable_normalized d
    ON d.profile_id = e.profile_id
   AND d.record_type = m.record_type
   AND d.date BETWEEN e.event_date - (w.window_days - 1) * INTERVAL '1 day' AND e.event_date
)
SELECT
  profile_id,
  family_role,
  event_date,
  source_id,
  window_days,
  context_metric,
  any_value(record_type) AS record_type,
  any_value(metric_en) AS metric_en,
  any_value(unit) AS unit,
  avg(context_value) AS value_avg,
  min(context_value) AS value_min,
  max(context_value) AS value_max,
  count(context_value) AS days_with_data,
  max(date) AS latest_context_date,
  'DERIVED|WEARABLE_CONTEXT' AS tags
FROM joined
GROUP BY profile_id, family_role, event_date, source_id, window_days, context_metric
HAVING count(context_value) > 0
"""


def _qa_issues_sql() -> str:
    return """
CREATE OR REPLACE TABLE qa_issues AS
WITH bodymass_outliers AS (
  SELECT
    'apple_bodymass_' || strftime(date, '%Y%m%d') AS issue_id,
    'warning' AS severity,
    'wearable_daily' AS table_name,
    CAST(date AS VARCHAR) AS row_ref,
    metric_en AS metric,
    'BodyMass above 140 kg; quarantine until source/unit is validated.' AS message,
    'exclude_from_weight_overlay' AS action,
    'QA_ISSUE' AS tag
  FROM wearable_normalized
  WHERE record_type = 'HKQuantityTypeIdentifierBodyMass'
    AND coalesce(value_last, value_avg, value_sum) > 140
),
sleep_overlap AS (
  SELECT
    'apple_sleep_overlap_review' AS issue_id,
    'warning' AS severity,
    'wearable_daily' AS table_name,
    NULL AS row_ref,
    'Sleep analysis' AS metric,
    'Sleep rows need interval normalization before duration inference.' AS message,
    'normalize_sleep_intervals_before_inference' AS action,
    'QA_ISSUE' AS tag
  WHERE EXISTS (
    SELECT 1 FROM wearable_normalized WHERE record_type = 'HKCategoryTypeIdentifierSleepAnalysis'
  )
),
current_partial_day AS (
  SELECT
    'apple_export_latest_day_partial_' || strftime(max(date), '%Y%m%d') AS issue_id,
    'info' AS severity,
    'wearable_daily' AS table_name,
    CAST(max(date) AS VARCHAR) AS row_ref,
    'Apple Health export date' AS metric,
    'Latest Apple Health date may be partial; show daily-chart badge.' AS message,
    'show_partial_day_badge' AS action,
    'QA_ISSUE' AS tag
  FROM wearable_normalized
)
SELECT * FROM bodymass_outliers
UNION ALL SELECT * FROM sleep_overlap
UNION ALL SELECT * FROM current_partial_day
"""


def _inference_events_sql() -> str:
    return """
CREATE OR REPLACE TABLE inference_events AS
WITH latest_alt AS (
  SELECT
    profile_id,
    TRY_CAST(observation_date AS DATE) AS event_date,
    TRY_CAST(numeric_value AS DOUBLE) AS alt_value,
    unit_raw,
    source_id,
    flag_raw,
    row_number() OVER (
      PARTITION BY profile_id ORDER BY TRY_CAST(observation_date AS DATE) DESC, source_id DESC
    ) AS rn
  FROM lab_observations
  WHERE analyte_en = 'ALT' AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
),
alt_events AS (
  SELECT
    'latest_alt_review_' || profile_id AS event_id,
    'INFERENCE' AS tag,
    profile_id,
    'liver' AS subject_area,
    event_date,
    'Latest ALT is ' || CAST(round(alt_value, 2) AS VARCHAR) || ' ' || coalesce(unit_raw, '') ||
      '; review with liver/metabolic context and source reference range.' AS statement,
    'medium' AS confidence,
    'needs_review' AS review_status,
    'lab_observations:ALT:' || CAST(event_date AS VARCHAR) || ':' || source_id AS inputs,
    'Not diagnostic; interpret with clinician context.' AS caveats
  FROM latest_alt
  WHERE rn = 1 AND (coalesce(flag_raw, '') <> '' OR alt_value > 55)
),
wearable_context AS (
  SELECT
    'wearable_context_available_' || profile_id AS event_id,
    'WEARABLE_CONTEXT' AS tag,
    profile_id,
    'activity' AS subject_area,
    max(event_date) AS event_date,
    'Wearable context windows are available for lab-event review.' AS statement,
    'medium' AS confidence,
    'ready_for_review' AS review_status,
    'context_windows' AS inputs,
    'Coverage gaps exist; HR/sleep/workouts are historical.' AS caveats
  FROM context_windows
  GROUP BY profile_id
),
cara_gap AS (
  SELECT
    'cara_wearable_data_gap' AS event_id,
    'DATA_GAP' AS tag,
    'cara' AS profile_id,
    'wearables' AS subject_area,
    NULL::DATE AS event_date,
    'No Apple Health wearable dataset is currently assigned to Cara.' AS statement,
    'high' AS confidence,
    'open' AS review_status,
    'wearable_normalized' AS inputs,
    'Profile-exclusive filtering should keep Rod Apple data out of Cara views.' AS caveats
  WHERE NOT EXISTS (SELECT 1 FROM wearable_normalized WHERE profile_id = 'cara')
),
qa_context AS (
  SELECT
    'apple_bodymass_outliers_quarantined' AS event_id,
    'QA_ISSUE' AS tag,
    'rod' AS profile_id,
    'weight' AS subject_area,
    NULL::DATE AS event_date,
    'Apple BodyMass outliers are quarantined for weight overlays.' AS statement,
    'high' AS confidence,
    'needs_source_review' AS review_status,
    'qa_issues:apple_bodymass' AS inputs,
    'Manual weight anchor remains separate from quarantined Apple rows.' AS caveats
  WHERE EXISTS (SELECT 1 FROM qa_issues WHERE action = 'exclude_from_weight_overlay')
)
SELECT * FROM alt_events
UNION ALL SELECT * FROM wearable_context
UNION ALL SELECT * FROM cara_gap
UNION ALL SELECT * FROM qa_context
"""
