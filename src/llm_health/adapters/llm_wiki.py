from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm_health.core.privacy import assert_safe_payload


@dataclass(frozen=True)
class LlmWikiAdapterConfig:
    topic_root: str
    write_enabled: bool = False

    def __post_init__(self) -> None:
        # Topic roots are local paths, but adapter config should not be exported
        # into health artifacts.
        # Do not call assert_safe_payload on topic_root here.
        if not self.topic_root:
            raise ValueError("topic_root is required")


class LlmWikiAdapter:
    """Skeleton adapter for de-identified llm-wiki import/export.

    The adapter intentionally avoids reading raw PDFs or private source paths. It should only import
    de-identified wiki notes, compiled articles, and canonical dataset exports.
    """

    def __init__(self, config: LlmWikiAdapterConfig) -> None:
        self.config = config
        self.topic_root = Path(config.topic_root).expanduser()

    def available(self) -> bool:
        return (self.topic_root / "_index.md").exists()

    def index_paths(self) -> dict[str, Path]:
        return {
            "topic": self.topic_root / "_index.md",
            "wiki": self.topic_root / "wiki" / "_index.md",
            "raw": self.topic_root / "raw" / "_index.md",
        }

    def export_markdown_note(self, relative_path: str, markdown: str) -> Path:
        if not self.config.write_enabled:
            raise PermissionError("llm-wiki adapter writes require write_enabled=True")
        assert_safe_payload({"relative_path": relative_path, "markdown": markdown})
        path = self.topic_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        return path
