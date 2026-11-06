from __future__ import annotations

import textwrap

import bpy

from . import operators


def _status_icon(status: str) -> str:
    normalized = status.lower()
    if normalized == "error":
        return "ERROR"
    if normalized.startswith(("sending", "applying")):
        return "TIME"
    if normalized.startswith("awaiting"):
        return "QUESTION"
    return "CHECKMARK"


def _transcript_lines(transcript: str, *, width: int = 42, limit: int = 12) -> list[str]:
    wrapped: list[str] = []
    for line in transcript.splitlines():
        wrapped.extend(
            textwrap.wrap(
                line,
                width=width,
                break_long_words=True,
                break_on_hyphens=False,
            )
            or [""]
        )
    return wrapped[-limit:]


class FIXTURE_PT_panel(bpy.types.Panel):
    bl_label = "Fixture"
    bl_idname = "FIXTURE_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fixture"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        props = context.scene.fixture
        status = operators.get_status()
        transcript = operators.get_transcript()
        has_pending = operators.has_pending_tools()

        status_box = layout.box()
        status_row = status_box.row(align=True)
        display_status = status[:1].upper() + status[1:]
        status_row.label(text=f"Status: {display_status}", icon=_status_icon(status))

        conversation = layout.box()
        conversation.label(text="Conversation", icon="TEXT")
        conversation_column = conversation.column(align=True)
        conversation_column.scale_y = 0.85
        lines = _transcript_lines(transcript)
        if lines:
            for line in lines:
                conversation_column.label(text=line)
        else:
            conversation_column.label(text="Messages and tool results appear here.")

        composer = layout.box()
        composer.label(text="Message", icon="CONSOLE")
        composer.prop(props, "message", text="")
        composer.prop(props, "model_lane", text="Model")
        action_row = composer.row(align=True)
        action_row.enabled = not has_pending
        action_row.operator("fixture.send_chat", text="Send", icon="PLAY")
        action_row.operator("fixture.explain", text="Explain", icon="INFO")

        confirmation = layout.box()
        confirmation.alert = has_pending
        if has_pending:
            confirmation.label(text="Review pending actions", icon="QUESTION")
        else:
            confirmation.label(text="No actions pending", icon="CHECKMARK")
        confirm_row = confirmation.row(align=True)
        confirm_row.enabled = has_pending
        confirm_row.operator("fixture.apply", text="Apply", icon="CHECKMARK")
        confirm_row.operator("fixture.cancel", text="Cancel", icon="X")


def register() -> None:
    bpy.utils.register_class(FIXTURE_PT_panel)


def unregister() -> None:
    bpy.utils.unregister_class(FIXTURE_PT_panel)
