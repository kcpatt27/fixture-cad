# Fixture chat worker thread-affinity smoke.
# Run:
#   & "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" `
#     -c "exec(open(r'...\smoke_chat_threading.py', encoding='utf-8').read())"

from __future__ import annotations

import sys
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parent
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

from PySide6 import QtCore

import fixture.ai_chat_dock as chat_dock


def _exercise_worker(*, fail: bool) -> dict[str, object]:
    state: dict[str, object] = {}
    loop = QtCore.QEventLoop()

    class FakeHarnessClient:
        def send_chat(self, payload: dict[str, object]) -> dict[str, object]:
            state["worker_thread"] = QtCore.QThread.currentThread()
            if payload.get("fail"):
                raise RuntimeError("expected thread smoke failure")
            return {"reply_text": "thread smoke", "payload": payload}

    original_client = chat_dock.HarnessClient
    chat_dock.HarnessClient = FakeHarnessClient
    holder = chat_dock._ChatWorker({"message": "thread smoke", "fail": fail})

    def on_ok(result: object) -> None:
        state["callback_thread"] = QtCore.QThread.currentThread()
        state["result"] = result
        loop.quit()

    def on_fail(error: str) -> None:
        state["callback_thread"] = QtCore.QThread.currentThread()
        state["error"] = error
        loop.quit()

    holder.gui_relay.finished.connect(on_ok)
    holder.gui_relay.failed.connect(on_fail)
    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(5000)
    holder.thread.start()
    loop.exec()
    holder.thread.quit()
    holder.thread.wait(5000)
    chat_dock.HarnessClient = original_client
    return state


def main() -> int:
    app = QtCore.QCoreApplication.instance()
    owns_app = app is None
    if app is None:
        app = QtCore.QCoreApplication([])

    success = _exercise_worker(fail=False)
    failure = _exercise_worker(fail=True)

    checks = {
        "success result relayed": isinstance(success.get("result"), dict),
        "success worker off main": success.get("worker_thread") != app.thread(),
        "success callback on main": success.get("callback_thread") == app.thread(),
        "failure relayed": "expected thread smoke failure" in str(failure.get("error")),
        "failure worker off main": failure.get("worker_thread") != app.thread(),
        "failure callback on main": failure.get("callback_thread") == app.thread(),
    }
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}  {name}", flush=True)
    print(
        f"summary: {sum(checks.values())} pass / "
        f"{len(checks) - sum(checks.values())} fail",
        flush=True,
    )
    if owns_app:
        app.quit()
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
