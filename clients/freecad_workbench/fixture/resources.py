from __future__ import annotations

from pathlib import Path


_ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"


def icon_path(name: str) -> str:
    """Return an absolute path accepted by FreeCAD and Qt icon loaders."""
    return str(_ICON_DIR / f"{name}.svg")
