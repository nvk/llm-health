from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_ENV = "LLM_HEALTH_CONFIG"
HUB_ENV = "LLM_HEALTH_HUB"
WIKI_ROOT_ENV = "HEALTH_WIKI_ROOT"
DEFAULT_CONFIG_PATH = Path("~/.config/llm-health/config.json")
DEFAULT_LOCAL_STORE = Path(".llm-health")


@dataclass(frozen=True)
class HealthConfig:
    config_path: Path
    hub_path: Path | None = None
    wiki_root: Path | None = None

    def to_json(self) -> dict[str, str]:
        data: dict[str, str] = {}
        if self.hub_path is not None:
            data["hub_path"] = collapse_home(self.hub_path)
        if self.wiki_root is not None:
            data["wiki_root"] = collapse_home(self.wiki_root)
        return data


def expand_leading_tilde(path: str | Path) -> Path:
    """Expand only a leading tilde, preserving tildes inside path components."""

    text = str(path)
    if text == "~":
        return Path.home()
    if text.startswith("~/"):
        return Path.home() / text[2:]
    return Path(text)


def collapse_home(path: str | Path) -> str:
    resolved = Path(path)
    home = Path.home()
    try:
        return "~/" + str(resolved.relative_to(home))
    except ValueError:
        return str(resolved)


def default_config_path() -> Path:
    env = os.environ.get(CONFIG_ENV)
    return expand_leading_tilde(env) if env else expand_leading_tilde(DEFAULT_CONFIG_PATH)


def load_config(config_path: str | Path | None = None) -> HealthConfig:
    path = expand_leading_tilde(config_path) if config_path else default_config_path()
    if not path.exists():
        return HealthConfig(config_path=path)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    hub_raw = data.get("hub_path") or data.get("resolved_path")
    wiki_raw = data.get("wiki_root") or data.get("health_assessments_wiki_root")
    hub = expand_leading_tilde(hub_raw) if hub_raw else None
    wiki_root = expand_leading_tilde(wiki_raw) if wiki_raw else None
    return HealthConfig(config_path=path, hub_path=hub, wiki_root=wiki_root)


def save_config(config: HealthConfig) -> None:
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    config.config_path.write_text(
        json.dumps(config.to_json(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def set_hub_path(hub_path: str | Path, config_path: str | Path | None = None) -> HealthConfig:
    current = load_config(config_path)
    config = HealthConfig(
        config_path=current.config_path,
        hub_path=expand_leading_tilde(hub_path),
        wiki_root=current.wiki_root,
    )
    save_config(config)
    return config


def set_wiki_root(wiki_root: str | Path, config_path: str | Path | None = None) -> HealthConfig:
    current = load_config(config_path)
    config = HealthConfig(
        config_path=current.config_path,
        hub_path=current.hub_path,
        wiki_root=expand_leading_tilde(wiki_root),
    )
    save_config(config)
    return config


def resolve_store_path(explicit_store: str | Path | None = None) -> Path:
    if explicit_store:
        return expand_leading_tilde(explicit_store)
    env_hub = os.environ.get(HUB_ENV)
    if env_hub:
        return expand_leading_tilde(env_hub)
    config = load_config()
    if config.hub_path is not None:
        return config.hub_path
    return DEFAULT_LOCAL_STORE


def resolve_wiki_root(explicit_wiki_root: str | Path | None = None) -> Path | None:
    if explicit_wiki_root:
        return expand_leading_tilde(explicit_wiki_root)
    env_root = os.environ.get(WIKI_ROOT_ENV)
    if env_root:
        return expand_leading_tilde(env_root)
    config = load_config()
    return config.wiki_root
