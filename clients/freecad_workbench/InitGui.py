"""Register the Fixture workbench with FreeCAD Gui."""

from __future__ import annotations

import FreeCADGui as Gui

from fixture.resources import icon_path


class FixtureWorkbench(Gui.Workbench):
    MenuText = "Fixture"
    ToolTip = "AI-assisted CAD via local Fixture harness"
    Icon = ""

    def Initialize(self) -> None:
        from fixture import commands
        from fixture.ai_chat_dock import ensure_chat_dock

        commands.register_commands()
        self.appendToolbar(
            "Fixture",
            [
                "Fixture_OpenChat",
                "Fixture_ExplainSelection",
                "Fixture_FitView",
            ],
        )
        self.appendMenu(
            "Fixture",
            [
                "Fixture_OpenChat",
                "Fixture_ExplainSelection",
                "Fixture_FitView",
            ],
        )
        ensure_chat_dock()

    def GetClassName(self) -> str:
        return "Gui::PythonWorkbench"

    def Activated(self) -> None:
        from fixture.ai_chat_dock import ensure_chat_dock

        ensure_chat_dock()

    def Deactivated(self) -> None:
        return


FixtureWorkbench.Icon = icon_path("workbench")
Gui.addWorkbench(FixtureWorkbench())
