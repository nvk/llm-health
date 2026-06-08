# PDF reports

`health report` creates local, de-identified PDFs for two audiences:

- **doctor**: concise clinician brief with active source flags, pending/nonnumeric rows,
  diagnostic gaps, context/family notes, mini-trends, and a recent source-row appendix.
- **family**: plain-language summary with what to know first, watch items, questions to ask,
  family/history context, recent results, and small trend visuals.

The reports are generated with a dependency-free local PDF writer. They are not medical advice,
not a diagnosis, not a prescription, and not an order. They are discussion packets; verify against
original source records before decisions.

## Examples

```sh
# Create both report types under <HUB>/reports/. If a wiki root is configured,
# the report includes the full v2 canonical history, not just latest synced rows.
health report --profile rod --audience both

# Clinician packet only, limited to the last 18 months
health report --profile rod --audience doctor --range 18mo

# Plain-language family packet in a chosen folder
health report --profile cara --audience family --output-dir ~/Desktop/health-packets

# Exact output path for a single-audience export
health report --profile rod --audience doctor --output ~/Desktop/rod-doctor-packet.pdf
```

## Privacy behavior

- Uses enrolled profile aliases only.
- Uses the configured health-assessments wiki root when available so reports match the GUI history.
- Does not export raw source filenames, source paths, legal names, full birth dates, emails, or raw
  Apple device/source names.
- Source-vault references are summarized as counts and hash/source-id status only.
- Pending rows are shown as questions, not numeric evidence.
- Older source flags are demoted when a later comparable normal row exists.

## Audience split

Doctor-facing PDFs favor compact tables and source ranges. Family-facing PDFs favor prose and
questions. Both include the own-risk note and keep derived/context claims visibly separate from
observed source rows.
