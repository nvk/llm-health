from pathlib import Path

from llm_health.core.models import (
    ContextNote,
    DiagnosticGap,
    EnrolledProfile,
    Observation,
    TestCandidate,
)
from llm_health.family import FamilyHistoryEvent, FamilyRelationship
from llm_health.reports import (
    active_flagged_observations,
    generate_profile_report,
    generate_profile_reports,
)
from llm_health.stores import LocalHealthStore


def _seed_store(tmp_path: Path) -> LocalHealthStore:
    store = LocalHealthStore(tmp_path)
    store.init()
    store.enroll_profile(EnrolledProfile(profile_id="alex", birth_year=1983, role="adult"))
    store.enroll_profile(EnrolledProfile(profile_id="parenta", birth_year=1955, role="parent"))
    store.append_observation(
        Observation(
            profile_id="alex",
            marker="ALT",
            value=75,
            unit="U/L",
            category="Liver",
            observed_on="2026-01-10",
            flag="High",
            reference_range="0-55",
            observation_id="obs_alt_high",
        )
    )
    store.append_observation(
        Observation(
            profile_id="alex",
            marker="ALT",
            value=42,
            unit="U/L",
            category="Liver",
            observed_on="2026-03-10",
            reference_range="0-55",
            observation_id="obs_alt_ok",
        )
    )
    store.append_observation(
        Observation(
            profile_id="alex",
            marker="Mercury whole blood",
            value=61.2,
            unit="ug/L",
            category="Heavy metals",
            observed_on="2026-05-01",
            flag="High",
            reference_range="<=19.7",
            observation_id="obs_mercury_high",
        )
    )
    store.append_observation(
        Observation(
            profile_id="alex",
            marker="Mercury whole blood",
            value=None,
            unit="ug/L",
            category="Heavy metals",
            observed_on="2026-06-01",
            flag="PENDING",
            observation_id="obs_mercury_pending",
        )
    )
    store.append_context_note(
        ContextNote(
            profile_id="alex",
            subject="GI",
            status="self-reported fine",
            note="Current GI status is self-reported fine.",
            observed_on="2026-06-07",
        )
    )
    store.append_diagnostic_gap(
        DiagnosticGap(
            profile_id="alex",
            title="Heavy metal follow-up",
            gap_type="follow_up",
            rationale="Confirm specimen and follow-up timing.",
            candidates=[TestCandidate(name="repeat mercury whole blood", role="trend follow-up")],
            context_questions=["Was the specimen whole blood?"],
        )
    )
    store.append_family_relationship(
        FamilyRelationship(profile_id="alex", relative_id="parenta", relation="child")
    )
    store.append_family_history_event(
        FamilyHistoryEvent(
            profile_id="parenta",
            condition="Gilbert syndrome",
            status="believed",
            related_profile_ids=["alex"],
        )
    )
    return store


def test_report_generation_creates_doctor_and_family_pdfs(tmp_path: Path) -> None:
    store = _seed_store(tmp_path)
    output_dir = tmp_path / "reports-out"

    reports = generate_profile_reports(store, "alex", audience="both", output_dir=output_dir)

    assert {report.audience for report in reports} == {"doctor", "family"}
    for report in reports:
        data = report.path.read_bytes()
        assert data.startswith(b"%PDF-1.4")
        assert report.observation_count == 4
        assert report.active_flag_count == 1
        assert report.pending_count == 1
        assert b"Clinician Brief" in data or b"Family Health Summary" in data
        assert b"/Users" not in data
        assert b"Mobile Documents" not in data
        assert b".pdf" not in data
        assert b"source_file_alias" not in data


def test_flagged_rows_are_resolved_by_later_comparable_normal_rows(tmp_path: Path) -> None:
    store = _seed_store(tmp_path)

    active = active_flagged_observations(store.observations("alex"))

    assert [item.observation.marker for item in active] == ["Mercury whole blood"]


def test_single_report_output_path(tmp_path: Path) -> None:
    store = _seed_store(tmp_path)
    output = tmp_path / "family-export.pdf"

    report = generate_profile_report(store, "alex", audience="family", output=output)

    assert report.path == output
    assert output.exists()


def test_report_can_include_full_v2_wiki_history(tmp_path: Path) -> None:
    store = _seed_store(tmp_path / "hub")
    wiki = tmp_path / "wiki"
    data_dir = wiki / "output" / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "lab-observations-long.csv").write_text(
        "profile_id,observation_id,observation_date,analyte_en,numeric_value,"
        "ucum_unit,panel_en,flag_raw,reference_range_raw,source_id\n"
        "alex,v2_old_alt,2025-01-01,ALT,40,U/L,Liver,,0-55,src1\n"
        "alex,v2_old_ast,2025-01-01,AST,30,U/L,Liver,,0-45,src1\n",
        encoding="utf-8",
    )

    report = generate_profile_report(
        store,
        "alex",
        audience="doctor",
        output=tmp_path / "doctor.pdf",
        wiki_root=wiki,
    )

    assert report.observation_count == 6
