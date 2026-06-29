# llm-health recipes

Copy/paste flows for common local-first work. All health-facing commands are own-risk, local, and
alias-only.

## First install / first HUB

```sh
health agreement show
health config hub-path ~/health --init --accept-risk
health doctor
health capabilities
```

## Enroll aliases and gather context

```sh
health enroll --alias alex --birth-year 1983 --role adult --accept-risk
health profiles
health data-wishlist
health dr-visit --profile alex --cadence onboarding
health dr-visit --profile alex --cadence monthly --sources
```

## Add one de-identified result and review it

```sh
health ingest-note --profile alex --marker ALT --value 42 --unit U/L --category liver --flag normal
health result --profile alex --marker ALT
health review --profile alex
health close-gaps --profile alex
```

## De-identify text before staging

Preview first:

```sh
health deid preview ./synthetic-note.txt --accept-risk
```

Extract entity metadata without raw values:

```sh
health deid extract ./synthetic-note.txt --accept-risk --json
```

Stage redacted text only:

```sh
health deid apply ./synthetic-note.txt --staging-only --accept-risk
```

Output paths are relative to the private HUB, for example `deid-staging/deid_<hash>.txt`. Raw source
paths and raw file names are not written into the staged metadata.

## Export and open the static Assessment board

```sh
health config wiki-root <deidentified-health-assessments-wiki-root>
health ui
```

Use `--no-open` for automation:

```sh
health ui --no-open --output ~/health/v2-web
```


## Import raw genotype context

Use a local raw genotype text file only after accepting the extra genetic-risk prompt. The file path
is not stored; the source is fingerprinted and dense calls stay under the private HUB.

```sh
health genomics import ./synthetic-genotype.txt --profile alex --accept-genetic-risk
health genomics qc --profile alex
health genomics annotate --profile alex
health genomics crossref --profile alex
health genomics pgx --profile alex
health genomics confirm-list --profile alex
```

Genomics output is confirmation-first context, not diagnosis or medication advice.

## Smoke-test the future local API

```sh
health service --local --smoke --accept-risk
```

If the optional service extra is installed, start the localhost API:

```sh
pip install 'llm-health[service]'
health service --local --host 127.0.0.1 --port 8765 --accept-risk
```

## Ask for test candidates and research queues

```sh
health test-battery --profile alex --scope core --sources
health test-battery --profile alex --category gaps
health test-battery --profile alex --scope expanded --queue-research
health plan-research --profile alex
```



## Add family history and hereditary context

```sh
health enroll --alias sol --birth-year 2018 --role child --accept-risk
health family add --profile sol --relative rod --relation father --lineage paternal --shared-household yes
health family add --profile sol --relative cara --relation mother --lineage maternal --shared-household yes
health family condition --profile rod --condition "Gilbert syndrome" --status believed --evidence context
health family tree --profile sol
health family risks --profile sol
```

Family risk notes are tagged `FAMILY_HISTORY`, `HEREDITARY_RISK`, `HOUSEHOLD_CONTEXT`, or
`FAMILY_PATTERN` where appropriate. They are review prompts, not diagnoses.

## Use the visible operator runtime

Draft first; finalize only after reviewing the visible plan:

```sh
health operator draft --profile alex --intent "review latest liver trend"
health operator list --profile alex
health operator show --draft-id draft_<id>
health operator finalize --draft-id draft_<id> --approve
health operator traces --profile alex
```

Draft/finalize stores lifecycle artifacts and fingerprint traces. It does not silently write wiki
notes, protocols, packets, or self-reports.

## Run broad category agents

```sh
health specialists --short
health consult --profile alex --specialist auto
health consult --profile alex --specialist internal_medicine --topic "baseline synthesis"
health specialist-notes --profile alex
```
