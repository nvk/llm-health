from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib import resources

CATALOG_RESOURCE = "data/clinical_markers.tsv"
ACGT = {"A", "C", "G", "T"}
DEFAULT_MATCH_RUNTIME_DEFAULTS = frozenset({"candidate_default_after_qc"})
DEFERRED_RUNTIME_DEFAULTS = frozenset(
    {"defer_until_context", "defer_until_strand_fixture", "defer_until_clinvar_validation"}
)
SPECIALTY_RUNTIME_DEFAULTS = frozenset({"specialty_opt_in"})
SENSITIVE_RUNTIME_DEFAULTS = frozenset(
    {"sensitive_opt_in", "sensitive_opt_in_gene_panel_preferred"}
)


@dataclass(frozen=True)
class MarkerKnowledge:
    rsid: str
    gene: str
    topic: str
    finding_type: str
    effect_allele: str
    label: str
    summary: str
    evidence_gate: str
    discussion_target: str = "clinician or genetic counselor"
    confidence: str = "low"
    clinical_reference: str = ""
    source_url: str = ""
    confirmation_tests: str = ""
    clinical_context_gate: str = ""
    reporting_tier: str = ""
    runtime_default: str = "candidate_default_after_qc"
    match_scope: str = ""
    source_family: str = ""
    output_tags: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    date_checked: str = ""
    catalog_version: str = ""

    @property
    def match_alleles(self) -> tuple[str, ...]:
        """Simple allele tokens that can be matched from 23andMe/Ancestry-like calls."""

        tokens = [token.strip().upper() for token in re.split(r"[|,;/\s]+", self.effect_allele)]
        return tuple(token for token in tokens if token in ACGT)

    @property
    def is_sensitive(self) -> bool:
        return self.runtime_default in SENSITIVE_RUNTIME_DEFAULTS

    @property
    def is_specialty(self) -> bool:
        return self.runtime_default in SPECIALTY_RUNTIME_DEFAULTS

    @property
    def is_deferred(self) -> bool:
        return self.runtime_default in DEFERRED_RUNTIME_DEFAULTS


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _topic_from_row(row: dict[str, str]) -> str:
    gene = row.get("gene", "").upper()
    text = " ".join(
        [
            row.get("trait", ""),
            row.get("category", ""),
            row.get("effect", ""),
            row.get("notes", ""),
        ]
    ).lower()
    if gene == "HFE" or "iron" in text or "hemochromatosis" in text:
        return "iron"
    if gene == "UGT1A1" or "bilirubin" in text or "gilbert" in text:
        return "bilirubin"
    if "celiac" in text or gene.startswith("HLA-"):
        return "celiac"
    if gene == "G6PD" or "hemolysis" in text:
        return "hemolysis"
    if gene == "SLCO1B1" or "statin" in text:
        return "statin"
    if gene == "CYP2C19":
        return "cyp2c19"
    if gene in {"CYP2C9", "VKORC1", "CYP4F2"} or "warfarin" in text:
        return "warfarin"
    if gene == "DPYD" or "fluoropyrimidine" in text:
        return "dpyd"
    if gene in {"TPMT", "NUDT15"} or "thiopurine" in text:
        return "thiopurine"
    if gene == "CYP3A5" or "tacrolimus" in text:
        return "tacrolimus"
    if gene == "CYP2B6":
        return "cyp2b6"
    if gene in {"RYR1", "CACNA1S"} or "malignant hyperthermia" in text:
        return "malignant_hyperthermia"
    if gene == "MT-RNR1" or "aminoglycoside" in text:
        return "aminoglycoside"
    if gene == "CFTR":
        return "cftr"
    if gene == "APOE":
        return "apoe"
    if gene.startswith("BRCA"):
        return "hereditary_cancer"
    if gene == "LPA" or "lipoprotein" in text or "lipid" in text:
        return "lipids"
    if gene in {"F5", "F2"} or "thrombophilia" in text:
        return "thrombosis"
    if gene == "SERPINA1" or "alpha1" in text or "alpha-1" in text:
        return "alpha1_antitrypsin"
    if gene == "HBB" or "hemoglobin" in text or "sickle" in text:
        return "hemoglobinopathy"
    return row.get("trait", "clinical_context").replace(" ", "_").lower() or "clinical_context"


def _finding_type_from_row(row: dict[str, str]) -> str:
    category = row.get("category", "").lower()
    scope = row.get("match_scope", "").lower()
    if "pgx" in category or "drug metabolism" in category or "cpic" in scope:
        return "pgx"
    if "anesthesia" in category:
        return "anesthesia_safety"
    if "sensitive" in category:
        return "sensitive_risk"
    if "susceptibility" in category:
        return "susceptibility_context"
    if "lab" in category:
        return "lab_modifier"
    if "carrier" in category:
        return "carrier_or_disease_context"
    if "hereditary" in category:
        return "hereditary_risk"
    return "clinical_context"


def _confidence_from_row(row: dict[str, str]) -> str:
    runtime = row.get("runtime_default", "")
    tier = row.get("reporting_tier", "")
    if runtime == "candidate_default_after_qc" and "expanded_pgx" in tier:
        return "medium"
    if runtime == "candidate_default_after_qc":
        return "medium"
    return "low"


def _label_from_row(row: dict[str, str], topic: str, finding_type: str) -> str:
    effect = _clean(row.get("effect"))
    gene = _clean(row.get("gene"))
    if effect and len(effect) <= 90:
        return f"{gene} {effect}"
    trait = _clean(row.get("trait")) or topic.replace("_", " ")
    suffix = "PGx" if finding_type == "pgx" else "context"
    return f"{gene} {trait} {suffix}"


def _summary_from_row(row: dict[str, str]) -> str:
    trait = _clean(row.get("trait"))
    gate = _clean(row.get("clinical_context_gate"))
    notes = _clean(row.get("notes"))
    pieces = []
    if trait:
        pieces.append(f"{trait} marker match is clinical context only.")
    if gate:
        pieces.append(gate)
    if notes:
        pieces.append(notes)
    return " ".join(pieces) or "Genomic marker match is clinical context only."


def _marker_from_row(row: dict[str, str]) -> MarkerKnowledge:
    topic = _topic_from_row(row)
    finding_type = _finding_type_from_row(row)
    output_tags = tuple(
        tag.strip()
        for tag in (row.get("output_tags") or "").replace(",", ";").split(";")
        if tag.strip()
    )
    confirmation = _clean(row.get("confirmation_tests"))
    context_gate = _clean(row.get("clinical_context_gate"))
    return MarkerKnowledge(
        rsid=row["rsid"].strip().lower(),
        gene=_clean(row.get("gene")),
        topic=topic,
        finding_type=finding_type,
        effect_allele=_clean(row.get("risk_allele")),
        label=_label_from_row(row, topic, finding_type),
        summary=_summary_from_row(row),
        evidence_gate=confirmation or context_gate or "Confirm clinically before action.",
        discussion_target=_clean(row.get("discussion_target")) or "clinician or genetic counselor",
        confidence=_confidence_from_row(row),
        clinical_reference=_clean(row.get("clinical_reference")),
        source_url=_clean(row.get("source_url")),
        confirmation_tests=confirmation,
        clinical_context_gate=context_gate,
        reporting_tier=_clean(row.get("reporting_tier")),
        runtime_default=_clean(row.get("runtime_default")) or "candidate_default_after_qc",
        match_scope=_clean(row.get("match_scope")),
        source_family=_clean(row.get("source_family")),
        output_tags=output_tags,
        notes=_clean(row.get("notes")),
        date_checked=_clean(row.get("date_checked")),
        catalog_version=_clean(row.get("catalog_version")),
    )


def load_marker_catalog() -> dict[str, MarkerKnowledge]:
    """Load the bundled release-pinned clinical marker catalog."""

    package = __package__ or "llm_health.genomics"
    with (resources.files(package) / CATALOG_RESOURCE).open("r", encoding="utf-8", newline="") as f:
        rows = csv.DictReader(f, delimiter="\t")
        markers = [_marker_from_row(row) for row in rows if row.get("rsid", "").startswith("rs")]
    return {marker.rsid: marker for marker in markers}


def markers_for_matching(
    *,
    include_specialty: bool = False,
    include_sensitive: bool = False,
    include_deferred: bool = False,
) -> dict[str, MarkerKnowledge]:
    """Return markers eligible for sparse storage under the requested consent tier."""

    allowed = set(DEFAULT_MATCH_RUNTIME_DEFAULTS)
    if include_deferred:
        allowed.update(DEFERRED_RUNTIME_DEFAULTS)
    if include_specialty:
        allowed.update(SPECIALTY_RUNTIME_DEFAULTS)
    if include_sensitive:
        allowed.update(SENSITIVE_RUNTIME_DEFAULTS)
    return {rsid: marker for rsid, marker in MARKERS.items() if marker.runtime_default in allowed}


def marker_count_by_runtime(markers: Iterable[MarkerKnowledge] | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for marker in markers or MARKERS.values():
        counts[marker.runtime_default] = counts.get(marker.runtime_default, 0) + 1
    return counts


MARKERS: dict[str, MarkerKnowledge] = load_marker_catalog()
MATCHABLE_MARKERS: dict[str, MarkerKnowledge] = markers_for_matching()

LAB_KEYWORDS: dict[str, tuple[str, ...]] = {
    "iron": ("ferritin", "transferrin", "saturation", "iron", "tibc", "alt", "ast"),
    "bilirubin": ("bilirubin", "alt", "ast", "ggt", "alkaline phosphatase"),
    "celiac": ("celiac", "transglutaminase", "ttg", "iga", "gliadin"),
    "hemolysis": ("hemoglobin", "reticulocyte", "ldh", "haptoglobin", "bilirubin"),
    "lipids": ("lipoprotein", "lp(a)", "apob", "ldl", "cholesterol", "triglyceride"),
    "thrombosis": ("thrombosis", "thromboembolism", "d-dimer", "apc resistance"),
    "alpha1_antitrypsin": ("alpha-1", "alpha 1", "aat", "serpina1", "emphysema"),
    "hemoglobinopathy": ("hemoglobin", "hgb", "sickle", "electrophoresis", "hplc"),
    "cftr": ("sweat chloride", "cftr", "cystic fibrosis"),
    "malignant_hyperthermia": ("malignant hyperthermia", "anesthesia", "rhabdomyolysis", "ck"),
}

MED_KEYWORDS: dict[str, tuple[str, ...]] = {
    "statin": ("statin", "simvastatin", "atorvastatin", "rosuvastatin", "pravastatin"),
    "cyp2c19": (
        "clopidogrel",
        "omeprazole",
        "pantoprazole",
        "escitalopram",
        "citalopram",
        "sertraline",
        "ssri",
    ),
    "warfarin": ("warfarin", "coumadin", "phenytoin", "nsaid", "ibuprofen", "celecoxib"),
    "dpyd": ("fluorouracil", "5-fu", "capecitabine", "fluoropyrimidine"),
    "thiopurine": ("azathioprine", "mercaptopurine", "thioguanine", "thiopurine"),
    "tacrolimus": ("tacrolimus", "transplant"),
    "cyp2b6": ("efavirenz", "bupropion", "methadone", "ketamine", "cyclophosphamide"),
    "bilirubin": ("irinotecan", "atazanavir", "nilotinib"),
    "hemolysis": ("dapsone", "primaquine", "rasburicase", "nitrofurantoin"),
    "aminoglycoside": ("gentamicin", "tobramycin", "amikacin", "aminoglycoside"),
}

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "iron": ("hemochromatosis", "iron overload", "hfe", "ferritin"),
    "bilirubin": ("gilbert", "bilirubin", "jaundice"),
    "celiac": ("celiac", "gluten", "autoimmune"),
    "hemolysis": ("hemolysis", "hemolytic", "g6pd", "jaundice", "anemia"),
    "statin": ("statin", "myopathy", "rhabdomyolysis"),
    "cyp2c19": ("clopidogrel", "drug reaction", "poor metabolizer", "ultrarapid"),
    "warfarin": ("warfarin", "coumadin", "bleeding", "clot"),
    "dpyd": ("fluoropyrimidine", "5-fu", "capecitabine", "dpyd"),
    "thiopurine": ("thiopurine", "azathioprine", "mercaptopurine", "tpmt", "nudt15"),
    "lipids": ("lipoprotein", "lp(a)", "cholesterol", "heart attack", "stroke"),
    "thrombosis": ("factor v", "prothrombin", "clot", "thrombosis", "embolism"),
    "apoe": ("apoe", "alzheimer", "dementia", "hyperlipoproteinemia"),
    "hereditary_cancer": ("brca", "breast cancer", "ovarian cancer", "pancreatic cancer"),
    "alpha1_antitrypsin": ("alpha-1", "alpha 1", "emphysema", "liver disease"),
    "hemoglobinopathy": ("sickle", "hemoglobin", "thalassemia"),
    "malignant_hyperthermia": ("malignant hyperthermia", "anesthesia reaction"),
}
