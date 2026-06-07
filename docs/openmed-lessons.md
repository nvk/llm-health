# Open medical UX lessons for llm-health

The useful pattern to borrow is not a single screen; it is the workflow discipline:

1. **Start with the user goal, not a chart picker.** Surface review queue, gaps, and high-signal
   timelines before asking people to choose a raw metric.
2. **Keep provenance close.** Every claim should connect back to source rows, tags, and whether it is
   observed, derived, context, inference, or a QA issue.
3. **Make data quality visible.** Pending/non-numeric rows, source flags, missing ranges, and de-id
   staging issues should be first-class cards instead of hidden footnotes.
4. **Use progressive disclosure.** Casual review starts with short cards and timelines; expert review
   can drill into source rows, route metadata, and machine-readable payloads.
5. **Separate interfaces from engine contracts.** The CLI, static board, future local service, and
   agent chat should all read the same private HUB artifacts instead of each becoming its own data
   island.

For this release that translates into three concrete surfaces:

- `health capabilities` for a live feature map and agent-readable command registry.
- `health deid` for pre-HUB redaction/staging before raw dumps are admitted into workflows.
- `health service --local` for a small, localhost-only API contract that future polished UIs can use
  without reimplementing storage logic.
- `health operator` for visible plan -> draft -> explicit finalize -> audit-trace workflows, so
  chat/agent actions do not become opaque writes.
