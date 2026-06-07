# Changelog

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
