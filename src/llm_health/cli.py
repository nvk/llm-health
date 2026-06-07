from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from importlib import resources
from pathlib import Path

from llm_health import __version__
from llm_health.agreement import (
    RiskAgreementRequired,
    read_agreement_status,
    render_disclaimer,
    require_agreement,
    write_agreement_acceptance,
)
from llm_health.assessment_v2.bridge import import_latest_for_profile
from llm_health.assessment_v2.export.v2_web import export_v2_web
from llm_health.config import (
    load_config,
    resolve_store_path,
    resolve_wiki_root,
    set_hub_path,
    set_wiki_root,
)
from llm_health.core.models import ContextNote, EnrolledProfile, Observation, stable_id
from llm_health.core.privacy import PrivacyError, validate_profile_alias
from llm_health.deid import (
    deidentify_text,
    load_text_input,
    render_extract,
    stage_deidentified_text,
)
from llm_health.engine import DiagnosticGapEngine, LeastHarmEngine, ReviewEngine
from llm_health.onboarding import (
    SOURCE_LINKS,
    SOURCE_NOTES,
    render_data_wishlist,
    render_dr_visit,
    render_welcome,
)
from llm_health.registry import dumps_capabilities, render_capabilities
from llm_health.research import ResearchWorkflowSpec
from llm_health.service import LOCAL_HOSTS, render_service_routes, run_service
from llm_health.specialists import (
    create_specialist_notes,
    list_specialists,
    render_specialist_notes,
    render_specialists,
    resolve_specialist_id,
)
from llm_health.stores import LocalHealthStore
from llm_health.test_batteries import TestBatteryEngine, render_test_battery


def _store_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--store",
        default=None,
        help=(
            "Override store path; default resolves from LLM_HEALTH_HUB "
            "or ~/.config/llm-health/config.json"
        ),
    )


def _store_from_args(args: argparse.Namespace) -> LocalHealthStore:
    return LocalHealthStore(resolve_store_path(getattr(args, "store", None)))


def _risk_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--accept-risk",
        action="store_true",
        help="Explicitly accept the own-risk agreement for this local HUB before running",
    )


def _ensure_risk_agreement(args: argparse.Namespace, store: LocalHealthStore) -> None:
    if getattr(args, "accept_risk", False):
        write_agreement_acceptance(store.root)
        return
    require_agreement(store.root)


def _private_store_from_args(args: argparse.Namespace) -> LocalHealthStore:
    store = _store_from_args(args)
    _ensure_risk_agreement(args, store)
    return store


def _profile_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", required=True, help="De-identified enrolled profile alias")


def _profile_for_store(args: argparse.Namespace, store: LocalHealthStore) -> str:
    profile = validate_profile_alias(args.profile)
    if not store.profile_exists(profile):
        raise PrivacyError(f"profile alias {profile!r} is not enrolled; run `health enroll` first")
    return profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llm-health", description="Local health intelligence CLI")
    parser.add_argument("--version", action="version", version=f"llm-health {__version__}")
    sub = parser.add_subparsers(dest="command", required=False)

    doctor = sub.add_parser("doctor", help="Check basic runtime status")
    _store_arg(doctor)

    init = sub.add_parser("init", help="Initialize the resolved llm-health HUB/store")
    _store_arg(init)
    _risk_arg(init)

    enroll = sub.add_parser("enroll", help="Enroll a de-identified profile alias")
    _store_arg(enroll)
    _risk_arg(enroll)
    enroll.add_argument("--alias", required=True, help="Alias token, e.g. sol")
    enroll.add_argument("--birth-year", type=int, help="Birth year only; no full birth dates")
    enroll.add_argument(
        "--birth-month",
        type=int,
        help="Optional birth month 1-12 when month precision is useful; no birth day",
    )
    enroll.add_argument("--role", help="Alias-safe role/context label")
    enroll.add_argument("--note", help="Alias-safe note; do not include raw identifiers")

    profiles = sub.add_parser("profiles", help="List enrolled profile aliases")
    _store_arg(profiles)
    _risk_arg(profiles)

    welcome = sub.add_parser("welcome", help="Show first-run onboarding and intake prompts")
    _store_arg(welcome)

    data_wishlist = sub.add_parser("data-wishlist", help="Show useful data dumps to import")
    _store_arg(data_wishlist)

    dr_visit = sub.add_parser("dr-visit", help="Show cadence-aware check-in questions")
    _store_arg(dr_visit)
    _risk_arg(dr_visit)
    _profile_arg(dr_visit)
    dr_visit.add_argument(
        "--cadence",
        choices=[
            "onboarding",
            "weekly",
            "monthly",
            "quarterly",
            "annual",
            "pre-lab",
            "post-result",
        ],
        default="monthly",
    )
    dr_visit.add_argument(
        "--sources", action="store_true", help="Also print source/rationale notes for the cadence"
    )

    config = sub.add_parser("config", help="Read or write llm-health config")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_show = config_sub.add_parser("show", help="Show current config and resolved store")
    config_show.add_argument("--config-path")
    config_hub = config_sub.add_parser("hub-path", help="Set the default llm-health HUB path")
    config_hub.add_argument("path")
    config_hub.add_argument("--config-path")
    config_hub.add_argument("--init", action="store_true", help="Initialize the hub after saving")
    config_hub.add_argument(
        "--accept-risk",
        action="store_true",
        help="Accept the own-risk agreement when initializing the hub",
    )
    config_wiki = config_sub.add_parser(
        "wiki-root", help="Set the default health-assessments wiki root for UI exports"
    )
    config_wiki.add_argument("path")
    config_wiki.add_argument("--config-path")

    ui = sub.add_parser("ui", help="Regenerate and open the local Assessment v2 static UI")
    _store_arg(ui)
    _risk_arg(ui)
    ui.add_argument("--wiki-root", help="Override health-assessments wiki root for this run")
    ui.add_argument(
        "--output",
        help="Override static UI output directory; default is <resolved HUB>/v2-web",
    )
    ui.add_argument("--no-open", action="store_true", help="Export only; do not open browser")

    agreement = sub.add_parser("agreement", help="Show or accept the own-risk agreement")
    _store_arg(agreement)
    agreement_sub = agreement.add_subparsers(dest="agreement_command", required=False)
    agreement_show = agreement_sub.add_parser("show", help="Print the full own-risk disclaimer")
    _store_arg(agreement_show)
    agreement_status = agreement_sub.add_parser(
        "status", help="Print agreement status for the resolved HUB"
    )
    _store_arg(agreement_status)
    agreement_accept = agreement_sub.add_parser("accept", help="Accept the own-risk agreement")
    _store_arg(agreement_accept)
    agreement_accept.add_argument(
        "--own-risk",
        action="store_true",
        required=True,
        help="Required explicit acknowledgement that use is at your own risk",
    )

    ingest = sub.add_parser(
        "ingest-note", help="Add one de-identified observation and trigger review"
    )
    _store_arg(ingest)
    _risk_arg(ingest)
    _profile_arg(ingest)
    ingest.add_argument("--marker", required=True)
    ingest.add_argument("--value", type=float)
    ingest.add_argument("--unit")
    ingest.add_argument("--category", default="uncategorized")
    ingest.add_argument("--date", dest="observed_on")
    ingest.add_argument("--flag")
    ingest.add_argument("--reference-range")
    ingest.add_argument("--comparator")
    ingest.add_argument("--specimen")
    ingest.add_argument("--interpretation")
    ingest.add_argument("--source-id", default="user_note")
    ingest.add_argument("--note")
    ingest.add_argument(
        "--deep",
        choices=["smart", "always", "none"],
        default="smart",
        help="Deep research queuing mode for this ingest",
    )

    sync_v2 = sub.add_parser(
        "sync-v2", help="Import latest de-identified v2 canonical rows and trigger review"
    )
    _store_arg(sync_v2)
    _risk_arg(sync_v2)
    sync_v2.add_argument(
        "--wiki-root",
        required=True,
        help="health-assessments wiki root containing output/data CSVs",
    )
    sync_v2.add_argument("--profile", required=True, choices=["rod", "cara", "all"])
    sync_v2.add_argument("--deep", choices=["smart", "always", "none"], default="smart")

    review = sub.add_parser("review", help="Show latest quick-review cards")
    _store_arg(review)
    _risk_arg(review)
    _profile_arg(review)
    review.add_argument("--limit", type=int, default=10)

    self_report = sub.add_parser(
        "self-report", help="Record a self-reported context note, not a lab result"
    )
    _store_arg(self_report)
    _risk_arg(self_report)
    _profile_arg(self_report)
    self_report.add_argument("--subject", required=True)
    self_report.add_argument("--status", required=True)
    self_report.add_argument("--note", required=True)
    self_report.add_argument("--date", dest="observed_on")

    context = sub.add_parser("context", help="Show self-reported context notes")
    _store_arg(context)
    _risk_arg(context)
    _profile_arg(context)
    context.add_argument("--subject")
    context.add_argument("--limit", type=int, default=10)

    result = sub.add_parser(
        "result", help="Show latest matching observation(s) with source reference range"
    )
    _store_arg(result)
    _risk_arg(result)
    _profile_arg(result)
    result.add_argument("--marker", required=True, help="Marker/category substring, e.g. mercury")
    result.add_argument("--category", help="Optional category substring filter")
    result.add_argument("--limit", type=int, default=5)

    gaps = sub.add_parser("close-gaps", help="Create diagnostic-gap/test-candidate cards")
    _store_arg(gaps)
    _risk_arg(gaps)
    _profile_arg(gaps)

    battery = sub.add_parser(
        "test-battery", help="Suggest profile-aware TEST_CANDIDATE batteries"
    )
    _store_arg(battery)
    _risk_arg(battery)
    _profile_arg(battery)
    battery.add_argument(
        "--scope",
        choices=["core", "expanded", "complete"],
        default="expanded",
        help="core=must/high, expanded=adds medium/low, complete=also nice-to-have",
    )
    battery.add_argument(
        "--category",
        default="all",
        help=(
            "all, foundation, cardio, metabolic, liver, kidney, nutrient, hormone, "
            "inflammation, exposure, sleep, pediatric, gaps"
        ),
    )
    battery.add_argument(
        "--no-gaps",
        action="store_true",
        help="Do not blend current diagnostic-gap candidates into the battery",
    )
    battery.add_argument(
        "--sources", action="store_true", help="Print source/rationale notes and links"
    )
    battery.add_argument(
        "--queue-research",
        action="store_true",
        help="Queue deep research jobs to refresh the selected battery",
    )

    plan = sub.add_parser(
        "plan-research", help="Show queued research jobs and the default research contract"
    )
    _store_arg(plan)
    _risk_arg(plan)
    _profile_arg(plan)
    plan.add_argument("--topic", help="Create a research workflow spec for a new topic")

    plugins = sub.add_parser(
        "plugin-paths", help="Print packaged agent/plugin template paths"
    )
    plugins.add_argument(
        "--kind",
        choices=["codex", "claude", "opencode", "agents", "all"],
        default="all",
    )

    capabilities = sub.add_parser("capabilities", help="Show llm-health feature map metadata")
    capabilities.add_argument(
        "--kind",
        choices=["all", "core", "data", "review", "research", "ui", "agent", "privacy", "service"],
        default="all",
        help="Filter the registry by capability kind",
    )
    capabilities.add_argument("--json", action="store_true", help="Print machine-readable JSON")

    deid = sub.add_parser("deid", help="Preview or stage de-identified text")
    deid_sub = deid.add_subparsers(dest="deid_command", required=True)
    for action, help_text in [
        ("extract", "Extract safe de-id entity metadata"),
        ("preview", "Print redacted text without storing it"),
        ("apply", "Stage redacted text under the private HUB"),
    ]:
        deid_cmd = deid_sub.add_parser(action, help=help_text)
        _store_arg(deid_cmd)
        _risk_arg(deid_cmd)
        deid_cmd.add_argument("input", help="Text or path to a local text file")
        deid_cmd.add_argument(
            "--method",
            choices=["replace", "mask", "hash"],
            default="replace",
            help="Redaction style for replacements",
        )
        deid_cmd.add_argument("--json", action="store_true", help="Print JSON output")
        if action == "apply":
            deid_cmd.add_argument(
                "--staging-only",
                action="store_true",
                required=True,
                help="Required: write only redacted staging files, never raw input",
            )

    service = sub.add_parser("service", help="Start or smoke-test the local-only service")
    _store_arg(service)
    _risk_arg(service)
    service.add_argument(
        "--local",
        action="store_true",
        default=True,
        help="Use a localhost bind; this is the default and recommended mode",
    )
    service.add_argument("--host", default="127.0.0.1", help="Bind host; defaults to localhost")
    service.add_argument("--port", type=int, default=8765, help="Bind port")
    service.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="Explicitly allow a non-local bind host; not recommended",
    )
    service.add_argument("--smoke", action="store_true", help="Print routes without serving")

    specialists = sub.add_parser(
        "specialists", help="List registered specialist/category agents"
    )
    specialists.add_argument("--short", action="store_true", help="Print only ids and names")

    consult = sub.add_parser(
        "consult", help="Run a specialist/category-agent consult and persist notes"
    )
    _store_arg(consult)
    _risk_arg(consult)
    _profile_arg(consult)
    consult.add_argument(
        "--specialist",
        default="auto",
        help="auto, internal_medicine, liver_biliary_gi, toxins_exposures, etc.",
    )
    consult.add_argument("--topic", help="Optional focused question/topic for the consult")
    consult.add_argument(
        "--no-persist", action="store_true", help="Print consult notes without storing them"
    )

    specialist_notes = sub.add_parser("specialist-notes", help="Show stored specialist notes")
    _store_arg(specialist_notes)
    _risk_arg(specialist_notes)
    _profile_arg(specialist_notes)
    specialist_notes.add_argument("--specialist", help="Filter by specialist id/substring")
    specialist_notes.add_argument("--limit", type=int, default=10)

    least = sub.add_parser("least-harm", help="Draft a low-intervention option card")
    _store_arg(least)
    _risk_arg(least)
    least.add_argument("target")

    med = sub.add_parser("med-review", help="Draft a medication collateral-damage review")
    _store_arg(med)
    _risk_arg(med)
    _profile_arg(med)
    med.add_argument("--active", required=True)
    med.add_argument("--indication", default="unknown")

    protocol = sub.add_parser("protocol-review", help="Draft a preventive-protocol review card")
    _store_arg(protocol)
    _risk_arg(protocol)
    _profile_arg(protocol)
    protocol.add_argument("target")

    return parser


def cmd_doctor(args: argparse.Namespace) -> int:
    config = load_config()
    store_path = resolve_store_path(args.store)
    store = LocalHealthStore(store_path)
    exists = store_path.exists()
    print(f"llm-health {__version__}")
    print(f"python: {sys.version.split()[0]}")
    print(
        f"config: {config.config_path} ({'exists' if config.config_path.exists() else 'not found'})"
    )
    print(f"hub: {config.hub_path or '[not set]'}")
    print(f"wiki_root: {config.wiki_root or '[not set]'}")
    print(f"store: {store.root} ({'exists' if exists else 'not initialized'})")
    agreement = read_agreement_status(store.root)
    print(f"agreement: {'accepted' if agreement.accepted else 'not accepted'}")
    if agreement.accepted_at:
        print(f"agreement_at: {agreement.accepted_at}")
    print("privacy: alias-only demo profiles; raw data paths blocked in stored artifacts")
    if not exists:
        print(
            "first_run: try `health welcome`, `health agreement show`, "
            "`health agreement accept --own-risk`, then "
            "`health enroll --alias <alias> --birth-year <yyyy>`"
        )
    print("status: ok")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    if args.accept_risk:
        status = write_agreement_acceptance(store.root)
        print(f"Accepted llm-health own-risk agreement: {status.version} at {status.accepted_at}")
    else:
        require_agreement(store.root)
    store.init()
    print(f"Initialized llm-health store: {store.root}")
    return 0


def cmd_enroll(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = EnrolledProfile(
        profile_id=args.alias,
        birth_year=args.birth_year,
        birth_month=args.birth_month,
        role=args.role,
        note=args.note,
    )
    store.enroll_profile(profile)
    print(f"Enrolled profile alias: {profile.profile_id}")
    print(f"  Birth: {profile.birth_label}")
    if profile.role:
        print(f"  Role/context: {profile.role}")
    print(f"  Tags: {', '.join(profile.tags)}")
    return 0


def cmd_profiles(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    for profile in store.enrolled_profiles(include_defaults=True):
        role = f" · {profile.role}" if profile.role else ""
        print(f"{profile.profile_id} · birth {profile.birth_label}{role}")
    return 0


def cmd_welcome(args: argparse.Namespace) -> int:
    print(render_welcome())
    return 0


def cmd_data_wishlist(args: argparse.Namespace) -> int:
    print(render_data_wishlist())
    return 0


def cmd_dr_visit(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = _profile_for_store(args, store)
    print(f"# Dr Visit for {profile} · {args.cadence}")
    print(render_dr_visit(args.cadence))
    if args.sources:
        print("\n## Source/rationale notes")
        for note in SOURCE_NOTES:
            print(f"- {note}")
        print("\n## Source links")
        for label, url in SOURCE_LINKS:
            print(f"- {label}: {url}")
    return 0


def cmd_agreement(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    command = args.agreement_command or "show"
    if command == "show":
        print(render_disclaimer())
        status = read_agreement_status(store.root)
        print()
        print("## Current HUB status")
        print(f"store: {store.root}")
        print(f"agreement: {'accepted' if status.accepted else 'not accepted'}")
        if status.accepted_at:
            print(f"accepted_at: {status.accepted_at}")
        return 0
    if command == "status":
        status = read_agreement_status(store.root)
        print(f"store: {store.root}")
        print(f"agreement: {'accepted' if status.accepted else 'not accepted'}")
        print(f"agreement_version: {status.version or '[none]'}")
        if status.accepted_at:
            print(f"accepted_at: {status.accepted_at}")
        return 0
    if command == "accept":
        status = write_agreement_acceptance(store.root)
        print(f"Accepted llm-health own-risk agreement: {status.version}")
        print(f"accepted_at: {status.accepted_at}")
        print(f"store: {store.root}")
        return 0
    raise ValueError(f"unknown agreement command: {command}")


def cmd_config(args: argparse.Namespace) -> int:
    if args.config_command == "show":
        config = load_config(args.config_path)
        print(f"config: {config.config_path}")
        print(f"hub: {config.hub_path or '[not set]'}")
        print(f"wiki_root: {config.wiki_root or '[not set]'}")
        print(f"resolved_store: {config.hub_path or resolve_store_path()}")
        print(f"resolved_wiki_root: {config.wiki_root or resolve_wiki_root() or '[not set]'}")
        return 0
    if args.config_command == "hub-path":
        config = set_hub_path(args.path, args.config_path)
        print(f"Saved llm-health hub_path: {config.hub_path}")
        print(f"config: {config.config_path}")
        if args.init:
            store = LocalHealthStore(config.hub_path)
            if args.accept_risk:
                status = write_agreement_acceptance(store.root)
                print(
                    f"Accepted llm-health own-risk agreement: {status.version} "
                    f"at {status.accepted_at}"
                )
            else:
                require_agreement(store.root)
            store.init()
            print(f"Initialized llm-health HUB/store: {store.root}")
        return 0
    if args.config_command == "wiki-root":
        config = set_wiki_root(args.path, args.config_path)
        print(f"Saved llm-health wiki_root: {config.wiki_root}")
        print(f"config: {config.config_path}")
        return 0
    raise ValueError(f"unknown config command: {args.config_command}")


def cmd_ui(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    wiki_root = resolve_wiki_root(args.wiki_root)
    if wiki_root is None:
        print(
            "wiki root not configured. Run `health config wiki-root <wiki-root>` "
            "or pass `health ui --wiki-root <path>`.",
            file=sys.stderr,
        )
        return 4
    observations_csv = wiki_root / "output" / "data" / "lab-observations-long.csv"
    if not observations_csv.exists():
        print(
            f"wiki root missing canonical observations CSV: {observations_csv}",
            file=sys.stderr,
        )
        return 4
    output_dir = Path(args.output).expanduser() if args.output else store.root / "v2-web"
    export = export_v2_web(wiki_root, output_dir)
    index_path = export.output_dir / "index.html"
    print(
        f"exported UI: {export.observation_count:,} observations, "
        f"{export.report_count:,} reports, {export.wearable_daily_count:,} wearable daily rows"
    )
    print(f"open: {index_path}")
    if export.latest_weights:
        weights = ", ".join(
            f"{profile}: {value:g} kg" for profile, value in sorted(export.latest_weights.items())
        )
        print(f"latest weights: {weights}")
    if not args.no_open:
        webbrowser.open(index_path.resolve().as_uri())
        print("browser: opened")
    return 0


def cmd_ingest_note(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = _profile_for_store(args, store)
    observation = Observation(
        profile_id=profile,
        marker=args.marker,
        value=args.value,
        unit=args.unit,
        category=args.category,
        observed_on=args.observed_on
        or Observation(profile_id=profile, marker=args.marker).observed_on,
        flag=args.flag,
        reference_range=args.reference_range,
        comparator=args.comparator,
        specimen=args.specimen,
        interpretation=args.interpretation,
        source_id=args.source_id,
        note=args.note,
    )
    threshold = 0.0 if args.deep == "always" else 2.0 if args.deep == "none" else 0.60
    result = ReviewEngine(store, interest_threshold=threshold).review_new_observations(
        profile, [observation], persist=True
    )
    store.append_observation(observation)
    gaps = DiagnosticGapEngine().create_gaps(profile, [observation])
    for gap in gaps:
        store.append_diagnostic_gap(gap)

    print(f"Added observation: {observation.marker} ({observation.category}) for {profile}")
    print(
        f"Quick cards: {len(result.cards)} | diagnostic gaps: {len(gaps)} | "
        f"research jobs: {len(result.research_jobs)}"
    )
    for card in result.cards:
        print(f"- {card.title}: {card.summary}")
    for job in result.research_jobs:
        print(f"Research queued: {job.topic}")
    return 0


def cmd_sync_v2(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profiles = ["rod", "cara"] if args.profile == "all" else [args.profile]
    threshold = 0.0 if args.deep == "always" else 2.0 if args.deep == "none" else 0.60
    total_obs = total_cards = total_gaps = total_jobs = 0
    for profile in profiles:
        result_meta, observations = import_latest_for_profile(args.wiki_root, profile)
        existing_observation_ids = {
            observation.observation_id for observation in store.observations(profile)
        }
        new_observations = [
            observation
            for observation in observations
            if observation.observation_id not in existing_observation_ids
        ]
        review = ReviewEngine(store, interest_threshold=threshold).review_new_observations(
            profile, new_observations, persist=True
        ) if new_observations else None
        for observation in observations:
            store.append_observation(observation)
        gaps = DiagnosticGapEngine().create_gaps(profile, new_observations)
        for gap in gaps:
            store.append_diagnostic_gap(gap)
        total_obs += len(observations)
        total_cards += len(review.cards) if review else 0
        total_gaps += len(gaps)
        total_jobs += len(review.research_jobs) if review else 0
        sources = ", ".join(result_meta.source_ids) if result_meta.source_ids else "none"
        print(
            f"{profile}: imported {result_meta.imported_count} latest observation(s) "
            f"from {result_meta.latest_date or 'no date'}; "
            f"new={len(new_observations)}; sources: {sources}"
        )
    print(
        f"sync-v2 complete: observations={total_obs}, quick_cards={total_cards}, "
        f"diagnostic_gaps={total_gaps}, research_jobs={total_jobs}"
    )
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    cards = store.quick_review_cards(profile)[-args.limit :]
    if not cards:
        print("No quick-review cards found. Try ingesting a note or syncing data first.")
        return 0
    for card in cards:
        print(f"[{card.priority:.2f}] {card.title}")
        print(f"  {card.summary}")
        if card.triggers:
            print(f"  triggers: {', '.join(card.triggers)}")
    return 0


def cmd_self_report(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile = _profile_for_store(args, store)
    observed_on = (
        args.observed_on or Observation(profile_id=profile, marker=args.subject).observed_on
    )
    note = ContextNote(
        profile_id=profile,
        subject=args.subject,
        status=args.status,
        note=args.note,
        observed_on=observed_on,
        context_id=stable_id(
            "context", profile, args.subject.strip().lower(), args.status, observed_on, args.note
        ),
    )
    store.append_context_note(note)
    print(f"Recorded self-report context for {profile}: {note.subject} · {note.status}")
    print(f"  Date: {note.observed_on}")
    print(f"  Tags: {', '.join(note.tags)}")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    notes = store.context_notes(profile, subject=args.subject)
    notes.sort(key=lambda item: (item.observed_on, item.created_at), reverse=True)
    if not notes:
        print("No self-reported context notes found.")
        return 0
    for index, note in enumerate(notes[: args.limit]):
        if index:
            print()
        print(f"{note.profile_id} · {note.subject} · {note.status}")
        print(f"  Date: {note.observed_on}")
        print(f"  Tag: {', '.join(note.tags)}")
        print(f"  Note: {note.note}")
    return 0


def _format_observation_value(observation: Observation) -> str:
    if observation.value is None:
        return "pending/non-numeric"
    value = f"{observation.value:g}"
    comparator = (observation.comparator or "").strip()
    if comparator in {"<", ">", "<=", ">="}:
        value = f"{comparator}{value}"
    if observation.unit:
        value = f"{value} {observation.unit}"
    return value


def cmd_result(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    marker = args.marker.strip().lower()
    category = (args.category or "").strip().lower()
    matches = []
    for observation in store.observations(profile):
        marker_hit = marker in observation.marker.lower() or marker in observation.category.lower()
        category_hit = not category or category in observation.category.lower()
        if marker_hit and category_hit:
            matches.append(observation)
    matches.sort(key=lambda obs: (obs.observed_on, obs.marker), reverse=True)

    if not matches:
        print("No matching observations found.")
        return 0

    for index, observation in enumerate(matches[: args.limit]):
        if index:
            print()
        print(f"{observation.profile_id} · {observation.marker}")
        print(f"  Date: {observation.observed_on}")
        print(f"  Result: {_format_observation_value(observation)}")
        print(
            "  Normal range (source): "
            f"{observation.reference_range or '[not available in source row]'}"
        )
        if observation.flag:
            print(f"  Source flag: {observation.flag}")
        if observation.interpretation:
            print(f"  Source interpretation: {observation.interpretation}")
        if observation.specimen:
            print(f"  Specimen: {observation.specimen}")
    return 0


def cmd_close_gaps(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    observations = store.observations(profile)
    gaps = DiagnosticGapEngine().create_gaps(profile, observations)
    for gap in gaps:
        store.append_diagnostic_gap(gap)
    if not gaps:
        print("No diagnostic gaps generated from current observations.")
        return 0
    for gap in gaps:
        print(f"[{gap.priority:.2f}] {gap.title} · {gap.gap_type}")
        print(f"  {gap.rationale}")
        for candidate in gap.candidates:
            print(f"  - {candidate.name} ({candidate.score():.2f}): {candidate.role}")
        if gap.context_questions:
            print("  context first:")
            for question in gap.context_questions:
                print(f"    - {question}")
    return 0


def _profile_record(store: LocalHealthStore, profile_id: str) -> EnrolledProfile:
    for profile in store.enrolled_profiles(include_defaults=True):
        if profile.profile_id == profile_id:
            return profile
    raise PrivacyError(f"profile alias {profile_id!r} is not enrolled; run `health enroll` first")


def _merged_gaps(store: LocalHealthStore, profile: str, observations: list[Observation]):
    merged = {gap.gap_id: gap for gap in store.diagnostic_gaps(profile)}
    for gap in DiagnosticGapEngine().create_gaps(profile, observations):
        merged.setdefault(gap.gap_id, gap)
    return list(merged.values())


def cmd_test_battery(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile_id = _profile_for_store(args, store)
    profile = _profile_record(store, profile_id)
    observations = store.observations(profile_id)
    gaps = _merged_gaps(store, profile_id, observations) if not args.no_gaps else []
    engine = TestBatteryEngine()
    battery = engine.generate(
        profile,
        observations,
        gaps,
        scope=args.scope,
        category=args.category,
        include_gaps=not args.no_gaps,
    )
    if args.queue_research:
        jobs = engine.research_jobs_for(battery)
        for job in jobs:
            store.append_research_job(job)
        print(f"Queued research jobs: {len(jobs)}")
        for job in jobs:
            print(f"- {job.topic}")
        print()
    print(render_test_battery(battery, sources=args.sources))
    return 0


def cmd_plan_research(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    if args.topic:
        spec = ResearchWorkflowSpec(topic=args.topic)
        print(f"Research workflow: {spec.topic}")
        print(f"Lenses: {', '.join(spec.lenses)}")
        print("Retrieval ladder:")
        for step in spec.retrieval_ladder:
            print(f"- {step}")
        return 0
    jobs = store.research_jobs(profile)
    if not jobs:
        print("No research jobs queued.")
        return 0
    for job in jobs:
        print(f"[{job.priority:.2f}] {job.topic} · {job.status}")
        print(f"  {job.rationale}")
        if job.triggers:
            print(f"  triggers: {', '.join(job.triggers)}")
    return 0


def cmd_plugin_paths(args: argparse.Namespace) -> int:
    base = resources.files("llm_health.plugin_templates")
    paths = {
        "codex": base / "codex" / "llm-health",
        "claude": base / "claude" / "health",
        "opencode": base / "opencode" / "llm-health",
        "agents": base / "agents" / "AGENTS.health.md",
    }
    for kind, path in paths.items():
        if args.kind in {"all", kind}:
            print(f"{kind}: {path}")
    return 0


def cmd_capabilities(args: argparse.Namespace) -> int:
    kind = None if args.kind == "all" else args.kind
    if args.json:
        print(dumps_capabilities(kind))
        return 0
    print(render_capabilities(kind))
    return 0


def cmd_deid(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    text = load_text_input(args.input)
    result = deidentify_text(text, method=args.method)

    if args.deid_command == "extract":
        payload = {
            "backend": result.backend,
            "entity_count": result.entity_count,
            "entities": [entity.to_dict() for entity in result.entities],
        }
        output = (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.json
            else render_extract(result)
        )
        print(output)
        return 0

    if args.deid_command == "preview":
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True) if args.json else result.text)
        return 0

    if args.deid_command == "apply":
        store.init()
        text_path, meta_path, staged = stage_deidentified_text(text, store.root, method=args.method)
        print(f"staged: {text_path.relative_to(store.root)}")
        print(f"metadata: {meta_path.relative_to(store.root)}")
        print(f"backend: {staged.backend}")
        print(f"entities: {staged.entity_count}")
        return 0

    raise ValueError(f"unknown deid command: {args.deid_command}")


def cmd_service(args: argparse.Namespace) -> int:
    if args.host not in LOCAL_HOSTS and not args.allow_nonlocal:
        print(
            "refusing non-local service bind without --allow-nonlocal; "
            "use --host 127.0.0.1 for local-only mode",
            file=sys.stderr,
        )
        return 4

    store = _private_store_from_args(args)
    store.init()

    if args.smoke:
        print(render_service_routes())
        print(f"host: {args.host}")
        print(f"port: {args.port}")
        print("status: smoke-ok")
        return 0

    try:
        print(f"starting llm-health local service on http://{args.host}:{args.port}")
        run_service(store, host=args.host, port=args.port)
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 4


def cmd_specialists(args: argparse.Namespace) -> int:
    specs = list_specialists()
    if args.short:
        for spec in specs:
            print(f"{spec.specialist_id} · {spec.name}")
        return 0
    print(render_specialists(specs))
    return 0


def cmd_consult(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    store.init()
    profile_id = _profile_for_store(args, store)
    profile = _profile_record(store, profile_id)
    observations = store.observations(profile_id)
    gaps = _merged_gaps(store, profile_id, observations)
    context_notes = store.context_notes(profile_id)
    notes = create_specialist_notes(
        profile,
        observations,
        gaps,
        context_notes,
        specialist=args.specialist,
        topic=args.topic,
    )
    if not args.no_persist:
        for note in notes:
            store.append_specialist_note(note)
    print(render_specialist_notes(notes))
    if not args.no_persist:
        print(f"\nstored_specialist_notes: {len(notes)}")
    return 0


def cmd_specialist_notes(args: argparse.Namespace) -> int:
    store = _private_store_from_args(args)
    profile = _profile_for_store(args, store)
    specialist_id = resolve_specialist_id(args.specialist) if args.specialist else None
    notes = store.specialist_notes(profile, specialist_id=specialist_id)
    notes.sort(key=lambda item: item.created_at, reverse=True)
    print(render_specialist_notes(notes[: args.limit]))
    return 0


def cmd_least_harm(args: argparse.Namespace) -> int:
    _private_store_from_args(args)
    option = LeastHarmEngine().watchful_waiting_option(args.target)
    print(f"{option.option_type}: {option.target}")
    print(option.rationale)
    print("Track: " + ", ".join(option.track))
    print("Escalate if: " + ", ".join(option.escalate_if))
    return 0


def cmd_med_review(args: argparse.Namespace) -> int:
    _private_store_from_args(args)
    profile = validate_profile_alias(args.profile)
    review = LeastHarmEngine().medication_collateral_review(
        profile, args.active, args.indication
    )
    print(f"Medication collateral review: {review.active_or_class}")
    print(f"Indication: {review.indication}")
    print("Collateral lanes: " + ", ".join(review.collateral_damage))
    print("Avoidability questions:")
    for question in review.avoidability_questions:
        print(f"- {question}")
    return 0


def cmd_protocol_review(args: argparse.Namespace) -> int:
    _private_store_from_args(args)
    profile = validate_profile_alias(args.profile)
    review = LeastHarmEngine().preventive_protocol_review(profile, args.target)
    print(f"Preventive protocol review: {review.target}")
    print("Conclusion options: " + ", ".join(review.conclusion_options))
    print("Benefit questions:")
    for question in review.benefit_questions:
        print(f"- {question}")
    print("Harm questions:")
    for question in review.harm_questions:
        print(f"- {question}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        print(render_welcome())
        return 0
    commands = {
        "doctor": cmd_doctor,
        "init": cmd_init,
        "enroll": cmd_enroll,
        "profiles": cmd_profiles,
        "welcome": cmd_welcome,
        "data-wishlist": cmd_data_wishlist,
        "dr-visit": cmd_dr_visit,
        "config": cmd_config,
        "ui": cmd_ui,
        "agreement": cmd_agreement,
        "ingest-note": cmd_ingest_note,
        "sync-v2": cmd_sync_v2,
        "review": cmd_review,
        "self-report": cmd_self_report,
        "context": cmd_context,
        "result": cmd_result,
        "close-gaps": cmd_close_gaps,
        "test-battery": cmd_test_battery,
        "plan-research": cmd_plan_research,
        "plugin-paths": cmd_plugin_paths,
        "capabilities": cmd_capabilities,
        "deid": cmd_deid,
        "service": cmd_service,
        "specialists": cmd_specialists,
        "consult": cmd_consult,
        "specialist-notes": cmd_specialist_notes,
        "least-harm": cmd_least_harm,
        "med-review": cmd_med_review,
        "protocol-review": cmd_protocol_review,
    }
    try:
        return commands[args.command](args)
    except RiskAgreementRequired as exc:
        print(f"agreement required: {exc}", file=sys.stderr)
        return 3
    except PrivacyError as exc:
        print(f"privacy error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
