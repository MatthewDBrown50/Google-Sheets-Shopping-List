"""Tap-to-cross shopping list Streamlit component."""

from __future__ import annotations

import os
from typing import Any

import streamlit.components.v1 as components

_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
_trip_list = components.declare_component("trip_list", path=_FRONTEND_DIR)


def trip_list(
    rows: list[dict[str, str]],
    crossed: list[str],
    *,
    key: str | None = None,
) -> dict[str, Any] | None:
    """Render the list; returns ``{key, seq}`` when a row is tapped."""
    return _trip_list(rows=rows, crossed=crossed, key=key, default=None)
