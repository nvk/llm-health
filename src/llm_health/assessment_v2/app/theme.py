"""Theme tokens for the local dashboard."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ThemeMode(StrEnum):
    """Supported UI color modes."""

    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ThemePalette:
    """Scientific/clinical UI palette tokens."""

    mode: ThemeMode
    background: str
    surface: str
    surface_alt: str
    text: str
    text_muted: str
    border: str
    accent: str
    accent_soft: str
    good: str
    warning: str
    danger: str
    info: str
    lab_band: str
    guideline_band: str
    weight: str


LIGHT_PALETTE = ThemePalette(
    mode=ThemeMode.LIGHT,
    background="#f6f8fb",
    surface="#ffffff",
    surface_alt="#eef3f8",
    text="#182234",
    text_muted="#65738a",
    border="#d7e0ea",
    accent="#2f6fb2",
    accent_soft="#dbeafe",
    good="#1f8a5b",
        warning="#9a6a1a",
        danger="#9b6a5e",
    info="#2870a6",
    lab_band="#dff3e5",
    guideline_band="#fff1d6",
    weight="#c86f1d",
)

DARK_PALETTE = ThemePalette(
    mode=ThemeMode.DARK,
    background="#0d1320",
    surface="#151d2b",
    surface_alt="#1d2738",
    text="#edf3fb",
    text_muted="#9dafc7",
    border="#304057",
    accent="#f2b84b",
    accent_soft="#3a2a12",
    good="#57c58d",
        warning="#d2a24d",
        danger="#d08a78",
    info="#f2b84b",
    lab_band="#183c2a",
    guideline_band="#493614",
    weight="#f0a45e",
)

PALETTES: dict[ThemeMode, ThemePalette] = {
    ThemeMode.LIGHT: LIGHT_PALETTE,
    ThemeMode.DARK: DARK_PALETTE,
}


def coerce_theme_mode(value: str | bytes | ThemeMode | None) -> ThemeMode:
    """Return a supported theme mode, defaulting to light."""

    if value is None:
        return ThemeMode.LIGHT
    if isinstance(value, ThemeMode):
        return value
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    normalized = value.strip().lower()
    if normalized in {"dark", "d"}:
        return ThemeMode.DARK
    if normalized in {"light", "l", "default"}:
        return ThemeMode.LIGHT
    raise ValueError(f"Unsupported theme: {value!r}")


def theme_mode_from_session_args(
    session_args: Mapping[str, Sequence[str | bytes] | str | bytes] | None,
    default: str | bytes | ThemeMode | None = ThemeMode.LIGHT,
) -> ThemeMode:
    """Resolve Panel's ``?theme=`` query argument into a supported theme mode.

    Panel's built-in Fast template toggle reloads the page with ``?theme=dark`` or
    ``?theme=default``.  When the app is served from a factory this helper lets the
    app synchronize our custom clinical CSS tokens with Panel's own template
    theme for that request.
    """

    fallback = coerce_theme_mode(default)
    if not session_args:
        return fallback

    raw_theme = session_args.get("theme")
    if isinstance(raw_theme, Sequence) and not isinstance(raw_theme, str | bytes):
        raw_theme = raw_theme[0] if raw_theme else None
    if raw_theme is None:
        return fallback
    try:
        return coerce_theme_mode(raw_theme)
    except ValueError:
        return fallback


def palette_for(mode: str | bytes | ThemeMode | None) -> ThemePalette:
    """Return palette tokens for a theme mode."""

    return PALETTES[coerce_theme_mode(mode)]


def panel_theme_for(mode: str | bytes | ThemeMode | None) -> Any:
    """Return Panel's theme class for a mode.

    Imported lazily so package imports and tests do not require Panel unless the app is built.
    """

    from panel.template import DarkTheme, DefaultTheme

    return DarkTheme if coerce_theme_mode(mode) is ThemeMode.DARK else DefaultTheme


def css_variables(palette: ThemePalette) -> str:
    """CSS custom properties shared by Panel panes and future static exports."""

    return f"""
:root {{
  --ha-bg: {palette.background};
  --ha-surface: {palette.surface};
  --ha-surface-alt: {palette.surface_alt};
  --ha-text: {palette.text};
  --ha-text-muted: {palette.text_muted};
  --ha-border: {palette.border};
  --ha-accent: {palette.accent};
  --ha-accent-soft: {palette.accent_soft};
  --ha-good: {palette.good};
  --ha-warning: {palette.warning};
  --ha-danger: {palette.danger};
  --ha-info: {palette.info};
  --ha-lab-band: {palette.lab_band};
  --ha-guideline-band: {palette.guideline_band};
  --ha-weight: {palette.weight};
}}
body {{
  background: var(--ha-bg);
  color: var(--ha-text);
}}
.ha-card {{
  background: var(--ha-surface);
  border: 1px solid var(--ha-border);
  border-radius: 14px;
  padding: 16px 18px;
}}
.ha-card h2, .ha-card h3 {{
  color: var(--ha-text);
  margin-top: 0;
}}
.ha-muted {{ color: var(--ha-text-muted); }}
.ha-tag {{
  border: 1px solid var(--ha-border);
  border-radius: 999px;
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
  margin: 0 6px 6px 0;
  padding: 3px 8px;
  text-transform: uppercase;
}}
.ha-tag-derived {{ color: var(--ha-info); background: var(--ha-accent-soft); }}
.ha-tag-context {{ color: var(--ha-warning); background: var(--ha-guideline-band); }}
.ha-tag-qa {{ color: var(--ha-danger); }}

.ha-hero {{
  background: linear-gradient(135deg, var(--ha-surface), var(--ha-surface-alt));
  border: 1px solid var(--ha-border);
  border-radius: 18px;
  padding: 20px 22px;
}}
.ha-hero h1 {{
  color: var(--ha-text);
  font-size: 28px;
  margin: 0 0 8px 0;
}}
.ha-metric-grid {{
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
}}
.ha-metric-card {{ min-height: 96px; }}
.ha-metric-label {{
  color: var(--ha-text-muted);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
}}
.ha-metric-value {{
  color: var(--ha-text);
  font-size: 25px;
  font-variant-numeric: tabular-nums;
  font-weight: 780;
  margin: 8px 0 2px;
}}
.ha-review-list {{
  margin: 0;
  padding-left: 20px;
}}
.ha-review-list li {{ margin: 8px 0; }}

"""
