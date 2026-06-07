# Event-driven review

Every ingest should emit a `NewResultEvent`. The event fans out into two lanes.

## Lane 1: quick review

Always runs. It should complete quickly and answer:

1. What was added?
2. What changed vs prior data?
3. What is flagged, pending, missing, or QA-blocked?
4. What needs review now?
5. Which chart/source rows should be opened?

## Lane 2: deep research

Runs when the interest score crosses the configured threshold or the user explicitly asks.

Deep triggers include:

- new abnormal result;
- normal-to-abnormal or abnormal-to-normal transition;
- large marker velocity;
- repeated unresolved abnormality;
- new category/panel;
- profile context collision, such as supplement stack, Gilbert context, weight/activity change;
- medication/protocol exposure near a lab change;
- open claim/gap already waiting on this marker.

## Output artifacts

- `quick_review_cards`
- `review_queue_items`
- `diagnostic_gaps`
- `research_jobs`
- `claims_registry` entries later

The chat answer is a view of these artifacts, not the source of truth.
