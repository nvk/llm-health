# Architecture

`llm-health` is a health intelligence layer, not a single dashboard.

```text
new source / user fact / external data sync
        ↓
source intake + privacy guard
        ↓
staging extraction candidates
        ↓
QA + canonical observation commit
        ↓
NewResultEvent
        ↓
quick review cards + diagnostic gap cards
        ↓
deep research queue when interest score is high
        ↓
claim cards / protocol cards / output packets
```

## Layers

| Layer | Purpose |
|---|---|
| Core models | Profiles, observations, source batches, review events, cards, gaps, research jobs. |
| Privacy guard | Blocks raw paths, filenames, obvious identifiers, and non-alias profile leakage. |
| Store | Local JSONL now; DuckDB/Parquet and wiki adapters later. |
| Review engine | Fast deterministic summary and trigger detection after each ingest. |
| Gap engine | Converts unresolved patterns into test/context candidates. |
| Least-harm engine | Represents watchful waiting, home remedy, symptom tolerance, medication collateral review, and preventive-protocol review. |
| Research engine | Queues bounded literature/paper/product/protocol research. |
| Agent adapters | `@health`, `/health`, CLI, Codex skill, Claude commands, MCP later. |

## Principle

LLMs should discover and explain possibilities, but durable outputs must be typed artifacts with
source links, evidence lanes, and uncertainty.
