from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "llm_health" / "assessment_v2" / "web_static"
STATIC_V3 = (
    Path(__file__).resolve().parents[1] / "src" / "llm_health" / "assessment_v2" / "web_static_v3"
)


def _asset_text() -> str:
    return "\n".join((STATIC / name).read_text() for name in ["index.html", "styles.css", "app.js"])


def _v3_asset_text() -> str:
    parts = [(STATIC_V3 / "index.html").read_text()]
    parts.extend(path.read_text() for path in sorted((STATIC_V3 / "assets").glob("*.*")))
    return "\n".join(parts)


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


def test_packaged_v3_static_ui_uses_framework_board() -> None:
    text = _v3_asset_text()

    assert "Assessment board" in text
    assert "data-v3-ui" in text
    assert "Context overlays" in text
    assert "Source flag rings" in text
    assert "Exact date labels" in text
    assert "Smart overlay comparison" in text
    assert "Overlay group" in text
    assert "Resolved flags are historical" in text
    assert "resolved by later" in text
    assert "pending resulted" in text
    assert "old pending row" in text
    assert "Normalization QA" in text
    assert "English display fields" in text
    assert "priority groups open first" in text
    assert "mantine" in text.lower()
    assert "recharts" in text.lower() or "recharts-wrapper" in text
    assert "--paper-grain" in text
    assert "--corner-lg" in text
    assert "--tag-issue-bg" in text
    assert "content:none" in text
    assert "QA issue" in text
    assert "Data gap" in text
    assert "Wearable context" in text


def test_packaged_v3_static_ui_privacy_contract() -> None:
    text = _v3_asset_text()

    for tag in [
        "OBSERVED",
        "DERIVED",
        "WEARABLE_CONTEXT",
        "CONTEXT",
        "DATA_GAP",
        "QA_ISSUE",
    ]:
        assert tag in text
    assert "--accent: #f2b84b" in text
    assert "/Users/" not in text
    assert "Mobile Documents" not in text
    assert ".pdf" not in text.lower()
    assert "source_file_alias" not in text


def test_packaged_v3_static_ui_opens_from_file_url() -> None:
    index = (STATIC_V3 / "index.html").read_text()

    assert 'data-v3-ui' in _v3_asset_text()
    assert 'type="module"' not in index
    assert 'crossorigin' not in index
    assert '<script defer src="./assets/' in index
    assert '<link rel="stylesheet" href="./assets/' in index
