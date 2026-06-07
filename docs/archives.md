# HUB archives

`llm-health` can create a compressed snapshot of the resolved private HUB for future reference:

```sh
health archive create
health archive list
health archive verify <archive.tar.gz>
```

Archives are written to `<HUB>/archives/` by default and include an `archive-manifest.json` with
member checksums, package version, and skipped-file notes.

## Privacy contract

The archive command is a **de-identified HUB snapshot**, not a raw-source backup. It allowlists known
HUB artifacts and skips unknown root folders so future raw/source-vault directories are not packed by
accident. It also byte-scans candidates, including binary DuckDB/Parquet files, and skips files that
contain blocked raw-source markers such as local paths, raw PDF/XML/CDA/XLS/XLSX filenames, provider
alias fields, source-file alias fields, or email-looking text.

Use `--strict` when you want the command to fail instead of skipping privacy-failing files:

```sh
health archive create --strict
```

Useful trims:

```sh
health archive create --no-ui        # skip generated static dashboard files
health archive create --no-v2-data   # skip generated DuckDB/Parquet analytics files
health archive create --json         # machine-readable manifest summary
```

Raw PDFs, Apple export XML/CDA, original filenames, and local source paths should remain outside the
HUB or in a separate explicitly managed source vault. The default archive does not try to preserve
raw originals.
