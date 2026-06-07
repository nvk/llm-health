# Changelog

## 0.0.18 - 2026-06-07

- Added superseded-pending semantics in the Assessment UI so old pending source rows stop counting as active once a later numeric result exists.
- Added source badges/CSV fields showing pending rows that were resulted by later follow-up.

## 0.0.17 - 2026-06-07

- Fixed normalization QA edge cases for CBC differential percent rows, nucleated RBC counts, and Spanish/Greek thyroid unit symbols.

## 0.0.16 - 2026-06-07

- Expanded Assessment unit normalization for common CBC, thyroid, vitals, MCHC, and ceruloplasmin unit aliases.
- Treated pH, BMI, and specific gravity as unitless so QA warnings focus on actual missing-unit risks.

## 0.0.15 - 2026-06-07

- Added Assessment export language/unit normalization so charts and source rows prefer English display fields and canonical units.
- Added normalization QA issues for translated rows, approved conversions, missing units, and mixed display units.
- Added v3 UI normalization QA cards, source-row focus, QA badges, and CSV fields.

## 0.0.14 - 2026-06-07

- Added resolved-flag semantics to the Assessment board so older abnormal source flags are demoted when later comparable normal follow-up exists.
- Added active vs resolved flag counts, source-row focus, chart badges, muted resolved dots, and CSV fields.

## 0.0.13 - 2026-06-07

- Added `health family` alias-only kinship graph and family-history commands.
- Added family-history, hereditary-risk, household-context, and family-pattern visible tags for kinship-aware notes.
- Added family service routes, registry metadata, docs, recipes, agent-plugin guidance, and release tests.

## 0.0.12 - 2026-06-07

- Added `health operator` visible runtime with draft/list/show/finalize/traces subcommands.
- Added operator draft and fingerprint-first audit trace HUB collections so agent workflows can show a plan before downstream writes.
- Added operator runtime docs, recipes, registry metadata, service route exposure, agent-template instructions, and lifecycle tests.

## 0.0.11 - 2026-06-07

- Added `health capabilities` with human and JSON feature maps for commands, modules, dependencies, privacy contracts, tests, and docs.
- Added `health deid extract|preview|apply` with a local regex de-identification adapter, redacted-only staging, and synthetic privacy tests.
- Added `health service --local --smoke` plus an optional localhost-only FastAPI/uvicorn service skeleton for future UI/chat integrations.
- Added feature-map, recipes, and open medical UX lessons docs, and updated agent templates for the new surfaces.

## 0.0.10 - 2026-06-07

- Added context-aware overlay groups: Smart overlay, Current domain, Flagged first, Recent movement, Core markers, and Context only.
- Made overlay defaults less noisy by switching first-time overlay views to 18mo and auto-picking context plus high-signal/flagged/recent markers.
- Improved stack grouping defaults so the most useful/flagged domains open first and group headers show flags and latest dates.

## 0.0.9 - 2026-06-07

- Removed the decorative hero swoop from the Assessment board.
- Fixed review badge contrast so status labels use placement-aware background/text colors in light and dark themes.

## 0.0.8 - 2026-06-07

- Tightened the Assessment board visual system with squarer corners, lower shadows, warm paper surfaces, and subtle Basecamp-like texture.
- Replaced raw enum-looking tag labels in the UI with readable badges while preserving the underlying durable tags.

## 0.0.7 - 2026-06-07

- Fixed the packaged Assessment board opening blank from `file://` in Chrome/Safari by using a deferred classic bundle script and removing CORS-only asset attributes.
- Added a static contract test so future frontend builds remain direct-file-open compatible.

## 0.0.6 - 2026-06-07

- Replaced the exported Assessment static dashboard with a prebuilt React + Mantine + Recharts board.
- Added polished card, tab, source-table, domain-map, overlay/stacked timeline, context-overlay, light/dark, and bookmarkable-state UX.
- Kept the Python export flow local-first: `health ui` still writes de-identified `data.js` plus static assets into the configured HUB.
- Added release tests for the v3 framework bundle and static privacy contract.

## 0.0.5 - 2026-06-07

- Added `health config wiki-root <path>` so users can save the de-identified health-assessments wiki root once.
- Added `health ui` to regenerate the Assessment v2 static dashboard into `<HUB>/v2-web/` and open it automatically.
- Added `health ui --no-open` and `--output <dir>` for scripted refreshes and custom export locations.
- Updated agent/plugin instructions and docs so Claude/Codex/OpenCode can guide users to the automated UI flow.

## 0.0.4 - 2026-06-07

- Trimmed Assessment v2 static UI chrome by removing the non-actionable workflow rail and shortening repeated helper copy.
- Made top profile/status chips clickable: profile opens review, plotted-capable jumps to timelines, source flags/pending jump to focused source rows.
- Added compact source row focus controls for all, flags, pending, and numeric rows.
- Made domain map cards clickable so they jump directly to the matching category timelines.

## 0.0.3 - 2026-06-07

- Added regression coverage for alias-only profile enrollment, default profile merging, and profile upserts.
- Hardened v2 static exports so malformed or unsafe enrolled HUB profiles are skipped before entering `data.js`.
- Filtered invalid canonical CSV profile IDs from v2 static export observations, reports, and wearable rows.
- Kept release/privacy gates green after the autoresearch quality pass.

## 0.0.2 - 2026-06-07

- Added review-board UX pass for the packaged v2 static dashboard: own-risk shell, review cards, domain map, view brief, clearer flag/pending semantics, and dark amber theme fixes.
- Added dynamic profile selectors in the v2 static dashboard, including alias-only zero-data enrolled profiles from the llm-health HUB.
- Added release tests for v2 static UI contracts and enrolled-profile export behavior.
- Tightened v2 upstream compatibility and release packaging so plugin template cache files are not shipped.

## 0.0.1 - 2026-06-06

- Initial `llm-health` package scaffold.
- Added dependency-light core CLI and JSONL private store.
- Added event-driven quick review and smart deep-research queue triggers.
- Added diagnostic-gap/test-candidate cards.
- Added least-harm, medication collateral-damage, and preventive-protocol review models.
- Repackaged `health-assessment-v2` as `llm_health.assessment_v2` with optional `v2` dependencies.
- Added `health sync-v2` bridge for latest de-identified canonical Rod/Cara rows.
- Added Claude Code, Codex, OpenCode/Pi, and portable AGENTS agent surfaces plus marketplace files.
- Added explicit own-risk agreement/disclaimer gate for health-facing HUB commands.
- Added release privacy scan, wheel/sdist build verification, and clean-wheel smoke testing.
