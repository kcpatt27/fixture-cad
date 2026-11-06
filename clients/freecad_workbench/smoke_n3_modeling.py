# Fixture N3 modeling smoke: direct runners, then harness chat -> pending -> Apply.
# Run:
#   & "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" `
#     -c "exec(open(r'...\smoke_n3_modeling.py', encoding='utf-8').read())"

from __future__ import annotations

import sys
import traceback
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parent
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

PASS = 0
FAIL = 0


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


def _near(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(float(a) - float(b)) <= tol


def _check_hinge(doc, *, prefix: str) -> None:
    leaf_a = doc.getObject("LeafA")
    leaf_b = doc.getObject("LeafB")
    pin = doc.getObject("Pin")
    check(
        f"{prefix} LeafA",
        leaf_a is not None and leaf_a.TypeId == "Part::Feature" and not leaf_a.Shape.isNull(),
    )
    check(
        f"{prefix} LeafB",
        leaf_b is not None and leaf_b.TypeId == "Part::Feature" and not leaf_b.Shape.isNull(),
    )
    check(
        f"{prefix} Pin",
        pin is not None and pin.TypeId == "Part::Feature" and not pin.Shape.isNull(),
    )
    if leaf_b is not None:
        base = leaf_b.Placement.Base
        check(
            f"{prefix} LeafB z=8",
            _near(base.z, 8.0),
            f"z={base.z}",
        )
    if pin is not None:
        base = pin.Placement.Base
        check(
            f"{prefix} Pin placement",
            _near(base.x, 18.0) and _near(base.y, 8.0) and _near(base.z, 0.0),
            f"xyz=({base.x},{base.y},{base.z})",
        )
    chamfer = doc.getObject("LeafA_Chamfer")
    check(
        f"{prefix} LeafA chamfer",
        chamfer is not None and not chamfer.Shape.isNull(),
        chamfer.TypeId if chamfer else "missing",
    )


def _check_booleans(doc, *, prefix: str) -> None:
    cut = doc.getObject("CutBase")
    fuse = doc.getObject("PlateBoss")
    check(
        f"{prefix} CutBase",
        cut is not None
        and cut.TypeId == "Part::Cut"
        and not cut.Shape.isNull()
        and len(cut.Shape.Solids) >= 1,
    )
    check(
        f"{prefix} PlateBoss",
        fuse is not None
        and fuse.TypeId == "Part::Fuse"
        and not fuse.Shape.isNull()
        and len(fuse.Shape.Solids) >= 1,
    )
    # Base/tool kept in tree
    check(f"{prefix} Base kept", doc.getObject("Base") is not None)
    check(f"{prefix} Cutter kept", doc.getObject("Cutter") is not None)
    check(f"{prefix} Plate kept", doc.getObject("Plate") is not None)
    check(f"{prefix} Boss kept", doc.getObject("Boss") is not None)


def _direct_path() -> None:
    import FreeCAD

    from fixture.tools.add_chamfer import run as add_chamfer
    from fixture.tools.boolean_cut import run as boolean_cut
    from fixture.tools.boolean_fuse import run as boolean_fuse
    from fixture.tools.create_parametric_box import run as create_box
    from fixture.tools.create_parametric_cylinder import run as create_cyl
    from fixture.tools.transform_placement import run as transform_placement

    doc = FreeCAD.newDocument("Fixture_N3_Direct")
    FreeCAD.setActiveDocument(doc.Name)
    try:
        create_box({"width": 40, "height": 20, "depth": 4, "name": "LeafA"})
        create_box({"width": 40, "height": 20, "depth": 4, "name": "LeafB"})
        transform_placement({"object_name": "LeafB", "z": 8})
        create_cyl({"radius": 3, "height": 16, "name": "Pin"})
        transform_placement({"object_name": "Pin", "x": 18, "y": 8, "z": 0})
        add_chamfer({"size": 0.5, "object_name": "LeafA"})
        _check_hinge(doc, prefix="direct hinge")

        create_box({"width": 40, "height": 40, "depth": 20, "name": "Base"})
        create_cyl({"radius": 8, "height": 30, "name": "Cutter"})
        boolean_cut({"base_name": "Base", "tool_name": "Cutter", "name": "CutBase"})
        create_box({"width": 30, "height": 20, "depth": 10, "name": "Plate"})
        create_cyl({"radius": 5, "height": 12, "name": "Boss"})
        boolean_fuse({"base_name": "Plate", "tool_name": "Boss", "name": "PlateBoss"})
        _check_booleans(doc, prefix="direct bool")
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

    doc = FreeCAD.newDocument("Fixture_N3_Apply")
    FreeCAD.setActiveDocument(doc.Name)
    client = HarnessClient(timeout=180.0)
    try:
        response = client.send_chat(
            {
                "app": "freecad",
                "version": config.CLIENT_VERSION,
                "context": {
                    "active_document": doc.Name,
                    "workbench_or_mode": "Part",
                    "selected_objects": [],
                    "extra": {},
                },
                "message": (
                    "Build a hinge-like mockup with no joints: create a 40x20x4mm box "
                    "named LeafA, a 40x20x4mm box named LeafB then move LeafB to z=8, "
                    "create a cylinder named Pin with radius 3mm and height 16mm then "
                    "move Pin to x=18, y=8, z=0, and add a 0.5mm chamfer on LeafA. "
                    "Do not fuse the solids or add assembly constraints."
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
        required = {
            "create_parametric_box",
            "create_parametric_cylinder",
            "transform_placement",
            "add_chamfer",
        }
        check(
            "planner has hinge tools",
            required.issubset(set(tool_names)),
            str(tool_names),
        )
        check(
            "planner need_confirm",
            any(
                action.get("type") == "meta" and action.get("kind") == "need_confirm"
                for action in response.get("actions") or []
            ),
        )
        check(
            "planner no boolean",
            "boolean_cut" not in tool_names and "boolean_fuse" not in tool_names,
            str(tool_names),
        )

        logs, pending = prepare_actions(response, client=client, defer_confirm=True)
        check("pre-Apply document unchanged", len(doc.Objects) == 0, str(doc.Objects))
        check("pending not empty", len(pending) > 0, f"logs={logs}")

        apply_logs = apply_pending(pending, client=client, request_id=response.get("request_id"))
        ok_lines = [line for line in apply_logs if line.startswith("ok:")]
        check("Apply produced ok lines", len(ok_lines) > 0, "; ".join(apply_logs))
        _check_hinge(doc, prefix="Apply hinge")
    except Exception as exc:
        check("harness Apply chain", False, str(exc))
        traceback.print_exc()
    finally:
        FreeCAD.closeDocument(doc.Name)


def main() -> int:
    print("=== Fixture N3 modeling smoke ===", flush=True)
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
