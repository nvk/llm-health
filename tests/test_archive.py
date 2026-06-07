from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from llm_health.agreement import write_agreement_acceptance
from llm_health.archive import create_archive, plan_archive_members, verify_archive
from llm_health.core.privacy import PrivacyError
from llm_health.stores import LocalHealthStore


def test_archive_skips_unknown_roots_and_raw_source_markers(tmp_path: Path) -> None:
    store = LocalHealthStore(tmp_path)
    write_agreement_acceptance(store.root)
    store.init()
    (tmp_path / "v2-web").mkdir()
    (tmp_path / "v2-web" / "index.html").write_text("safe dashboard")
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "original.pdf").write_bytes(b"not eligible by allowlist")
    (tmp_path / "v2-data").mkdir()
    (tmp_path / "v2-data" / "health.duckdb").write_bytes(b"embedded raw-source.pdf")

    members, skipped = plan_archive_members(tmp_path)
    member_paths = {member.path for member in members}
    skipped_paths = {item.path for item in skipped}

    assert "v2-web/index.html" in member_paths
    assert "raw/original.pdf" not in member_paths
    assert "v2-data/health.duckdb" in skipped_paths

    with pytest.raises(PrivacyError):
        plan_archive_members(tmp_path, strict=True)


def test_archive_create_and_verify(tmp_path: Path) -> None:
    store = LocalHealthStore(tmp_path)
    write_agreement_acceptance(store.root)
    store.init()
    (tmp_path / "v2-web").mkdir()
    (tmp_path / "v2-web" / "index.html").write_text("safe dashboard")

    result = create_archive(tmp_path)
    assert result.archive_path.exists()
    assert result.member_count > 0
    assert result.skipped_count == 0

    with tarfile.open(result.archive_path, "r:gz") as tar:
        names = set(tar.getnames())
        manifest = json.loads(tar.extractfile("archive-manifest.json").read().decode("utf-8"))
    assert "v2-web/index.html" in names
    assert manifest["schema"] == "llm-health-archive-v1"
    assert manifest["hub_root_label"] == "resolved llm-health HUB"

    verified_manifest, failures = verify_archive(result.archive_path)
    assert verified_manifest["archive_id"] == result.archive_id
    assert failures == []
