from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm_health.core.models import utc_now_iso

AGREEMENT_VERSION = "llm-health-own-risk-v1"
AGREEMENT_FILENAME = "agreement.json"


class RiskAgreementRequired(RuntimeError):
    """Raised when a health-facing command is used before own-risk acceptance."""


DISCLAIMER_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "No medical advice or clinician relationship",
        (
            "llm-health is software for organizing records, calculations, questions, "
            "and research notes.",
            "It does not diagnose, prescribe, order tests, treat disease, or replace "
            "qualified medical care.",
        ),
    ),
    (
        "Use at your own risk",
        (
            "You are responsible for decisions, actions, delays, experiments, purchases, "
            "and omissions based on its output.",
            "Outputs can be incomplete, wrong, stale, overconfident, or mismatched to "
            "your context.",
        ),
    ),
    (
        "Emergencies and red flags",
        (
            "Do not use this for emergencies or urgent symptoms.",
            "Seek urgent local help for severe pain, breathing trouble, chest pain, "
            "stroke-like symptoms, severe allergic reactions, uncontrolled bleeding, "
            "poisoning/overdose, suicidal intent, severe dehydration, or rapidly "
            "worsening illness.",
        ),
    ),
    (
        "Medication, supplements, procedures, and protocols",
        (
            "Do not start, stop, combine, or change medications, supplements, devices, "
            "procedures, or preventive protocols solely because llm-health suggested "
            "or questioned something.",
            "Review interactions, contraindications, dosing, pregnancy/child status, "
            "allergies, labs, and escalation thresholds with an appropriate "
            "professional when risk is material.",
        ),
    ),
    (
        "Research and evidence limits",
        (
            "llm-health separates mainstream, frontier, edge, contrarian, capture, "
            "inversion, and risk lenses; disagreement is not proof.",
            "Paper summaries, web research, and agent analysis may miss contrary "
            "evidence, conflicts, methods problems, or newer data.",
        ),
    ),
    (
        "Privacy and data responsibility",
        (
            "Keep raw medical files outside Git and public chats; use aliases and review "
            "every export before sharing.",
            "You are responsible for backing up, securing, and deciding where your local "
            "HUB lives.",
        ),
    ),
    (
        "No warranty",
        (
            "The package is experimental and provided as-is, without guarantees of "
            "accuracy, safety, availability, fitness, or regulatory compliance.",
        ),
    ),
)


@dataclass(frozen=True)
class AgreementStatus:
    path: Path
    accepted: bool
    version: str | None = None
    accepted_at: str | None = None


def agreement_path(store_root: str | Path) -> Path:
    return Path(store_root) / AGREEMENT_FILENAME


def render_disclaimer(*, include_acceptance_instructions: bool = True) -> str:
    lines = [
        "# llm-health own-risk agreement",
        "Read this before storing data, running reviews, or asking agents to act on health output.",
        "",
    ]
    for title, bullets in DISCLAIMER_SECTIONS:
        lines.append(f"## {title}")
        for bullet in bullets:
            lines.append(f"- {bullet}")
        lines.append("")
    if include_acceptance_instructions:
        lines.extend(
            [
                "## Accepting",
                "To initialize or use a private HUB, explicitly accept once per HUB:",
                "",
                "```sh",
                "health agreement accept --own-risk",
                "# or during setup:",
                "health config hub-path ~/health --init --accept-risk",
                "```",
                "",
                "Acceptance records only the agreement version and timestamp in the local HUB.",
            ]
        )
    return "\n".join(lines).rstrip()


def read_agreement_status(store_root: str | Path) -> AgreementStatus:
    path = agreement_path(store_root)
    if not path.exists():
        return AgreementStatus(path=path, accepted=False)
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AgreementStatus(path=path, accepted=False)
    version = str(data.get("agreement_version") or "") or None
    accepted = bool(data.get("accepted")) and version == AGREEMENT_VERSION
    accepted_at = str(data.get("accepted_at") or "") or None
    return AgreementStatus(path=path, accepted=accepted, version=version, accepted_at=accepted_at)


def write_agreement_acceptance(store_root: str | Path) -> AgreementStatus:
    root = Path(store_root)
    root.mkdir(parents=True, exist_ok=True)
    path = agreement_path(root)
    payload = {
        "accepted": True,
        "accepted_at": utc_now_iso(),
        "agreement_version": AGREEMENT_VERSION,
        "summary": (
            "User explicitly accepted own-risk, non-medical-advice, emergency, privacy, "
            "AI-error, and no-warranty terms for this local HUB."
        ),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return read_agreement_status(root)


def require_agreement(store_root: str | Path) -> AgreementStatus:
    status = read_agreement_status(store_root)
    if status.accepted:
        return status
    raise RiskAgreementRequired(
        "llm-health requires explicit own-risk acceptance before health-facing HUB use. "
        "Run `health agreement show` to read the disclaimer, then "
        "`health agreement accept --own-risk` for this HUB, or pass `--accept-risk` during setup."
    )
