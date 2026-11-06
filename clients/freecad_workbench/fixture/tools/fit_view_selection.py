from __future__ import annotations

from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import FreeCADGui as Gui

    _ = args
    try:
        Gui.SendMsgToActiveView("ViewSelection")
    except Exception:  # noqa: BLE001
        Gui.SendMsgToActiveView("ViewFit")
    return "view fitted"


RUNNER = ToolRunner(name="fit_view_selection", permission="auto", run=run)
