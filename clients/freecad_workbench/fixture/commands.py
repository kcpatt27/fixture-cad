from __future__ import annotations

from .resources import icon_path


class Fixture_OpenChat:
    def Activated(self) -> None:
        from .ai_chat_dock import ensure_chat_dock

        ensure_chat_dock()

    def GetResources(self) -> dict:
        return {
            "Pixmap": icon_path("chat"),
            "MenuText": "Open AI Chat",
            "ToolTip": "Show the Fixture chat panel",
        }

    def IsActive(self) -> bool:
        return True


class Fixture_ExplainSelection:
    def Activated(self) -> None:
        from .ai_chat_dock import ensure_chat_dock

        dock = ensure_chat_dock()
        dock.explain_selection()

    def GetResources(self) -> dict:
        return {
            "Pixmap": icon_path("explain"),
            "MenuText": "Explain Selection",
            "ToolTip": "Ask the harness to explain the current selection",
        }

    def IsActive(self) -> bool:
        return True


class Fixture_FitView:
    def Activated(self) -> None:
        from .tools.fit_view_selection import run

        run({})

    def GetResources(self) -> dict:
        return {
            "Pixmap": icon_path("fit"),
            "MenuText": "Fit View Selection",
            "ToolTip": "Frame the 3D view on the selection",
        }

    def IsActive(self) -> bool:
        return True


def register_commands() -> None:
    import FreeCADGui as Gui

    Gui.addCommand("Fixture_OpenChat", Fixture_OpenChat())
    Gui.addCommand("Fixture_ExplainSelection", Fixture_ExplainSelection())
    Gui.addCommand("Fixture_FitView", Fixture_FitView())
