# Genomics and SNP cross-reference layer

`health genomics` is a local-first scaffold for using SNP/genotype data as context in
llm-health. It keeps genotype matches as context for review and follow-up planning. It scans raw genotype text locally by fingerprint, stores only matched SNP findings by default, runs QC, and
creates confirmation-first review cards that can cross-reference labs, medication context, and family
history.

## Privacy contract

Genetic data is unusually sensitive: it identifies the profile, implicates relatives, and can have
family, emotional, insurance, and long-lived privacy consequences. The genomics layer therefore uses
stricter defaults:

- profile-specific commands require the normal own-risk agreement;
- imports also require `--accept-genetic-risk`;
- raw genetic file paths and file names are never stored;
- source summaries store a file hash, source kind, marker counts, call-rate fields, and QC flags;
- dense genome-wide calls are not stored by default; only matched allowlist SNP calls plus
  confirmation-first findings are persisted;
- outputs must frame genetic context as review notes and prompt confirmation before decision-relevant use.

## Commands

```sh
health genomics ui --profile alex
health genomics import ./synthetic-genotype.txt --profile alex --accept-genetic-risk
health genomics import ./synthetic-genotype.txt --profile alex --accept-genetic-risk --include-research-markers
health genomics status --profile alex
health genomics qc --profile alex
health genomics annotate --profile alex
health genomics crossref --profile alex
health genomics pgx --profile alex
health genomics explain rs1800562 --profile alex
health genomics confirm-list --profile alex
```

`import`/GUI matching currently supports simple 23andMe/Ancestry-like rows:

```text
rsid chromosome position genotype
rs1800562 6 26092913 AG
```

Comment lines beginning with `#` are used only for source-kind/build hints such as 23andMe or
GRCh37/GRCh38. The parser is dependency-free so synthetic fixtures and first-run imports work before
installing heavier bioinformatics tools.

The GUI is started with `health genomics ui`. It binds to localhost by default, opens a browser
file-picker page, reads the selected text in the browser, runs matching locally, and persists only
matched SNP findings by default. It does not send the browser filename/path or store dense
genome-wide calls.

## What the scaffold does today

- Parses raw genotype text rows locally and stores only matched allowlist `VariantCall` artifacts by
  default.
- Stores `GenomicSource` summaries, sparse matched allowlist SNP calls, and review findings under the
  private HUB; dense genome-wide calls require an explicit local-only override.
- Reports QC notes for low call rate, duplicate markers, unknown genome build, complex/indel-like
  calls, and consumer/unconfirmed sources.
- Provides a release-pinned bundled marker catalog with 916 rows: 786 CPIC/ClinPGx
  allele-definition markers across 17 genes, 19 manually reviewed clinical sentinel rows, and
  111 opt-in neurodevelopmental GWAS research rows covering dyslexia, ADHD, and direct
  autism-spectrum lead SNPs.
- Uses only the `candidate_default_after_qc` subset for normal sparse matching by default
  (437 markers in this release). Sensitive, specialty, and deferred markers stay out of default
  storage until dedicated opt-in/confirmation workflows exist.
- Provides opt-in research trait lists such as dyslexia, ADHD, and direct autism-spectrum GWAS
  lead-SNP lists. These are excluded from default matching and are summarized as separate
  non-diagnostic research-context cards, not as individual clinical findings or a polygenic
  risk score.
- Creates `GenomicInference` cards tagged as review artifacts with required confirmation gates.
- Provides `health genomics ui`, a localhost-only browser SNP matching panel with a file picker, profile
  selector, genetic-risk checkbox, QC summary, and cross-reference cards.
- Exposes local service routes for `/health/ui/`, `/genomics/ui`, `/genomics/import-text`,
  `/genomics/sources`, `/genomics/qc`, `/genomics/crossrefs`, and `/genomics/crossrefs/run`.

## Deliberate limits

This release intentionally does not fetch live ClinVar/dbSNP/ClinGen/CPIC/PGS data at runtime.
`annotate` uses the bundled release-pinned marker catalog and prints that no external calls were
made. Full VCF import, PharmCAT integration, PGS Catalog scoring, GA4GH VRS identifiers, and FHIR
Genomics exports should be added after the privacy, QC, and confirmation-first contracts are stable.

## Bundled clinical marker catalog

The packaged catalog lives under `llm_health.genomics` package data and is loaded without network
access. It includes source-family labels, source URLs for review, clinical context gates,
confirmation-test wording, reporting tiers, and runtime-default flags.

Runtime tiers:

- `candidate_default_after_qc`: included in normal match-only imports.
- `defer_until_context`, `defer_until_strand_fixture`, `defer_until_clinvar_validation`: documented
  but not stored by default.
- `specialty_opt_in`: specialty contexts such as malignant-hyperthermia anesthesia safety, CFTR, and
  mitochondrial aminoglycoside/hearing-loss markers; not default.
- `sensitive_opt_in` / `sensitive_opt_in_gene_panel_preferred`: APOE and selected BRCA-style
  sensitive contexts; not default and never a reassurance screen.
- `research_opt_in`: research trait marker lists such as dyslexia, ADHD, and autism-spectrum GWAS
  lead SNPs; not default, not diagnostic, and aggregated in review output to avoid
  over-interpreting individual SNPs.

Rows are clinical-review prompts, not diagnoses. Missing rows or absent array coverage never means
low risk.

## Review semantics

Cards are meant for questions like:

- “Does this HFE context make the existing ferritin/iron pattern worth confirming?”
- “Does this SLCO1B1 marker matter for a statin discussion with a clinician or pharmacist?”
- “Is this UGT1A1 proxy relevant to an isolated bilirubin pattern?”

They are **not** answers to:

- “Do I have this disease?”
- “Should I take or stop this medication?”
- “Should relatives act on this raw genotype result?”

High-impact genetic findings should be confirmed using clinical-grade testing and interpreted with a
qualified clinician, pharmacist, or genetic counselor.
