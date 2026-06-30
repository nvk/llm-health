from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_health.core.privacy import assert_safe_payload, validate_profile_alias

from .models import GenomicInference, GenomicSource, VariantCall


class GenomicsStore:
    """Path-free local genomics artifact store under the private llm-health HUB."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root) / "genomics"

    def init(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "variants").mkdir(exist_ok=True)
        for name in ["sources.jsonl", "inferences.jsonl"]:
            (self.root / name).touch(exist_ok=True)
        manifest = self.root / "manifest.json"
        if not manifest.exists():
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "llm-health-genomics-v0",
                        "privacy": (
                            "raw genetic files are not stored here; source paths omitted; "
                            "stored variant calls are matched allowlist only by default"
                        ),
                        "review_note": "genomic artifacts are context notes",
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                assert_safe_payload(row)
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    def _upsert(self, path: Path, row: dict[str, Any], key: str) -> bool:
        self.init()
        assert_safe_payload(row)
        key_value = row.get(key)
        rows = self._read_jsonl(path)
        changed = False
        found = False
        out: list[dict[str, Any]] = []
        for existing in rows:
            if existing.get(key) == key_value:
                found = True
                changed = changed or existing != row
                out.append(row)
            else:
                out.append(existing)
        if not found:
            changed = True
            out.append(row)
        if changed:
            self._write_jsonl(path, out)
        return changed

    @property
    def sources_path(self) -> Path:
        return self.root / "sources.jsonl"

    @property
    def inferences_path(self) -> Path:
        return self.root / "inferences.jsonl"

    def variant_path(self, source_id: str) -> Path:
        safe = source_id.replace("/", "_").replace("..", "_")
        return self.root / "variants" / f"{safe}.jsonl"

    def upsert_source(self, source: GenomicSource) -> None:
        self._upsert(self.sources_path, source.to_dict(), "source_id")

    def sources(self, profile_id: str | None = None) -> list[GenomicSource]:
        self.init()
        profile = validate_profile_alias(profile_id) if profile_id else None
        rows = self._read_jsonl(self.sources_path)
        if profile:
            rows = [row for row in rows if row.get("profile_id") == profile]
        return [GenomicSource.from_dict(row) for row in rows]

    def replace_variants(self, source_id: str, variants: list[VariantCall]) -> None:
        self.init()
        self._write_jsonl(self.variant_path(source_id), [variant.to_dict() for variant in variants])

    def variants(
        self,
        profile_id: str | None = None,
        source_id: str | None = None,
    ) -> list[VariantCall]:
        self.init()
        profile = validate_profile_alias(profile_id) if profile_id else None
        paths = (
            [self.variant_path(source_id)]
            if source_id
            else sorted((self.root / "variants").glob("*.jsonl"))
        )
        rows: list[dict[str, Any]] = []
        for path in paths:
            rows.extend(self._read_jsonl(path))
        if profile:
            rows = [row for row in rows if row.get("profile_id") == profile]
        return [VariantCall.from_dict(row) for row in rows]

    def variants_by_rsid(self, profile_id: str, rsid: str) -> list[VariantCall]:
        target = rsid.strip().lower()
        return [variant for variant in self.variants(profile_id) if variant.rsid == target]

    def upsert_inference(self, inference: GenomicInference) -> bool:
        return self._upsert(self.inferences_path, inference.to_dict(), "inference_id")

    def inferences(self, profile_id: str | None = None) -> list[GenomicInference]:
        self.init()
        profile = validate_profile_alias(profile_id) if profile_id else None
        rows = self._read_jsonl(self.inferences_path)
        if profile:
            rows = [row for row in rows if row.get("profile_id") == profile]
        return [GenomicInference.from_dict(row) for row in rows]
