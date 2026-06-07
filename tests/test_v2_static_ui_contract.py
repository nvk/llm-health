from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "llm_health" / "assessment_v2" / "web_static"


def _asset_text() -> str:
    return "\n".join((STATIC / name).read_text() for name in ["index.html", "styles.css", "app.js"])


def test_packaged_v2_static_ui_uses_review_packet_structure() -> None:
    text = _asset_text()

    assert "Local longitudinal review" in text
    assert "workflow-block" not in text
    assert "flow-steps" not in text
    assert "id=\"profileState\"" in text
    assert "id=\"domainMap\"" in text
    assert "id=\"viewBrief\"" in text
    assert "data-row-focus=\"flags\"" in text
    assert "data-jump" in text
    assert "data-category-jump" in text
    assert "function populateProfiles" in text
    assert "function renderDomainMap" in text
    assert "function viewBrief" in text
    assert "function rowFocusRows" in text
    assert "Source flag rings" in text
    assert "Pending/nonnumeric rows stay in sources" in text


def test_packaged_v2_static_ui_preserves_tags_and_privacy() -> None:
    text = _asset_text()

    for tag in [
        "OBSERVED",
        "DERIVED",
        "WEARABLE_CONTEXT",
        "CONTEXT",
        "INFERENCE",
        "DATA_GAP",
        "QA_ISSUE",
    ]:
        assert tag in text
    assert "--accent: #f2b84b" in text
    assert "/Users/" not in text
    assert "Mobile Documents" not in text
    assert ".pdf" not in text.lower()
    assert "source_file_alias" not in text
