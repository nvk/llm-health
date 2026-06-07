# Family history and kinship graph

`llm-health` supports an alias-only family graph so hereditary and household-context clues can affect
review questions, diagnostic gaps, test candidates, and future specialist routing without pretending
to diagnose genetics.

## Commands

```sh
health enroll --alias sol --birth-year 2018 --role child --accept-risk
health enroll --alias rod --birth-year 1983 --role adult --accept-risk
health family add --profile sol --relative rod --relation father --lineage paternal --shared-household yes
health family condition --profile rod --condition "Gilbert syndrome" --status believed --evidence context
health family tree --profile sol
health family history --profile rod
health family risks --profile sol
```

## Data collections

| Collection | Purpose |
|---|---|
| `family_relationships.jsonl` | Directed alias relationship edges such as child -> father. |
| `family_history_events.jsonl` | Alias-level reported/observed/believed/confirmed/absent conditions. |
| `hereditary_risk_notes.jsonl` | Generated family-pattern notes for review and follow-up questions. |

## Tags

Family support adds visible tags:

- `FAMILY_HISTORY`
- `HEREDITARY_RISK`
- `HOUSEHOLD_CONTEXT`
- `FAMILY_PATTERN`

These tags are context markers, not diagnoses.

## What it should infer

Good uses:

- A parent has believed Gilbert syndrome, so a child's future bilirubin flag should ask about
  direct/indirect fractionation before overcalling liver disease.
- Multiple close relatives have thyroid/autoimmune history, so thyroid/autoimmune context questions
  become more relevant.
- A household has exposure markers such as mercury/lead/mold, so household context is separated from
  inherited risk.
- Family history of early, bilateral, recurrent, or multi-relative cancers can raise a candidate
  genetic-counseling/testing question.

Bad uses:

- Do not infer that a child has a disease just because a parent has it.
- Do not mix household exposure with hereditary risk.
- Do not store legal names, full birth dates, source paths, or raw family documents.
- Do not make autonomous genetic-testing or screening orders.

## Privacy contract

Use aliases only. Family role words like father/mother/child are relationship labels, not profile IDs.
The profile aliases remain tokens such as `rod`, `cara`, `sol`, `abe`, or `lele`.

## Future integration

Family risk notes should eventually feed:

1. diagnostic-gap scoring;
2. test-battery priority;
3. specialist/category-agent routing;
4. chart annotations;
5. child-profile context and household exposure reviews.
