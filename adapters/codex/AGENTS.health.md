# Codex adapter

The Codex plugin source lives at:

```text
plugins/llm-health/
```

Once the public repo is published, install as a Codex marketplace plugin:

```sh
codex plugin marketplace add nvk/llm-health
```

Then use `@health` naturally:

```text
@health review alex
@health close gaps for alex
@health what changed in the latest labs?
@health run toxins_exposures consult for mercury
```

Codex plugins package skills, not Claude-style slash commands. Treat `/health` examples as shorthand
for the same workflow through `@health` or natural language. Use aliases only and never write raw
source paths or legal identifiers.

Before profile-specific work, ensure `health agreement status` is accepted for the selected HUB. If not, run `health agreement show` and ask the user to accept with `health agreement accept --own-risk`.
