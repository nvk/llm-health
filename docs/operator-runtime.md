# Visible operator runtime

The OpenMed Agent lesson worth borrowing is not an opaque chatbot. It is the visible operator loop:

```text
alias-safe intent
  -> typed plan
  -> deterministic local reads/tools
  -> draft artifact
  -> explicit finalize approval
  -> fingerprint-first audit trace
```

`llm-health` starts that loop with `health operator`.

## Commands

```sh
health operator draft --profile rod --intent "review latest liver trend"
health operator list --profile rod
health operator show --draft-id draft_<id>
health operator finalize --draft-id draft_<id> --approve
health operator traces --profile rod
```

## What draft creation does

Draft creation reads the local private HUB for the selected alias:

- enrolled profile existence;
- observations;
- self-reported context;
- quick-review cards;
- diagnostic gaps.

It then writes only two lifecycle artifacts:

- `operator_drafts.jsonl` — visible plan, counts, alias-safe intent, lifecycle status;
- `audit_traces.jsonl` — fingerprint-first trace metadata.

It does **not** finalize wiki writes, packet exports, self-report commits, protocols, or research
claims. Those need explicit later commands.

## Privacy contract

- The intent string is stored, so it must be alias-safe.
- Raw source paths, raw filenames, emails, legal names, and full birth dates are blocked by the same
  privacy guard as other durable artifacts.
- Audit traces store fingerprints and metadata, not raw source payloads.
- `finalize` changes lifecycle status only. It is not a hidden medical action, prescription, order,
  or wiki write.

## Why this matters

This gives agent/chat workflows a predictable shape: show the plan, show what was read, show what
would be written, and require approval before durable downstream outputs. It should become the common
wrapper for result reviews, research jobs, medication/protocol reviews, packet generation, and wiki
adapter writes.
