# HUB setup

`llm-health` supports a default HUB/store path similar to `llm-wiki`.

Config file:

```text
~/.config/llm-health/config.json
```

Shape:

```json
{
  "hub_path": "~/health"
}
```

Set and initialize it:

```sh
health agreement show
health config hub-path ~/health --init --accept-risk
health doctor
```

Resolution order for commands with a `--store` option:

1. explicit `--store`;
2. `LLM_HEALTH_HUB` environment variable;
3. `~/.config/llm-health/config.json` `hub_path`;
4. local `.llm-health/` fallback.

The HUB is a private local health store. Do not commit it. Initializing or using health-facing
commands requires an own-risk acceptance stored as `agreement.json` in that HUB.
