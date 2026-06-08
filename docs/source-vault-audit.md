# Source vault and source audit

`llm-health` separates the safe de-identified HUB archive from optional raw-source handling.
The source vault is for private audit/re-ingestion of originals; normal `health archive create`
intentionally excludes it.

## Commands

```sh
health source-vault init
health source-vault add <file-or-folder> --wiki-root <health-assessments-topic-root>
health source-vault add <file-or-folder> --wiki-root <health-assessments-topic-root> --copy --accept-raw-storage
health source-vault list
health source-audit run --profile rod --focus medium
health source-audit report
```

## Privacy contract

The manifest stores only hashes, byte sizes, source type, alias profile, and de-identified
`source_id`. It does not store raw filesystem paths or raw filenames. When `--copy` is used, raw
bytes are copied into `source-vault/blobs/<sha256>` without extension. These blobs are not included
in normal de-identified HUB archives.

Use catalog-only mode when you only need proof that a raw file exists. Use `--copy` only when you
want the tool to run future multipass extraction/audit without needing the original folder mounted.

## Audit model

`health source-audit run` reviews current canonical lab rows and records:

- source-vault presence by de-identified `source_id`;
- medium-confidence rows;
- OCR/order/inference risk notes;
- simple medical consistency checks, currently bilirubin reconciliation and CBC hematocrit math;
- multipass extraction summaries for copied PDF blobs.

PDF extraction uses available local readers:

- `pdftotext -layout` and `pdftotext -raw` when Poppler is installed;
- optional Python readers when installed: `pypdf`, `pdfplumber`, and `PyMuPDF`.

Only summaries are stored: character counts, numeric-token counts, marker-hit counts, and agreement
scores. Extracted text is not persisted.
