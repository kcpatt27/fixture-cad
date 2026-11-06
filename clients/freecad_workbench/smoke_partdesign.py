# Fixture PartDesign smoke: direct runners, then harness chat -> pending -> Apply.
# Run:
#   & "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" `
#     -c "exec(open(r'...\smoke_partdesign.py', encoding='utf-8').read())"

from __future__ import annotations

import sys
import traceback
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parent
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

PASS = 0
FAIL = 0

EXPECTED_TOOLS = [
    "create_body",
    "new_sketch",
    "sketch_rectangle",
    "pad_sketch",
    "new_sketch",
    "sketch_rectangle",
    "pocket_sketch",
]


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        prefix = "PASS"
    else:
        FAIL += 1
        prefix = "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"{prefix}  {name}{suffix}", flush=True)


def _support_role(sketch) -> str:
    support = sketch.AttachmentSupport
    if isinstance(support, (list, tuple)) and support:
        target = support[0]
        if isinstance(target, (list, tuple)) and target:
            target = target[0]
        return str(getattr(target, "Role", ""))
    return str(getattr(support, "Role", ""))


def _check_result(doc, *, prefix: str) -> None:
    body = doc.getObject("BracketBody")
    sketch = doc.getObject("Profile")
    pad = doc.getObject("BracketPad")
    cut_sketch = doc.getObject("CutProfile")
    pocket = doc.getObject("BracketPocket")
    check(f"{prefix} Body", body is not None and body.TypeId == "PartDesign::Body")
    check(
        f"{prefix} Sketch",
        sketch is not None
        and sketch.TypeId == "Sketcher::SketchObject"
        and int(sketch.GeometryCount) == 4,
        f"role={_support_role(sketch) if sketch else '?'}",
    )
    check(
        f"{prefix} XY support",
        sketch is not None and _support_role(sketch) == "XY_Plane",
        _support_role(sketch) if sketch else "missing",
    )
    check(
        f"{prefix} Pad",
        pad is not None
        and abs(float(pad.Length.Value) - 10.0) <= 1e-9
        and not pad.Shape.isNull()
        and len(pad.Shape.Solids) == 1,
    )
    check(
        f"{prefix} Cut Sketch",
        cut_sketch is not None
        and cut_sketch.TypeId == "Sketcher::SketchObject"
        and int(cut_sketch.GeometryCount) == 4
        and _support_role(cut_sketch) == "XY_Plane",
        f"role={_support_role(cut_sketch) if cut_sketch else '?'}",
    )
    check(
        f"{prefix} Pocket",
        pocket is not None
        and abs(float(pocket.Length.Value) - 5.0) <= 1e-9
        and bool(pocket.Reversed)
        and not pocket.Shape.isNull()
        and len(pocket.Shape.Solids) == 1
        and abs(float(pocket.Shape.Volume) - 7000.0) <= 1e-6,
        f"volume={float(pocket.Shape.Volume) if pocket else '?'}",
    )


def _direct_path() -> None:
    import FreeCAD

    from fixture.tools.create_body import run as create_body
    from fixture.tools.new_sketch import run as new_sketch
    from fixture.tools.pad_sketch import run as pad_sketch
    from fixture.tools.pocket_sketch import run as pocket_sketch
    from fixture.tools.sketch_rectangle import run as sketch_rectangle

    doc = FreeCAD.newDocument("Fixture_PartDesign_Direct")
    FreeCAD.setActiveDocument(doc.Name)
    try:
        create_body({"name": "BracketBody"})
        new_sketch({"body_name": "BracketBody", "plane": "XY", "name": "Profile"})
        sketch_rectangle(
            {
                "sketch_name": "Profile",
                "x": 0,
                "y": 0,
                "width": 40,
                "height": 20,
            }
        )
        pad_sketch({"sketch_name": "Profile", "length": 10, "name": "BracketPad"})
        new_sketch({"body_name": "BracketBody", "plane": "XY", "name": "CutProfile"})
        sketch_rectangle(
            {
                "sketch_name": "CutProfile",
                "x": 10,
                "y": 5,
                "width": 20,
                "height": 10,
            }
        )
        pocket_sketch(
            {
                "sketch_name": "CutProfile",
                "length": 5,
                "reversed": True,
                "name": "BracketPocket",
            }
        )
        _check_result(doc, prefix="direct")
    except Exception as exc:
        check("direct runner chain", False, str(exc))
        traceback.print_exc()
    finally:
        FreeCAD.closeDocument(doc.Name)


def _harness_apply_path() -> None:
    import FreeCAD

    from fixture import config
    from fixture.action_runner import apply_pending, prepare_actions
    from fixture.client import HarnessClient

    doc = FreeCAD.newDocument("Fixture_PartDesign_Apply")
    FreeCAD.setActiveDocument(doc.Name)
    client = HarnessClient(timeout=180.0)
    try:
        response = client.send_chat(
            {
                "app": "freecad",
                "version": config.CLIENT_VERSION,
                "context": {
                    "active_document": doc.Name,
                    "workbench_or_mode": "PartDesign",
                    "selected_objects": [],
                    "extra": {},
                },
                "message": (
                    "Create a PartDesign Body named BracketBody. On its XY plane "
                    "create a Sketch named Profile with a 40mm by 20mm rectangle "
                    "starting at x=0, y=0, then Pad that sketch 10mm and name the "
                    "feature BracketPad. On the same Body XY plane create a second "
                    "Sketch named CutProfile with a 20mm by 10mm rectangle starting "
                    "at x=10, y=5. Pocket CutProfile 5mm in the reversed direction "
                    "and name the feature BracketPocket."
                ),
                "mode": "chat",
                "model_lane": "accurate",
            }
        )
        tool_names = [
            action.get("tool_name")
            for action in response.get("actions") or []
            if action.get("type") == "tool_call"
        ]
        check("planner tool order", tool_names == EXPECTED_TOOLS, str(tool_names))
        check(
            "planner need_confirm",
            any(
                action.get("type") == "meta" and action.get("kind") == "need_confirm"
                for action in response.get("actions") or []
            ),
        )

        logs, pending = prepare_actions(response, client=client, defer_confirm=True)
        check(
            "all tools pending",
            [item.tool_name for item in pending] == EXPECTED_TOOLS,
            f"pending={[item.tool_name for item in pending]} logs={logs}",
        )
        check("pre-Apply document unchanged", len(doc.Objects) == 0, str(doc.Objects))

        apply_logs = apply_pending(pending, client=client, request_id=response.get("request_id"))
        check(
            "Apply all tools",
            all(any(f"ok: {tool}" in line for line in apply_logs) for tool in EXPECTED_TOOLS),
            "; ".join(apply_logs),
        )
        _check_result(doc, prefix="Apply")
    except Exception as exc:
        check("harness Apply chain", False, str(exc))
        traceback.print_exc()
    finally:
        FreeCAD.closeDocument(doc.Name)


def main() -> int:
    print("=== Fixture PartDesign pad and pocket smoke ===", flush=True)
    try:
        import FreeCAD as App

        print("FreeCAD:", ".".join(str(value) for value in App.Version()[:3]), flush=True)
        import fixture  # noqa: F401
    except Exception as exc:
        check("FreeCAD/fixture import", False, str(exc))
        return 1

    _direct_path()
    _harness_apply_path()
    print(f"summary: {PASS} pass / {FAIL} fail", flush=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
