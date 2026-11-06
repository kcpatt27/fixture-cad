from __future__ import annotations

import threading
from typing import Any

import bpy

from . import config
from .action_runner import PendingTool, apply_pending, prepare_actions
from .client import HarnessClient
from .context import build_context
from .conversation_history import (
    append_structured_turn,
    format_intent_presentation,
    history_for_request,
    pending_scope_summary,
)

_TRANSCRIPT: list[str] = []
_STATUS = "idle"
_PENDING_RESULT: dict[str, Any] | None = None
_PENDING_ERROR: str | None = None
_PENDING_TOOLS: list[PendingTool] = []
_PENDING_REQUEST_ID: str | None = None
_PENDING_INTENT_STATUS: str | None = None
_PENDING_SUPPORTED_SCOPE: dict[str, Any] | None = None
_TURNS: list[dict[str, str]] = []
_VERIFY_MODE = False


def append_line(line: str) -> None:
    _TRANSCRIPT.append(line)
    if len(_TRANSCRIPT) > 200:
        del _TRANSCRIPT[:-200]


def get_transcript() -> str:
    return "\n".join(_TRANSCRIPT)


def get_status() -> str:
    return _STATUS


def has_pending_tools() -> bool:
    return bool(_PENDING_TOOLS)


def _set_pending(
    tools: list[PendingTool],
    request_id: str | None,
    *,
    intent_status: str | None = None,
    supported_scope: dict[str, Any] | None = None,
) -> None:
    global _STATUS, _PENDING_TOOLS, _PENDING_REQUEST_ID
    global _PENDING_INTENT_STATUS, _PENDING_SUPPORTED_SCOPE
    _PENDING_TOOLS = list(tools)
    _PENDING_REQUEST_ID = request_id
    _PENDING_INTENT_STATUS = intent_status
    _PENDING_SUPPORTED_SCOPE = supported_scope
    if _PENDING_TOOLS:
        tools_summary = "; ".join(
            f"{item.tool_name}({item.args})" for item in _PENDING_TOOLS
        )
        summary = pending_scope_summary(
            intent_status,
            supported_scope,
            tools_summary,
        )
        append_line(f"confirm: Click Apply to run: {summary}")
        _STATUS = "awaiting Apply / Cancel"
    else:
        _STATUS = "idle"
    _redraw()


class FIXTURE_OT_send_chat(bpy.types.Operator):
    bl_idname = "fixture.send_chat"
    bl_label = "Send"
    bl_description = "Send chat message to Fixture harness"

    def execute(self, context: bpy.types.Context):
        global _STATUS, _PENDING_RESULT, _PENDING_ERROR, _TURNS
        if has_pending_tools():
            self.report({"WARNING"}, "Apply or cancel the pending tools first")
            return {"CANCELLED"}
        props = context.scene.fixture
        message = (props.message or "").strip()
        if not message:
            self.report({"WARNING"}, "Empty message")
            return {"CANCELLED"}

        append_line(f"you: {message}")
        props.message = ""
        _STATUS = "sending…"
        _PENDING_RESULT = None
        _PENDING_ERROR = None
        history = history_for_request(_TURNS)
        _TURNS = append_structured_turn(_TURNS, role="user", text=message)

        payload = {
            "app": config.PROTOCOL_APP,
            "version": config.CLIENT_VERSION,
            "context": build_context(),
            "message": message,
            "history": history,
            "mode": "chat",
            "model_lane": props.model_lane,
        }

        def worker() -> None:
            global _PENDING_RESULT, _PENDING_ERROR
            try:
                _PENDING_RESULT = HarnessClient().send_chat(payload)
            except Exception as exc:  # noqa: BLE001
                _PENDING_ERROR = str(exc)

        threading.Thread(target=worker, daemon=True).start()
        bpy.app.timers.register(_poll_result, first_interval=0.2)
        return {"FINISHED"}


class FIXTURE_OT_explain(bpy.types.Operator):
    bl_idname = "fixture.explain"
    bl_label = "Explain Selection"
    bl_description = "Ask harness to explain selection"

    def execute(self, context: bpy.types.Context):
        global _STATUS, _PENDING_RESULT, _PENDING_ERROR, _TURNS
        if has_pending_tools():
            self.report({"WARNING"}, "Apply or cancel the pending tools first")
            return {"CANCELLED"}
        message = "Explain what this selected object is."
        props = context.scene.fixture
        append_line(f"you: {message}")
        _STATUS = "sending…"
        _PENDING_RESULT = None
        _PENDING_ERROR = None
        history = history_for_request(_TURNS)
        _TURNS = append_structured_turn(_TURNS, role="user", text=message)
        payload = {
            "app": config.PROTOCOL_APP,
            "version": config.CLIENT_VERSION,
            "context": build_context(),
            "message": message,
            "history": history,
            "mode": "explain",
            "model_lane": props.model_lane,
        }

        def worker() -> None:
            global _PENDING_RESULT, _PENDING_ERROR
            try:
                _PENDING_RESULT = HarnessClient().send_chat(payload)
            except Exception as exc:  # noqa: BLE001
                _PENDING_ERROR = str(exc)

        threading.Thread(target=worker, daemon=True).start()
        bpy.app.timers.register(_poll_result, first_interval=0.2)
        return {"FINISHED"}


class FIXTURE_OT_apply(bpy.types.Operator):
    bl_idname = "fixture.apply"
    bl_label = "Apply"
    bl_description = "Apply pending Fixture tool calls"
    bl_options = {"UNDO"}

    @classmethod
    def poll(cls, _context: bpy.types.Context) -> bool:
        return has_pending_tools()

    def execute(self, _context: bpy.types.Context):
        global _STATUS, _TURNS, _PENDING_RESULT, _PENDING_ERROR, _VERIFY_MODE
        pending = list(_PENDING_TOOLS)
        request_id = _PENDING_REQUEST_ID
        prior_scope = _PENDING_SUPPORTED_SCOPE
        lane = pending[0].model_lane if pending else "accurate"
        _set_pending([], None)
        _STATUS = "applying..."
        repaired: list[PendingTool] = []
        apply_logs = apply_pending(pending, request_id=request_id, pending_out=repaired)
        for line in apply_logs:
            append_line(f"tool: {line}")
        append_line("meta: Undo is available in Blender")
        if repaired:
            _set_pending(repaired, repaired[0].request_id or request_id)
            append_line("status: Repair produced confirm-tier tools; click Apply to run them.")
            _STATUS = "awaiting Apply / Cancel"
            _redraw()
            return {"FINISHED"}
        if any(line.startswith("fail:") for line in apply_logs):
            _STATUS = "idle"
            _redraw()
            return {"FINISHED"}

        from .verify import (
            VERIFY_MESSAGE,
            format_verify_history_text,
            post_apply_verify,
        )

        verify_lines, inspection = post_apply_verify(apply_logs)
        for line in verify_lines:
            append_line(line)
        fit_result = "view fitted"
        for line in verify_lines:
            if line.startswith("verify: fit ->"):
                fit_result = line.split("->", 1)[-1].strip()
                break
        history_text = format_verify_history_text(inspection, fit_result=fit_result)
        _TURNS = append_structured_turn(_TURNS, role="assistant", text=history_text)

        context = build_context()
        extra = dict(context.get("extra") or {})
        extra["inspection"] = inspection
        if isinstance(prior_scope, dict):
            extra["prior_supported_scope"] = prior_scope
        context["extra"] = extra
        payload = {
            "app": config.PROTOCOL_APP,
            "version": config.CLIENT_VERSION,
            "context": context,
            "message": VERIFY_MESSAGE,
            "history": history_for_request(_TURNS),
            "mode": "explain",
            "model_lane": lane,
        }
        _STATUS = "verifying..."
        _PENDING_RESULT = None
        _PENDING_ERROR = None
        _VERIFY_MODE = True

        def worker() -> None:
            global _PENDING_RESULT, _PENDING_ERROR
            try:
                _PENDING_RESULT = HarnessClient().send_chat(payload)
            except Exception as exc:  # noqa: BLE001
                _PENDING_ERROR = str(exc)

        threading.Thread(target=worker, daemon=True).start()
        bpy.app.timers.register(_poll_result, first_interval=0.2)
        _redraw()
        return {"FINISHED"}


class FIXTURE_OT_cancel(bpy.types.Operator):
    bl_idname = "fixture.cancel"
    bl_label = "Cancel"
    bl_description = "Discard pending Fixture tool calls"

    @classmethod
    def poll(cls, _context: bpy.types.Context) -> bool:
        return has_pending_tools()

    def execute(self, _context: bpy.types.Context):
        names = ", ".join(item.tool_name for item in _PENDING_TOOLS)
        append_line(f"tool: cancelled: {names}")
        _set_pending([], None)
        return {"FINISHED"}


def _poll_result() -> float | None:
    global _STATUS, _PENDING_RESULT, _PENDING_ERROR, _TURNS, _VERIFY_MODE
    if _PENDING_ERROR is not None:
        append_line(f"error: {_PENDING_ERROR}")
        _STATUS = "error" if not _VERIFY_MODE else "idle"
        if _VERIFY_MODE:
            append_line(f"error: verify chat failed: {_PENDING_ERROR}")
        _PENDING_ERROR = None
        _VERIFY_MODE = False
        _redraw()
        return None
    if _PENDING_RESULT is None:
        return 0.2

    result = _PENDING_RESULT
    _PENDING_RESULT = None
    if _VERIFY_MODE:
        from .verify import filter_verify_response

        filtered = filter_verify_response(result)
        _VERIFY_MODE = False
        reply = str(filtered.get("reply_text") or "")
        if reply:
            append_line(f"ai: {reply}")
            _TURNS = append_structured_turn(_TURNS, role="assistant", text=reply)
        for line in format_intent_presentation(
            filtered.get("intent_status"),
            filtered.get("supported_scope"),
        ):
            append_line(line)
        logs, pending = prepare_actions(
            filtered,
            on_meta=lambda a: append_line(f"meta: {a.get('kind')}: {a.get('text')}"),
            defer_confirm=True,
        )
        for line in logs:
            append_line(f"tool: {line}")
        if pending:
            append_line(
                "status: verify ignored pending confirm tools: "
                + ", ".join(p.tool_name for p in pending)
            )
        _set_pending([], None)
        _STATUS = "idle"
        _redraw()
        return None

    reply = str(result.get("reply_text") or "")
    append_line(f"ai: {reply}")
    _TURNS = append_structured_turn(_TURNS, role="assistant", text=reply)
    for line in format_intent_presentation(
        result.get("intent_status"),
        result.get("supported_scope"),
    ):
        append_line(line)
    lane = result.get("model_lane")
    model = result.get("model")
    if lane and model:
        append_line(f"model: {lane}: {model}")

    logs, pending = prepare_actions(
        result,
        on_meta=lambda a: append_line(f"meta: {a.get('kind')}: {a.get('text')}"),
        defer_confirm=True,
    )
    for line in logs:
        append_line(f"tool: {line}")
    scope = result.get("supported_scope")
    _set_pending(
        pending,
        result.get("request_id"),
        intent_status=result.get("intent_status")
        if isinstance(result.get("intent_status"), str)
        else None,
        supported_scope=scope if isinstance(scope, dict) else None,
    )
    return None


def _redraw() -> None:
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class FixtureProps(bpy.types.PropertyGroup):
    message: bpy.props.StringProperty(name="Message", default="")  # type: ignore[valid-type]
    model_lane: bpy.props.EnumProperty(  # type: ignore[valid-type]
        name="Model",
        items=(
            ("accurate", "Accurate", "Use the pinned 14b model"),
            ("fast", "Fast", "Use the faster 7b model"),
            ("auto", "Auto", "Route by request mode"),
        ),
        default="accurate",
    )


CLASSES = (
    FixtureProps,
    FIXTURE_OT_send_chat,
    FIXTURE_OT_explain,
    FIXTURE_OT_apply,
    FIXTURE_OT_cancel,
)


def register() -> None:
    global _TURNS, _TRANSCRIPT
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.fixture = bpy.props.PointerProperty(type=FixtureProps)


def unregister() -> None:
    global _TURNS, _TRANSCRIPT, _PENDING_TOOLS
    _TURNS = []
    _TRANSCRIPT = []
    _PENDING_TOOLS = []
    del bpy.types.Scene.fixture
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
