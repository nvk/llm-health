from __future__ import annotations

from pathlib import Path

import pytest

from llm_health.assessment_v2.storage.build import build_from_wiki


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_v2_storage_build_scrubs_source_file_and_provider_aliases(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    wiki = tmp_path / "wiki"
    data = tmp_path / "data"
    out = wiki / "output" / "data"

    _write(
        out / "lab-observations-long.csv",
        "observation_id,profile_id,family_role,observation_date,source_id,source_title,"
        "source_file_alias,provider_alias,analyte_en,numeric_value,unit_raw,flag_raw,"
        "reference_range_raw\n"
        "obs1,rod,father,2026-06-05,src1,Deidentified source,raw-file.pdf,"
        "private provider,ALT,61,U/L,high,0-55\n",
    )
    _write(
        out / "lab-reports.csv",
        "source_id,profile_id,family_role,provider_alias,source_title,collection_date,"
        "report_date,language,status,source_file_alias,notes\n"
        "src1,rod,father,private provider,Deidentified source,2026-06-05,2026-06-05,"
        "en,final,raw-report.pdf,fixture\n",
    )
    _write(
        out / "apple-health-daily-summary.csv",
        "profile_id,family_role,date,record_type,category,metric_en,unit,value_text,"
        "aggregation_preferred,value_sum,value_avg,value_min,value_max,value_last,"
        "duration_seconds,count\n"
        "rod,father,2026-06-05,HKQuantityTypeIdentifierStepCount,activity,Step count,"
        "count,,sum,1000,,,,,0,1\n",
    )
    _write(
        out / "apple-health-activity-summaries.csv",
        "profile_id,family_role,date,active_energy_burned,active_energy_burned_goal,"
        "active_energy_burned_unit,apple_move_time,apple_move_time_goal,"
        "apple_exercise_time,apple_exercise_time_goal,apple_exercise_time_unit,"
        "apple_stand_hours,apple_stand_hours_goal,apple_stand_hours_unit\n"
        "rod,father,2026-06-05,100,500,kcal,0,0,10,30,min,8,12,h\n",
    )
    _write(
        out / "apple-health-workouts.csv",
        "apple_health_workout_id,profile_id,family_role,workout_activity_type,"
        "workout_activity_en,start_datetime,end_datetime,creation_datetime,duration,"
        "duration_unit,total_distance,total_distance_unit,total_energy_burned,"
        "total_energy_burned_unit,source_alias,source_version,device_alias,device_model,"
        "device_hardware,device_software\n"
        "w1,rod,father,HKWorkoutActivityTypeWalking,Walking,2026-06-05,2026-06-05,"
        "2026-06-05,1200,s,1,km,100,kcal,ah_source_001,1,device_alias,,,\n",
    )
    _write(
        out / "apple-health-source-aliases.csv",
        "source_alias,source_name_sha256,source_kind,record_count,workout_count,first_seen,"
        "last_seen,type_count,top_types\n"
        "ah_source_001,abc,Apple Watch,1,1,2026-06-05,2026-06-05,1,steps\n",
    )
    _write(
        out / "apple-health-characteristics.csv",
        "profile_id,family_role,characteristic,value_deidentified,notes\n"
        "rod,father,birth_year,1983,year precision only\n",
    )

    build_from_wiki(wiki, data, data / "health.duckdb")

    con = duckdb.connect(str(data / "health.duckdb"), read_only=True)
    try:
        lab_observation_cols = {row[0] for row in con.sql("describe lab_observations").fetchall()}
        lab_report_cols = {row[0] for row in con.sql("describe lab_reports").fetchall()}
    finally:
        con.close()

    assert "source_file_alias" not in lab_observation_cols
    assert "provider_alias" not in lab_observation_cols
    assert "source_file_alias" not in lab_report_cols
    assert "provider_alias" not in lab_report_cols
    observation_bytes = (data / "parquet" / "lab_observations.parquet").read_bytes()
    report_bytes = (data / "parquet" / "lab_reports.parquet").read_bytes()
    duckdb_bytes = (data / "health.duckdb").read_bytes()
    for payload in [observation_bytes, report_bytes, duckdb_bytes]:
        assert b"raw-file.pdf" not in payload
        assert b"raw-report.pdf" not in payload
        assert b"source_file_alias" not in payload
        assert b"provider_alias" not in payload
