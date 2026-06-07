# Release checklist

Run from a virtual environment:

```sh
make install-v2
make verify
make package
```

Additional manual smoke:

```sh
health doctor
health agreement show
SMOKE_STORE=$(mktemp -d)
health init --store "$SMOKE_STORE" --accept-risk
health plugin-paths
health plugin-paths --kind opencode
health plugin-paths --kind agents
health sync-v2 --wiki-root "$HEALTH_WIKI_ROOT" --profile all --deep smart
health-v2 doctor
HEALTH_DATA_DIR=$(mktemp -d) HEALTH_DUCKDB_PATH=$(mktemp -u).duckdb health-v2 build --from-wiki
```

Release blockers:

- privacy scan fails;
- Codex plugin validation fails;
- generated wheel lacks `llm_health.assessment_v2`;
- generated wheel lacks Claude/Codex/OpenCode/portable agent templates;
- own-risk agreement gate can be bypassed by profile-specific health commands;
- clean wheel smoke fails;
- local Rod/Cara de-identified smoke prints or stores source paths/raw filenames.
