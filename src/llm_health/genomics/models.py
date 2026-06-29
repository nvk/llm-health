from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from llm_health.core.enums import VisibleTag
from llm_health.core.models import stable_id, utc_now_iso
from llm_health.core.privacy import assert_safe_payload, validate_profile_alias
from llm_health.core.serialization import to_jsonable


@dataclass(frozen=True)
class GenomicSource:
    """Alias-scoped, path-free summary of one genotype or genomic report import."""

    profile_id: str
    source_kind: str
    file_sha256: str
    marker_count: int
    called_count: int
    no_call_count: int
    duplicate_marker_count: int = 0
    assay_type: str = "genotyping_array"
    genome_build: str = "unknown"
    clinical_grade: bool = False
    consent: str = "own-risk genetic context only; not diagnostic"
    tags: list[str] = field(default_factory=lambda: [VisibleTag.CONTEXT.value])
    source_id: str | None = None
    imported_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        profile = validate_profile_alias(self.profile_id)
        object.__setattr__(self, "profile_id", profile)
        kind = self.source_kind.strip().lower().replace(" ", "_")
        object.__setattr__(self, "source_kind", kind or "unknown")
        if self.source_id is None:
            object.__setattr__(self, "source_id", stable_id("gsrc", profile, self.file_sha256))
        normalized_tags = sorted({str(tag) for tag in self.tags} | {VisibleTag.CONTEXT.value})
        object.__setattr__(self, "tags", normalized_tags)
        assert_safe_payload(self)

    @property
    def call_rate(self) -> float:
        if self.marker_count <= 0:
            return 0.0
        return self.called_count / self.marker_count

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenomicSource:
        return cls(**data)


@dataclass(frozen=True)
class VariantCall:
    """Normalized enough variant call for review and cross-reference workflows."""

    profile_id: str
    source_id: str
    rsid: str
    chrom: str
    pos: int | None
    reported_genotype: str
    normalized_alleles: list[str]
    genome_build: str = "unknown"
    strand: str = "unknown"
    call_status: str = "called"
    quality_flags: list[str] = field(default_factory=list)
    variant_id: str | None = None

    def __post_init__(self) -> None:
        profile = validate_profile_alias(self.profile_id)
        object.__setattr__(self, "profile_id", profile)
        rsid = self.rsid.strip().lower()
        object.__setattr__(self, "rsid", rsid)
        genotype = self.reported_genotype.strip().upper()
        object.__setattr__(self, "reported_genotype", genotype)
        alleles = [allele.strip().upper() for allele in self.normalized_alleles if allele.strip()]
        object.__setattr__(self, "normalized_alleles", alleles)
        if self.variant_id is None:
            object.__setattr__(
                self,
                "variant_id",
                stable_id("gvar", profile, self.source_id, rsid, self.chrom, self.pos, genotype),
            )
        assert_safe_payload(self)

    @property
    def is_called(self) -> bool:
        return self.call_status == "called"

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VariantCall:
        return cls(**data)


@dataclass(frozen=True)
class GenomicInference:
    """Sparse, review-worthy genotype cross-reference artifact."""

    profile_id: str
    finding_type: str
    title: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    variant_ids: list[str] = field(default_factory=list)
    related_observation_ids: list[str] = field(default_factory=list)
    required_confirmation: bool = True
    discussion_target: str = "clinician or genetic counselor"
    confidence: str = "low"
    status: str = "review"
    tags: list[str] = field(default_factory=lambda: [VisibleTag.INFERENCE.value])
    inference_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        profile = validate_profile_alias(self.profile_id)
        object.__setattr__(self, "profile_id", profile)
        normalized_tags = sorted({str(tag) for tag in self.tags} | {VisibleTag.INFERENCE.value})
        object.__setattr__(self, "tags", normalized_tags)
        if self.inference_id is None:
            object.__setattr__(
                self,
                "inference_id",
                stable_id("ginf", profile, self.finding_type, self.title, self.variant_ids),
            )
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenomicInference:
        return cls(**data)


@dataclass(frozen=True)
class GenomicQC:
    profile_id: str
    source_id: str
    marker_count: int
    called_count: int
    no_call_count: int
    duplicate_marker_count: int
    call_rate: float
    warnings: list[str] = field(default_factory=list)
    generated_on: str = field(default_factory=lambda: date.today().isoformat())

    def __post_init__(self) -> None:
        object.__setattr__(self, "profile_id", validate_profile_alias(self.profile_id))
        assert_safe_payload(self)

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)
