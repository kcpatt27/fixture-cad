from __future__ import annotations

from .base import ToolRunner
from . import clean_mesh, clean_scan, explain_selection, fit_view_selection


def get_runner(name: str) -> ToolRunner | None:
    runners = {
        r.name: r
        for r in (
            explain_selection.RUNNER,
            fit_view_selection.RUNNER,
            clean_mesh.RUNNER,
            clean_scan.RUNNER,
        )
    }
    return runners.get(name)
