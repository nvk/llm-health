# Homebrew install

Public install target:

```sh
brew tap nvk/tap
brew install llm-health
```

Then initialize a private HUB/store. Use any local or synced directory that is private to you:

```sh
health agreement show
health config hub-path ~/health --init --accept-risk
health doctor
```

Optional: import latest de-identified rows from a compatible health-assessment wiki export:

```sh
health sync-v2 --wiki-root <health-assessments-topic-root> --profile all
health review --profile <alias>
health close-gaps --profile <alias>
```

The `--accept-risk` flag records one local own-risk agreement for that HUB. To inspect or accept
separately, use `health agreement show` and `health agreement accept --own-risk`.


## Automated local UI

Configure the private HUB and wiki root once:

```sh
health config hub-path ~/health --init --accept-risk
health config wiki-root <health-assessments-topic-root>
```

Then regenerate and open the static Assessment v2 UI with:

```sh
health ui
```

By default this writes to `<resolved HUB>/v2-web/` and opens `index.html`. For automation, use
`health ui --no-open`; for custom output, use `health ui --output <dir>`.

Formula behavior:

- Installs `health`, `llm-health`, and `health-v2`.
- Installs the package CLI plus `v2-core` analytics/static-export support so `health-v2 doctor`,
  `health-v2 build`, `health-v2 sync`, and `health-v2 export-web` are available.
- Does not install the full live Panel dashboard stack by default; use a Python/dev install with
  `llm-health[v2]` when `health-v2 serve` is needed.
- Release formula URL should point at the GitHub release sdist:
  `https://github.com/nvk/llm-health/releases/download/vX.Y.Z/llm_health-X.Y.Z.tar.gz`.

For local formula testing before a public release, place `Formula/llm-health.rb` in the active tap
checkout returned by `brew --repo nvk/tap`, use a `file://` URL to `dist/`, and update `sha256` from
`shasum -a 256 dist/llm_health-*.tar.gz`.
