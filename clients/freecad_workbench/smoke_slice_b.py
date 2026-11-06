# Fixture Slice B smoke: SVG import + STL export (direct + harness Apply).
# GUI file dialog for attach_reference_image is NOT exercised headless.
# Run (harness on 127.0.0.1:8766):
#   & "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" `
#     -c "exec(open(r'...\smoke_slice_b.py', encoding='utf-8').read())"

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parent
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

PASS = 0
FAIL = 0

RECT_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="60mm" viewBox="0 0 100 60">
  <rect x="0" y="0" width="100" height="60" fill="none" stroke="black" stroke-width="0.5"/>
</svg>
"""


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


def _write_temp_svg(text: str, *, name: str = "rect-outline.svg") -> Path:
    folder = Path(tempfile.mkdtemp(prefix="fixture_slice_b_"))
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def _oversized_svg() -> str:
    # >64 separate path-like shapes to trip MAX_PATHS
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400">',
    ]
    for i in range(70):
        x = (i % 10) * 10
        y = (i // 10) * 10
        parts.append(
            f'<rect x="{x}" y="{y}" width="8" height="8" '
            f'fill="none" stroke="black"/>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def _direct_path() -> None:
    import FreeCAD

    from fixture.reference_store import get_store
    from fixture.tools.create_parametric_box import run as create_box
    from fixture.tools.export_stl import run as export_stl
    from fixture.tools.import_svg_sketch import run as import_svg

    store = get_store()
    store.clear()

    svg_path = _write_temp_svg(RECT_SVG)
    try:
        meta = store.attach(svg_path)
        check(
            "store attach svg",
            meta.get("media_type") == "image/svg+xml" and meta.get("file_name") == svg_path.name,
            str(meta),
        )

        doc = FreeCAD.newDocument("Fixture_SliceB_Direct")
        FreeCAD.setActiveDocument(doc.Name)
        try:
            result = import_svg({"name": "Outline"})
            sketch = doc.getObject("Outline")
            # Sketch may live inside a Body; search by Label if Name differs.
            if sketch is None:
                for obj in doc.Objects:
                    if getattr(obj, "Label", "") == "Outline" or obj.Name == "Outline":
                        sketch = obj
                        break
            body = None
            for obj in doc.Objects:
                if obj.isDerivedFrom("PartDesign::Body"):
                    body = obj
                    break
            check("direct import message", "imported sketch Outline" in result, result)
            geom_count = getattr(sketch, "GeometryCount", None) if sketch else None
            check(
                "direct Body+Sketch",
                body is not None and sketch is not None and (geom_count or 0) >= 1,
                f"doc={doc.Name} objects={[o.Name for o in doc.Objects]} "
                f"body={getattr(body, 'Name', None)} geom={geom_count}",
            )

            create_box({"width": 100, "height": 60, "depth": 25, "name": "RemoteShell"})
            export_result = export_stl({"path": "remote.stl", "object_names": ["RemoteShell"]})
            check("direct export message", "exported STL" in export_result, export_result)
            out_file = None
            for token in export_result.split():
                if token.endswith(".stl") and "\\" in token or token.endswith("remote.stl"):
                    # path may contain spaces? our policy forbids spaces in filename
                    candidate = Path(token)
                    if candidate.suffix == ".stl":
                        out_file = candidate
                        break
            # Robust parse: last path-like token ending .stl
            for token in export_result.replace("(", " ").replace(")", " ").split():
                if token.lower().endswith(".stl"):
                    out_file = Path(token)
            check(
                "direct STL exists",
                out_file is not None and out_file.is_file() and out_file.stat().st_size > 0,
                str(out_file),
            )
        except Exception as exc:
            check("direct runner chain", False, str(exc))
            traceback.print_exc()
        finally:
            FreeCAD.closeDocument(doc.Name)
    finally:
        store.clear()

    # Fail-closed oversized SVG
    store.clear()
    fat = _write_temp_svg(_oversized_svg(), name="fat.svg")
    doc2 = FreeCAD.newDocument("Fixture_SliceB_Cap")
    FreeCAD.setActiveDocument(doc2.Name)
    try:
        store.attach(fat)
        raised = False
        try:
            import_svg({"name": "TooMany"})
        except Exception as exc:
            raised = True
            check(
                "oversized SVG fail-closed",
                "cap" in str(exc).lower() or "exceed" in str(exc).lower(),
                str(exc),
            )
        if not raised:
            check("oversized SVG fail-closed", False, "expected RuntimeError")
        check(
            "oversized left no sketch",
            doc2.getObject("TooMany") is None,
            str([o.Name for o in doc2.Objects]),
        )
    except Exception as exc:
        check("oversized SVG harness", False, str(exc))
        traceback.print_exc()
    finally:
        store.clear()
        FreeCAD.closeDocument(doc2.Name)


def _harness_apply_path() -> None:
    import FreeCAD

    from fixture import config
    from fixture.action_runner import apply_pending, prepare_actions
    from fixture.client import HarnessClient
    from fixture.reference_store import get_store
    from fixture.tools.create_parametric_box import run as create_box

    store = get_store()
    store.clear()
    svg_path = _write_temp_svg(RECT_SVG, name="bench-outline.svg")
    store.attach(svg_path)

    doc = FreeCAD.newDocument("Fixture_SliceB_Apply")
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
                    "extra": {"reference_image": store.metadata()},
                },
                "message": (
                    "Trace the attached SVG outline into a sketch named Outline "
                    "and pad it 8 mm. Do not export."
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
        check(
            "planner has import+pad",
            "import_svg_sketch" in tool_names and "pad_sketch" in tool_names,
            str(tool_names),
        )
        check(
            "planner need_confirm",
            any(
                action.get("type") == "meta" and action.get("kind") == "need_confirm"
                for action in response.get("actions") or []
            ),
        )
        check("planner no export", "export_stl" not in tool_names, str(tool_names))

        logs, pending = prepare_actions(response, client=client, defer_confirm=True)
        check("pre-Apply document empty", len(doc.Objects) == 0, str(doc.Objects))
        check("pending not empty", len(pending) > 0, f"logs={logs}")

        apply_logs = apply_pending(pending, client=client, request_id=response.get("request_id"))
        ok_lines = [line for line in apply_logs if line.startswith("ok:")]
        check("Apply import/pad ok", len(ok_lines) > 0, "; ".join(apply_logs))
        sketch = doc.getObject("Outline")
        check(
            "Apply sketch present",
            sketch is not None,
            str([o.Name for o in doc.Objects]),
        )

        # Export path: create a solid then ask planner to export
        create_box({"width": 40, "height": 20, "depth": 10, "name": "ExportBox"})
        export_response = client.send_chat(
            {
                "app": "freecad",
                "version": config.CLIENT_VERSION,
                "context": {
                    "active_document": doc.Name,
                    "workbench_or_mode": "Part",
                    "selected_objects": [
                        {
                            "name": "ExportBox",
                            "type": "Part::Feature",
                            "shape": "Solid",
                        }
                    ],
                    "extra": {},
                },
                "message": "Export ExportBox as sliceb.stl",
                "mode": "chat",
                "model_lane": "accurate",
            }
        )
        export_tools = [
            action.get("tool_name")
            for action in export_response.get("actions") or []
            if action.get("type") == "tool_call"
        ]
        check("planner export_stl", "export_stl" in export_tools, str(export_tools))
        _, export_pending = prepare_actions(
            export_response, client=client, defer_confirm=True
        )
        export_logs = apply_pending(
            export_pending,
            client=client,
            request_id=export_response.get("request_id"),
        )
        check(
            "Apply export ok",
            any(line.startswith("ok: export_stl") for line in export_logs),
            "; ".join(export_logs),
        )
    except Exception as exc:
        check("harness Apply chain", False, str(exc))
        traceback.print_exc()
    finally:
        store.clear()
        FreeCAD.closeDocument(doc.Name)


def main() -> int:
    print("=== Fixture Slice B smoke ===", flush=True)
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
