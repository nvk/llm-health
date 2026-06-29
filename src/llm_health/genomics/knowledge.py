from __future__ import annotations

from dataclasses import dataclass


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


MARKERS: dict[str, MarkerKnowledge] = {
    "rs1800562": MarkerKnowledge(
        rsid="rs1800562",
        gene="HFE",
        topic="iron",
        finding_type="lab_modifier",
        effect_allele="A",
        label="HFE C282Y iron-overload context",
        summary=(
            "HFE C282Y context can be relevant when ferritin, transferrin saturation, "
            "iron studies, liver markers, or family history already raise questions."
        ),
        evidence_gate="Confirm with clinical-grade testing and iron studies before action.",
    ),
    "rs1799945": MarkerKnowledge(
        rsid="rs1799945",
        gene="HFE",
        topic="iron",
        finding_type="lab_modifier",
        effect_allele="G",
        label="HFE H63D iron-overload context",
        summary=(
            "HFE H63D context is usually interpreted with C282Y status and iron labs, "
            "not as a standalone diagnosis."
        ),
        evidence_gate="Confirm clinically if iron overload is suspected.",
    ),
    "rs6742078": MarkerKnowledge(
        rsid="rs6742078",
        gene="UGT1A1",
        topic="bilirubin",
        finding_type="lab_modifier",
        effect_allele="T",
        label="UGT1A1 bilirubin/Gilbert-pattern context",
        summary=(
            "UGT1A1-linked bilirubin context can help frame isolated bilirubin patterns, "
            "but proxy SNPs are not diagnostic."
        ),
        evidence_gate="Use bilirubin fractions and clinician review before conclusion.",
    ),
    "rs2187668": MarkerKnowledge(
        rsid="rs2187668",
        gene="HLA-DQA1/HLA-DQB1",
        topic="celiac",
        finding_type="lab_modifier",
        effect_allele="T",
        label="HLA-DQ2.5 celiac-risk tag context",
        summary=(
            "HLA-DQ context can support or weaken celiac workups, but diagnosis depends "
            "on symptoms, serology, diet state, and clinical evaluation."
        ),
        evidence_gate="Confirm with appropriate serology or clinical HLA testing if relevant.",
    ),
    "rs1050828": MarkerKnowledge(
        rsid="rs1050828",
        gene="G6PD",
        topic="hemolysis",
        finding_type="lab_modifier",
        effect_allele="T",
        label="G6PD hemolysis-risk context",
        summary=(
            "G6PD context can matter for anemia/hemolysis patterns and medication or "
            "food exposures, but DTC calls require confirmation."
        ),
        evidence_gate="Confirm with clinical testing before medication or diet decisions.",
    ),
    "rs4149056": MarkerKnowledge(
        rsid="rs4149056",
        gene="SLCO1B1",
        topic="statin",
        finding_type="pgx",
        effect_allele="C",
        label="SLCO1B1 statin myopathy PGx context",
        summary=(
            "SLCO1B1 context can affect statin adverse-effect discussions, especially "
            "with simvastatin-class exposure."
        ),
        evidence_gate="Use CPIC/PharmGKB-style PGx review; do not change dose autonomously.",
        discussion_target="clinician or pharmacist",
        confidence="medium",
    ),
    "rs4244285": MarkerKnowledge(
        rsid="rs4244285",
        gene="CYP2C19",
        topic="cyp2c19",
        finding_type="pgx",
        effect_allele="A",
        label="CYP2C19 no-function PGx context",
        summary=(
            "CYP2C19 no-function context can affect drug-response discussions for some "
            "antiplatelet, acid-suppression, and psychiatric medications."
        ),
        evidence_gate="Use a dedicated PGx report or PharmCAT/CPIC-style review before action.",
        discussion_target="clinician or pharmacist",
        confidence="medium",
    ),
    "rs12248560": MarkerKnowledge(
        rsid="rs12248560",
        gene="CYP2C19",
        topic="cyp2c19",
        finding_type="pgx",
        effect_allele="T",
        label="CYP2C19 increased-function PGx context",
        summary=(
            "CYP2C19 increased-function context can matter for medication response, "
            "but should be interpreted with full diplotype/phenotype tooling."
        ),
        evidence_gate="Use a dedicated PGx report or PharmCAT/CPIC-style review before action.",
        discussion_target="clinician or pharmacist",
        confidence="medium",
    ),
}

LAB_KEYWORDS: dict[str, tuple[str, ...]] = {
    "iron": ("ferritin", "transferrin", "saturation", "iron", "tibc", "alt", "ast"),
    "bilirubin": ("bilirubin", "alt", "ast", "ggt", "alkaline phosphatase"),
    "celiac": ("celiac", "transglutaminase", "ttg", "iga", "gliadin"),
    "hemolysis": ("hemoglobin", "reticulocyte", "ldh", "haptoglobin", "bilirubin"),
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
}

FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "iron": ("hemochromatosis", "iron overload", "hfe", "ferritin"),
    "bilirubin": ("gilbert", "bilirubin", "jaundice"),
    "celiac": ("celiac", "gluten", "autoimmune"),
    "hemolysis": ("hemolysis", "hemolytic", "g6pd", "jaundice", "anemia"),
    "statin": ("statin", "myopathy", "rhabdomyolysis"),
    "cyp2c19": ("clopidogrel", "drug reaction", "poor metabolizer", "ultrarapid"),
}
