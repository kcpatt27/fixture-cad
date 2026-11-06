from __future__ import annotations

from typing import Any

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
from .reference_store import get_store
from .resources import icon_path


def _qt():
    try:
        from PySide6 import QtCore, QtGui, QtWidgets

        return QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets

        return QtCore, QtGui, QtWidgets


def _standard_icon(style: Any, widgets: Any, name: str) -> Any:
    standard_pixmap = getattr(widgets.QStyle, name, None)
    if standard_pixmap is None:
        standard_pixmap = getattr(widgets.QStyle.StandardPixmap, name)
    return style.standardIcon(standard_pixmap)


class _ChatWorker:
    """Runs harness HTTP off-thread and relays results onto the GUI thread."""

    def __init__(self, payload: dict[str, Any]) -> None:
        QtCore, _, _ = _qt()

        class GuiRelay(QtCore.QObject):
            finished = QtCore.Signal(object)
            failed = QtCore.Signal(str)

            @QtCore.Slot(object)
            def forward_finished(self, result: object) -> None:
                self.finished.emit(result)

            @QtCore.Slot(str)
            def forward_failed(self, error: str) -> None:
                self.failed.emit(error)

        class Worker(QtCore.QObject):
            finished = QtCore.Signal(object)
            failed = QtCore.Signal(str)

            def __init__(self, data: dict[str, Any]) -> None:
                super().__init__()
                self._data = data

            @QtCore.Slot()
            def run(self) -> None:
                try:
                    client = HarnessClient()
                    result = client.send_chat(self._data)
                    self.finished.emit(result)
                except Exception as exc:  # noqa: BLE001
                    self.failed.emit(str(exc))

        self.worker = Worker(payload)
        # Constructed by AIChatDock on the GUI thread; explicit queued
        # connections ensure widget callbacks never run in the HTTP thread.
        self.gui_relay = GuiRelay()
        self.thread = QtCore.QThread()
        self.thread.setObjectName("Fixture HTTP worker")
        self.worker.moveToThread(self.thread)
        queued = getattr(QtCore.Qt, "QueuedConnection", None)
        if queued is None:
            queued = QtCore.Qt.ConnectionType.QueuedConnection
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.gui_relay.forward_finished, queued)
        self.worker.failed.connect(self.gui_relay.forward_failed, queued)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.failed.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)


class AIChatDock:
    def __init__(self, parent=None) -> None:
        QtCore, QtGui, QtWidgets = _qt()
        self._QtWidgets = QtWidgets
        self.dock = QtWidgets.QDockWidget("Fixture Chat", parent)
        self.dock.setObjectName("FixtureChatDock")

        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        status_row = QtWidgets.QHBoxLayout()
        status_label = QtWidgets.QLabel("Status")
        status_font = status_label.font()
        status_font.setBold(True)
        status_label.setFont(status_font)
        self.status = QtWidgets.QLabel("Idle")
        self.status.setAccessibleName("Fixture status")
        status_row.addWidget(status_label)
        status_row.addWidget(self.status)
        status_row.addStretch()
        layout.addLayout(status_row)

        conversation_label = QtWidgets.QLabel("Conversation")
        conversation_font = conversation_label.font()
        conversation_font.setBold(True)
        conversation_label.setFont(conversation_font)
        layout.addWidget(conversation_label)

        self.transcript = QtWidgets.QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("Messages and tool results appear here.")
        wrap_mode = getattr(QtWidgets.QPlainTextEdit, "WidgetWidth", None)
        if wrap_mode is None:
            wrap_mode = QtWidgets.QPlainTextEdit.LineWrapMode.WidgetWidth
        self.transcript.setLineWrapMode(wrap_mode)
        self.transcript.document().setMaximumBlockCount(500)
        self.transcript.setAccessibleName("Fixture conversation")
        layout.addWidget(self.transcript)

        message_label = QtWidgets.QLabel("Message")
        message_font = message_label.font()
        message_font.setBold(True)
        message_label.setFont(message_font)
        layout.addWidget(message_label)

        self.input = QtWidgets.QPlainTextEdit()
        self.input.setPlaceholderText("Ask Fixture...")
        self.input.setFixedHeight(84)
        self.input.setAccessibleName("Fixture message")
        layout.addWidget(self.input)

        attach_row = QtWidgets.QHBoxLayout()
        self.attach_btn = QtWidgets.QPushButton("Attach…")
        self.attach_btn.setToolTip(
            "Attach a local reference image or SVG (basename metadata only)"
        )
        self.attach_btn.setAccessibleName("Attach Fixture reference")
        self.attach_btn.clicked.connect(self.attach_reference)
        attach_row.addWidget(self.attach_btn)
        self.clear_attach_btn = QtWidgets.QPushButton("Clear")
        self.clear_attach_btn.setEnabled(False)
        self.clear_attach_btn.setToolTip("Clear the attached reference")
        self.clear_attach_btn.setAccessibleName("Clear Fixture reference")
        self.clear_attach_btn.clicked.connect(self.clear_reference)
        attach_row.addWidget(self.clear_attach_btn)
        self.attach_label = QtWidgets.QLabel("No reference attached")
        self.attach_label.setWordWrap(True)
        self.attach_label.setAccessibleName("Fixture attached reference")
        attach_row.addWidget(self.attach_label, stretch=1)
        layout.addLayout(attach_row)

        lane_row = QtWidgets.QHBoxLayout()
        lane_row.addWidget(QtWidgets.QLabel("Model"))
        self.lane_select = QtWidgets.QComboBox()
        self.lane_select.addItem("Accurate", "accurate")
        self.lane_select.addItem("Fast", "fast")
        self.lane_select.addItem("Auto", "auto")
        self.lane_select.setToolTip("Accurate is the default; Auto routes by request mode")
        self.lane_select.setAccessibleName("Fixture model lane")
        lane_row.addWidget(self.lane_select)
        lane_row.addStretch()
        self.send_btn = QtWidgets.QPushButton("Send")
        self.send_btn.setIcon(QtGui.QIcon(icon_path("send")))
        self.send_btn.setToolTip("Send message to the local Fixture harness")
        self.send_btn.setAccessibleName("Send Fixture message")
        self.send_btn.clicked.connect(self.send_message)
        lane_row.addWidget(self.send_btn)
        layout.addLayout(lane_row)

        self.pending_group = QtWidgets.QGroupBox("Pending actions")
        pending_layout = QtWidgets.QVBoxLayout(self.pending_group)
        self.pending_summary = QtWidgets.QLabel()
        self.pending_summary.setWordWrap(True)
        self.pending_summary.setAccessibleName("Pending Fixture actions")
        pending_layout.addWidget(self.pending_summary)
        confirm_row = QtWidgets.QHBoxLayout()
        confirm_row.addStretch()
        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.apply_btn.setIcon(
            _standard_icon(container.style(), QtWidgets, "SP_DialogApplyButton")
        )
        self.apply_btn.setEnabled(False)
        self.apply_btn.setToolTip("Apply pending AI tool calls")
        self.apply_btn.setAccessibleName("Apply pending Fixture actions")
        self.apply_btn.clicked.connect(self.apply_pending_tools)
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setIcon(
            _standard_icon(container.style(), QtWidgets, "SP_DialogCancelButton")
        )
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip("Discard pending AI tool calls")
        self.cancel_btn.setAccessibleName("Cancel pending Fixture actions")
        self.cancel_btn.clicked.connect(self.cancel_pending_tools)
        confirm_row.addWidget(self.apply_btn)
        confirm_row.addWidget(self.cancel_btn)
        pending_layout.addLayout(confirm_row)
        self.pending_group.setVisible(False)
        layout.addWidget(self.pending_group)

        self.dock.setWidget(container)
        self._worker_holder: _ChatWorker | None = None
        self._pending: list[PendingTool] = []
        self._pending_request_id: str | None = None
        self._pending_intent_status: str | None = None
        self._pending_supported_scope: dict[str, Any] | None = None
        self._turns: list[dict[str, str]] = []
        self._busy = False

    def append(self, who: str, text: str) -> None:
        self.transcript.appendPlainText(f"{who}: {text}")

    def set_status(self, text: str) -> None:
        self.status.setText(text[:1].upper() + text[1:] if text else "")

    def _refresh_attach_label(self) -> None:
        meta = get_store().metadata()
        if meta is None:
            self.attach_label.setText("No reference attached")
            self.clear_attach_btn.setEnabled(False)
            return
        dims = ""
        if meta.get("width_px") and meta.get("height_px"):
            dims = f", {meta['width_px']}x{meta['height_px']}px"
        self.attach_label.setText(
            f"{meta['file_name']} ({meta['media_type']}, {meta['byte_size']} B{dims})"
        )
        self.clear_attach_btn.setEnabled(True)

    def attach_reference(self) -> None:
        if self._busy or self._pending:
            self.append("status", "Apply or cancel pending actions before attaching.")
            return
        store = get_store()
        try:
            meta = store.pick_file()
        except Exception as exc:  # noqa: BLE001
            self.append("error", f"attach failed: {exc}")
            return
        if meta is None:
            self.append("status", "attach cancelled")
            return
        self._refresh_attach_label()
        self.append(
            "status",
            f"attached {meta['file_name']} ({meta['media_type']}, {meta['byte_size']} B)",
        )

    def clear_reference(self) -> None:
        get_store().clear()
        self._refresh_attach_label()
        self.append("status", "reference cleared")

    def _context_with_reference(self) -> dict[str, Any]:
        context = build_context()
        meta = get_store().metadata()
        if meta is not None:
            extra = dict(context.get("extra") or {})
            extra["reference_image"] = meta
            context["extra"] = extra
        return context

    def _refresh_send_enabled(self) -> None:
        blocked = self._busy or bool(self._pending)
        self.send_btn.setEnabled(not blocked)

    def _set_pending(
        self,
        pending: list[PendingTool],
        request_id: str | None,
        *,
        intent_status: str | None = None,
        supported_scope: dict[str, Any] | None = None,
    ) -> None:
        self._pending = list(pending)
        self._pending_request_id = request_id
        self._pending_intent_status = intent_status
        self._pending_supported_scope = supported_scope
        has = bool(self._pending)
        self.apply_btn.setEnabled(has)
        self.cancel_btn.setEnabled(has)
        self.pending_group.setVisible(has)
        self._refresh_send_enabled()
        if has:
            tools_summary = "; ".join(f"{p.tool_name}({p.args})" for p in self._pending)
            summary = pending_scope_summary(
                intent_status,
                supported_scope,
                tools_summary,
            )
            self.pending_summary.setText(summary)
            self.append("confirm", f"Click Apply to run: {summary}")
            self.set_status("awaiting Apply / Cancel")
        else:
            self.pending_summary.clear()
            if not self._busy:
                self.set_status("idle")

    def apply_pending_tools(self) -> None:
        if not self._pending:
            return
        pending = list(self._pending)
        request_id = self._pending_request_id
        prior_scope = self._pending_supported_scope
        self._set_pending([], None)
        self.set_status("applying...")
        repaired: list[PendingTool] = []
        logs = apply_pending(pending, request_id=request_id, pending_out=repaired)
        for line in logs:
            self.append("tool", line)
        if repaired:
            self._set_pending(repaired, repaired[0].request_id or request_id)
            self.append(
                "status",
                "Repair produced confirm-tier tools; click Apply to run them.",
            )
            self.set_status("awaiting Apply / Cancel")
            return
        if any(line.startswith("fail:") for line in logs):
            self.set_status("idle")
            return
        from .verify import (
            VERIFY_MESSAGE,
            format_verify_history_text,
            post_apply_verify,
        )

        verify_lines, inspection = post_apply_verify(logs)
        for line in verify_lines:
            self.transcript.appendPlainText(line)
        fit_result = "view fitted"
        for line in verify_lines:
            if line.startswith("verify: fit ->"):
                fit_result = line.split("->", 1)[-1].strip()
                break
        history_text = format_verify_history_text(inspection, fit_result=fit_result)
        self._turns = append_structured_turn(
            self._turns, role="assistant", text=history_text
        )
        self._dispatch_verify(
            VERIFY_MESSAGE,
            inspection=inspection,
            prior_scope=prior_scope if isinstance(prior_scope, dict) else None,
        )

    def _dispatch_verify(
        self,
        message: str,
        *,
        inspection: dict[str, Any],
        prior_scope: dict[str, Any] | None,
    ) -> None:
        """Grounded explain after Apply; never stages confirm-tier tools."""
        from .verify import filter_verify_response

        history = history_for_request(self._turns)
        context = self._context_with_reference()
        extra = dict(context.get("extra") or {})
        extra["inspection"] = inspection
        if prior_scope:
            extra["prior_supported_scope"] = prior_scope
        context["extra"] = extra
        payload = {
            "app": config.PROTOCOL_APP,
            "version": config.CLIENT_VERSION,
            "context": context,
            "message": message,
            "history": history,
            "mode": "explain",
            "model_lane": self.lane_select.currentData(),
        }
        self._busy = True
        self.set_status("verifying...")
        self._refresh_send_enabled()
        holder = _ChatWorker(payload)
        self._worker_holder = holder

        def on_ok(result: object) -> None:
            self._busy = False
            if not isinstance(result, dict):
                self.append("error", "bad verify response")
                self.set_status("idle")
                self._refresh_send_enabled()
                return
            filtered = filter_verify_response(result)
            reply = str(filtered.get("reply_text") or "")
            if reply:
                self.append("ai", reply)
                self._turns = append_structured_turn(
                    self._turns, role="assistant", text=reply
                )
            for line in format_intent_presentation(
                filtered.get("intent_status"),
                filtered.get("supported_scope"),
            ):
                self.transcript.appendPlainText(line)

            def on_meta(action: dict[str, Any]) -> None:
                self.append("meta", f"{action.get('kind')}: {action.get('text')}")

            logs, pending = prepare_actions(
                filtered, on_meta=on_meta, defer_confirm=True
            )
            for line in logs:
                self.append("tool", line)
            # Never stage confirm-tier from verify (filter already drops them).
            if pending:
                self.append(
                    "status",
                    "verify ignored pending confirm tools: "
                    + ", ".join(p.tool_name for p in pending),
                )
            self._set_pending([], None)
            self.set_status("idle")
            self._refresh_send_enabled()

        def on_fail(err: str) -> None:
            self._busy = False
            self.set_status("idle")
            self.append("error", f"verify chat failed: {err}")
            self._refresh_send_enabled()

        holder.gui_relay.finished.connect(on_ok)
        holder.gui_relay.failed.connect(on_fail)
        holder.thread.start()

    def cancel_pending_tools(self) -> None:
        if not self._pending:
            return
        names = ", ".join(p.tool_name for p in self._pending)
        self.append("tool", f"cancelled: {names}")
        self._set_pending([], None)

    def send_message(self) -> None:
        if self._busy or self._pending:
            self.append("status", "Apply or cancel pending actions before sending.")
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.append("you", text)
        self._dispatch(text, mode="chat")

    def explain_selection(self) -> None:
        if self._busy or self._pending:
            self.append("status", "Apply or cancel pending actions before sending.")
            return
        msg = "Explain what this selected part is and what it does."
        self.append("you", msg)
        self._dispatch(msg, mode="explain")

    def _dispatch(self, message: str, *, mode: str) -> None:
        history = history_for_request(self._turns)
        payload = {
            "app": config.PROTOCOL_APP,
            "version": config.CLIENT_VERSION,
            "context": self._context_with_reference(),
            "message": message,
            "history": history,
            "mode": mode,
            "model_lane": self.lane_select.currentData(),
        }
        self._turns = append_structured_turn(self._turns, role="user", text=message)
        self._busy = True
        self.set_status("sending...")
        self._refresh_send_enabled()
        self.apply_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        holder = _ChatWorker(payload)
        self._worker_holder = holder

        def on_ok(result: object) -> None:
            self._busy = False
            if not isinstance(result, dict):
                self.append("error", "bad harness response")
                self.set_status("idle")
                self._refresh_send_enabled()
                return
            reply = str(result.get("reply_text") or "")
            self.append("ai", reply)
            self._turns = append_structured_turn(
                self._turns, role="assistant", text=reply
            )
            for line in format_intent_presentation(
                result.get("intent_status"),
                result.get("supported_scope"),
            ):
                self.transcript.appendPlainText(line)
            lane = result.get("model_lane")
            model = result.get("model")
            if lane and model:
                self.append("model", f"{lane}: {model}")

            def on_meta(action: dict[str, Any]) -> None:
                self.append("meta", f"{action.get('kind')}: {action.get('text')}")

            logs, pending = prepare_actions(result, on_meta=on_meta, defer_confirm=True)
            for line in logs:
                self.append("tool", line)
            self._refresh_attach_label()
            scope = result.get("supported_scope")
            self._set_pending(
                pending,
                result.get("request_id"),
                intent_status=result.get("intent_status")
                if isinstance(result.get("intent_status"), str)
                else None,
                supported_scope=scope if isinstance(scope, dict) else None,
            )

        def on_fail(err: str) -> None:
            self._busy = False
            self.set_status("error")
            self.append("error", err)
            self._refresh_send_enabled()

        holder.gui_relay.finished.connect(on_ok)
        holder.gui_relay.failed.connect(on_fail)
        holder.thread.start()


_DOCK: AIChatDock | None = None


def ensure_chat_dock() -> AIChatDock:
    global _DOCK
    import FreeCADGui as Gui

    QtCore, _, QtWidgets = _qt()
    mw = Gui.getMainWindow()
    if _DOCK is not None:
        _DOCK.dock.show()
        _DOCK.dock.raise_()
        return _DOCK

    existing = mw.findChild(QtWidgets.QDockWidget, "FixtureChatDock")
    if existing is not None:
        # Stale dock from previous import — replace with fresh wrapper if needed
        existing.show()
        existing.raise_()

    dock_wrap = AIChatDock(mw)
    area = getattr(QtCore.Qt, "RightDockWidgetArea", None)
    if area is None:
        area = QtCore.Qt.DockWidgetArea.RightDockWidgetArea
    mw.addDockWidget(area, dock_wrap.dock)
    _DOCK = dock_wrap
    return dock_wrap


def get_chat_dock() -> AIChatDock | None:
    return _DOCK
