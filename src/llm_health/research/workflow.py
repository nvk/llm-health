from __future__ import annotations

from dataclasses import dataclass, field

from llm_health.core.enums import EvidenceLens
from llm_health.core.privacy import assert_safe_payload
from llm_health.core.serialization import to_jsonable


def default_retrieval_ladder() -> list[str]:
    return [
        "local cache / package vault",
        "llm-wiki adapter",
        "PubMed / NCBI E-utilities metadata",
        "PubMed Central open full text",
        "Europe PMC",
        "Unpaywall + OpenAlex OA locations",
        "Crossref metadata",
        "Semantic Scholar citation graph",
        "ClinicalTrials.gov protocol/results",
        "user-provided PDF ingestion",
    ]


@dataclass(frozen=True)
class ResearchWorkflowSpec:
    topic: str
    lenses: list[str] = field(
        default_factory=lambda: [
            EvidenceLens.MAINSTREAM.value,
            EvidenceLens.FRONTIER.value,
            EvidenceLens.EDGE.value,
            EvidenceLens.CONTRARIAN.value,
            EvidenceLens.CAPTURE.value,
            EvidenceLens.RISK.value,
        ]
    )
    retrieval_ladder: list[str] = field(default_factory=default_retrieval_ladder)
    output_contract: list[str] = field(
        default_factory=lambda: [
            "claim cards",
            "evidence grid",
            "conflict/capture map",
            "absolute benefit/harm where calculable",
            "fit-to-profile notes",
            "data gaps and next-test candidates",
        ]
    )

    def __post_init__(self) -> None:
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, object]:
        return to_jsonable(self)
