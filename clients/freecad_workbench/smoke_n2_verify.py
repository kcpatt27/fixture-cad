# FreeCAD Path B N2: inspect runners + post-Apply verify (deterministic + filter).
# Run:
# & "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -c "exec(open(r'...\\smoke_n2_verify.py', encoding='utf-8').read())"

from __future__ import annotations

import sys
import traceback
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parent
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

PASS = 0
FAIL = 0
LOG = CLIENT_ROOT / "_smoke_n2_last.txt"


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        line = f"PASS  {name}" + (f"  ({detail})" if detail else "")
    else:
        FAIL += 1
        line = f"FAIL  {name}" + (f"  ({detail})" if detail else "")
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def main() -> int:
    try:
        open(LOG, "w", encoding="utf-8").close()
    except Exception:
        pass
    print("=== Fixture FreeCAD N2 verify smoke ===", flush=True)
    try:
        import FreeCAD
        from fixture.action_runner import apply_pending, prepare_actions
        from fixture.client import HarnessClient
        from fixture.context import build_context
        from fixture.tools.create_parametric_box import run as create_box
        from fixture.tools.get_object import run as get_object
        from fixture.tools.list_document_objects import run as list_objects
        from fixture.verify import (
            VERIFY_MESSAGE,
            filter_verify_response,
            parse_created_names,
            post_apply_verify,
        )
    except Exception as exc:
        check("imports", False, str(exc))
        traceback.print_exc()
        return 1

    try:
        doc = FreeCAD.newDocument("Fixture_N2")
        FreeCAD.setActiveDocument(doc.Name)

        box_msg = create_box(
            {"width": 20, "height": 10, "depth": 5, "name": "N2Box"}
        )
        check("create box", "N2Box" in box_msg, box_msg)
        listed = list_objects({})
        check("list includes N2Box", "N2Box" in listed, listed[:120])
        detail = get_object({"object_name": "N2Box"})
        check("get_object N2Box", "N2Box" in detail and "volume=" in detail, detail[:160])

        fake_logs = [f"ok: create_parametric_box -> {box_msg}"]
        names = parse_created_names(fake_logs)
        check("parse created name", "N2Box" in names, str(names))

        verify_lines, inspection = post_apply_verify(fake_logs)
        check("verify lines present", bool(verify_lines), str(verify_lines[:3]))
        check(
            "inspection has tips",
            bool(inspection.get("tips")),
            str(inspection.get("tips")),
        )
        check(
            "inspection detail mentions box",
            "N2Box" in str(inspection.get("detail") or "")
            or "N2Box" in str(inspection.get("object_list") or ""),
            str(inspection.get("detail") or "")[:120],
        )

        client = HarnessClient()
        context = build_context()
        extra = dict(context.get("extra") or {})
        extra["inspection"] = inspection
        context["extra"] = extra
        resp = client.send_chat(
            {
                "app": "freecad",
                "version": "0.1.0",
                "context": context,
                "message": VERIFY_MESSAGE,
                "history": [],
                "mode": "explain",
                "model_lane": "accurate",
            }
        )
        filtered = filter_verify_response(resp)
        logs, pending = prepare_actions(filtered, defer_confirm=True)
        check("verify reply_text", bool(str(filtered.get("reply_text") or "").strip()))
        check(
            "verify leaves no confirm pending",
            not pending,
            str([p.tool_name for p in pending]),
        )

        # Chat -> pending -> Apply path for a fresh box name
        doc2 = FreeCAD.newDocument("Fixture_N2_Apply")
        FreeCAD.setActiveDocument(doc2.Name)
        before = len(doc2.Objects)
        plan = client.send_chat(
            {
                "app": "freecad",
                "version": "0.1.0",
                "context": build_context(),
                "message": "create a 15x15x15 mm box named SmokeN2",
                "history": [],
                "mode": "chat",
                "model_lane": "accurate",
            }
        )
        _logs, pending2 = prepare_actions(plan, defer_confirm=True)
        check("pre-Apply unchanged", len(doc2.Objects) == before, str(doc2.Objects))
        if not pending2:
            check("chat pending create", False, "no pending tools")
        else:
            apply_logs = apply_pending(pending2, client=client)
            check(
                "Apply mutates",
                len(doc2.Objects) > before,
                f"objs={doc2.Objects} logs={apply_logs[:2]}",
            )
            v_lines, v_insp = post_apply_verify(apply_logs)
            check("post-Apply verify lines", any("verify:" in ln for ln in v_lines), str(v_lines[:2]))
            check("post-Apply inspection tips", bool(v_insp.get("tips")), str(v_insp.get("tips")))

    except Exception as exc:
        check("smoke body", False, str(exc))
        traceback.print_exc()

    print(f"=== {PASS} pass / {FAIL} fail ===", flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(f"=== {PASS} pass / {FAIL} fail ===\n")
    except Exception:
        pass
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
