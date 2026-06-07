"""Rollup helpers for wearable and lab-window context."""

from __future__ import annotations

VALID_WINDOWS_DAYS = (7, 30, 90, 365)


def window_label(days: int) -> str:
    """Return a stable context-window label."""

    if days not in VALID_WINDOWS_DAYS:
        raise ValueError(f"unsupported window: {days}")
    return f"{days}d"
