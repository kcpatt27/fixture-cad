from __future__ import annotations

from typing import Any

from ..reference_store import get_store
from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    """Auto-tier: open file picker when GUI is available; never mutates the document."""
    del args  # no args
    store = get_store()
    try:
        meta = store.pick_file()
    except RuntimeError as exc:
        return f"attach_reference_image: {exc}; use the Attach button in Fixture Chat"
    if meta is None:
        return "attach cancelled"
    return (
        f"attached {meta['file_name']} "
        f"({meta['media_type']}, {meta['byte_size']} bytes)"
    )


RUNNER = ToolRunner(name="attach_reference_image", permission="auto", run=run)
