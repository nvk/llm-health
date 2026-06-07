"""Build deterministic health briefing tables."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BriefingTable:
    table: str
    row_count: int


def build_briefing_tables(con) -> list[BriefingTable]:
    statements = [
        _domain_status_sql(),
        _review_queue_sql(),
        _what_changed_sql(),
    ]
    for sql in statements:
        con.execute(sql)
    tables = ["domain_status", "review_queue", "what_changed"]
    return [
        BriefingTable(
            table=table, row_count=int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        )
        for table in tables
    ]


def _domain_status_sql() -> str:
    return """
CREATE OR REPLACE TABLE domain_status AS
WITH latest AS (
  SELECT
    profile_id,
    lower(analyte_en) AS analyte,
    analyte_en,
    TRY_CAST(observation_date AS DATE) AS date,
    TRY_CAST(numeric_value AS DOUBLE) AS value,
    unit_raw,
    flag_raw,
    reference_range_raw,
    source_id,
    row_number() OVER (
      PARTITION BY profile_id, lower(analyte_en)
      ORDER BY TRY_CAST(observation_date AS DATE) DESC, source_id DESC
    ) AS rn
  FROM lab_observations
  WHERE TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
),
latest_pivot AS (
  SELECT * FROM latest WHERE rn = 1
),
latest_weight AS (
  SELECT
    profile_id,
    TRY_CAST(observation_date AS DATE) AS date,
    CASE
      WHEN lower(coalesce(unit_raw, '')) IN ('lb', 'lbs', 'pound', 'pounds')
        THEN TRY_CAST(numeric_value AS DOUBLE) * 0.45359237
      ELSE TRY_CAST(numeric_value AS DOUBLE)
    END AS weight_kg,
    row_number() OVER (
      PARTITION BY profile_id
      ORDER BY TRY_CAST(observation_date AS DATE) DESC, source_id DESC
    ) AS rn
  FROM lab_observations
  WHERE lower(analyte_en) = 'weight'
    AND TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
),
rod_domains AS (
  SELECT
    'rod' AS profile_id,
    'liver_bilirubin' AS domain_id,
    'Liver / bilirubin / Gilbert context' AS domain,
    'needs_review' AS status,
    'high' AS priority,
    'INFERENCE' AS primary_tag,
    'ALT is flagged; review bilirubin separately as indirect/Gilbert-compatible.' AS summary,
    'ALT/AST/bilirubin rows, Rod Gilbert context, current weight/activity context.' AS evidence,
    'Clinician review; do not use Gilbert context to explain ALT elevation.' AS data_needed,
    1 AS sort_order
  WHERE EXISTS (
    SELECT 1 FROM latest_pivot
    WHERE profile_id = 'rod' AND analyte = 'alt' AND (coalesce(flag_raw, '') <> '' OR value > 55)
  )
  UNION ALL
  SELECT
    'rod', 'lipids', 'Lipids / ASCVD context', 'needs_review', 'high', 'OBSERVED',
    'Persistent LDL/non-HDL/ApoB burden remains a longitudinal review item.',
    'Repeated LDL/non-HDL/ApoB rows are source-flagged or above common risk-enhancing anchors.',
    'Clinician ASCVD risk inputs: BP treatment, smoking, diabetes, family history, Lp(a).',
    2
  UNION ALL
  SELECT
    'rod', 'weight_activity', 'Weight / activity / metabolic context', 'monitor', 'medium',
    'WEARABLE_CONTEXT',
    'Current weight and recent Apple activity context should travel with liver/lipid review.',
    coalesce(
      (
        SELECT 'Latest de-identified weight ' || CAST(round(weight_kg, 1) AS VARCHAR) ||
          ' kg on ' || CAST(date AS VARCHAR) ||
          ' plus Apple 30/90/365-day activity summaries.'
        FROM latest_weight WHERE profile_id = 'rod' AND rn = 1
      ),
      'Weight context plus Apple 30/90/365-day activity summaries.'
    ),
    'Validate Apple BodyMass outliers before using Apple weight stream.',
    3
  UNION ALL
  SELECT
    'rod', 'heavy_metals', 'Heavy metals', 'needs_followup', 'medium', 'DATA_GAP',
    'Lead history improved, but mercury follow-up/pending status remains a review item.',
    'Historical lead/mercury lab rows and pending/flagged source rows.',
    'Confirm latest mercury result, exposure/diet history, and clinician guidance.',
    4
  UNION ALL
  SELECT
    'rod', 'kidney_urate', 'Kidney / urate', 'monitor', 'medium', 'OBSERVED',
    'Kidney markers look comparatively stable, while urate has been a recurring context item.',
    'eGFR/ACR/creatinine and urate rows.',
    'Interpret urate with symptoms, stones/gout history, diet, renal context.',
    5
  UNION ALL
  SELECT
    'rod', 'glycemia', 'Glycemia', 'stable', 'low', 'OBSERVED',
    'A1c/glucose history is comparatively stable in the extracted data.',
    'A1c and glucose rows.',
    'Continue trending; interpret insulin/HOMA only with fasting context.',
    6
),
cara_domains AS (
  SELECT
    'cara' AS profile_id,
    'cbc_anemia' AS domain_id,
    'CBC / anemia' AS domain,
    'improved_monitor' AS status,
    'high' AS priority,
    'OBSERVED' AS primary_tag,
    '2025 significant anemia appears resolved by 2026, but etiology is not inferable here.',
    'Hemoglobin rose from 8.9 g/dL in 2025 to 14.8 g/dL in 2026; RDW remains context.',
    'Postpartum/lactation timing, iron/ferritin/B12/folate/retic context if clinically needed.',
    1 AS sort_order
  UNION ALL
  SELECT
    'cara', 'hormones', 'Hormones / postpartum context', 'context_needed', 'medium', 'CONTEXT',
    'Hormone rows need cycle/postpartum/lactation context before interpretation.',
    'Estradiol/prolactin and related report rows.',
    'Cycle day, lactation status, symptoms, medications/supplements.',
    2
  UNION ALL
  SELECT
    'cara', 'wearables', 'Wearables', 'data_gap', 'medium', 'DATA_GAP',
    'No Apple Health wearable dataset is assigned to Cara.',
    'Profile-exclusive Apple rows are Rod-only in this build.',
    'Ingest Cara wearable export if desired.',
    3
  UNION ALL
  SELECT
    'cara', 'lipids_metals_kidney', 'Lipids / metals / kidney context', 'data_gap', 'medium',
    'DATA_GAP',
    'Cara has limited longitudinal data for lipids, metals, urinalysis, and kidney albuminuria.',
    'Current extracted reports do not provide a long timeline for these domains.',
    'Add future labs or historical records if available.',
    4
)
SELECT * FROM rod_domains
UNION ALL SELECT * FROM cara_domains
"""


def _review_queue_sql() -> str:
    return """
CREATE OR REPLACE TABLE review_queue AS
SELECT
  profile_id,
  domain_id,
  domain,
  status,
  priority,
  primary_tag AS tag,
  summary AS review_item,
  evidence,
  data_needed,
  sort_order
FROM domain_status
WHERE status NOT IN ('stable')
ORDER BY
  profile_id,
  CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
  sort_order
"""


def _what_changed_sql() -> str:
    return """
CREATE OR REPLACE TABLE what_changed AS
WITH ranked AS (
  SELECT
    profile_id,
    analyte_en,
    unit_raw,
    TRY_CAST(observation_date AS DATE) AS date,
    TRY_CAST(numeric_value AS DOUBLE) AS value,
    flag_raw,
    row_number() OVER (
      PARTITION BY profile_id, analyte_en, unit_raw
      ORDER BY TRY_CAST(observation_date AS DATE) DESC, source_id DESC
    ) AS rn
  FROM lab_observations
  WHERE TRY_CAST(numeric_value AS DOUBLE) IS NOT NULL
),
pairs AS (
  SELECT
    latest.profile_id,
    latest.analyte_en,
    latest.unit_raw,
    latest.date AS latest_date,
    latest.value AS latest_value,
    prev.date AS previous_date,
    prev.value AS previous_value,
    latest.flag_raw AS latest_flag,
    prev.flag_raw AS previous_flag,
    latest.value - prev.value AS delta
  FROM ranked latest
  LEFT JOIN ranked prev
    ON latest.profile_id = prev.profile_id
   AND latest.analyte_en = prev.analyte_en
   AND coalesce(latest.unit_raw, '') = coalesce(prev.unit_raw, '')
   AND prev.rn = 2
  WHERE latest.rn = 1 AND prev.value IS NOT NULL
),
lab_changes AS (
  SELECT
    profile_id,
    CASE
      WHEN coalesce(latest_flag, '') <> '' AND coalesce(previous_flag, '') = '' THEN 'new_flag'
      WHEN coalesce(latest_flag, '') = '' AND coalesce(previous_flag, '') <> '' THEN 'resolved_flag'
      WHEN abs(delta) < 0.000001 THEN 'unchanged'
      WHEN delta > 0 THEN 'increased'
      ELSE 'decreased'
    END AS change_type,
    analyte_en || ': ' || CAST(round(previous_value, 3) AS VARCHAR) || ' → ' ||
      CAST(round(latest_value, 3) AS VARCHAR) || ' ' || coalesce(unit_raw, '') AS statement,
    latest_date,
    abs(delta) AS magnitude
  FROM pairs
  WHERE analyte_en IN ('ALT','AST','Total bilirubin','LDL Cholesterol','Non-HDL Cholesterol',
                       'ApoB','Hemoglobin','Ferritin','Uric Acid','Mercury','Lead','A1c')
)
SELECT * FROM lab_changes
WHERE change_type <> 'unchanged'
ORDER BY profile_id, latest_date DESC, magnitude DESC
"""
