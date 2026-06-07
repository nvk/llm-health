# health-assessment-v2 repackaging

`health-assessment-v2` is now distributed inside `llm-health` as:

```python
llm_health.assessment_v2
```

The original CLI remains available as the console script:

```sh
health-v2 doctor
health-v2 build --from-wiki
health-v2 export-web --output data/v2-web

# Package-level one-command flow after configuring the HUB and wiki root:
health config wiki-root <health-assessments-topic-root>
health ui
```

The exported static dashboard uses prebuilt React + Mantine + Recharts assets copied from the wheel into
the local HUB. The older vanilla static files remain in the package only as a compatibility fallback; no
Node runtime is required for users.

The dependency-light analytics/static-export dependency set lives behind `v2-core`:

```sh
pip install '.[v2-core]'
```

The full live Panel dashboard stack lives behind `v2`:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install '.[dev,v2]'
```

## Privacy boundary

Only code and static UI assets are packaged. Releases must not include:

- raw PDFs or medical records;
- Apple Health XML/CDA exports;
- generated DuckDB/Parquet/CSV private data;
- source filesystem paths;
- legal names, full birth dates, health numbers, emails, or raw Apple source/device names.

The bridge command imports only sanitized de-identified canonical rows into the local private store:

```sh
health sync-v2 --wiki-root "$HEALTH_WIKI_ROOT" --profile rod
```

It stores marker/category/value/date/source-id only and intentionally drops source-file aliases.
