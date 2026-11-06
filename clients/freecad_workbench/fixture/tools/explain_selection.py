from __future__ import annotations

from typing import Any

from .base import ToolRunner


def _selected_objects() -> list[Any]:
    try:
        import FreeCADGui as Gui

        if hasattr(Gui, "Selection"):
            sel = Gui.Selection.getSelection()
            if sel:
                return list(sel)
    except Exception:  # noqa: BLE001
        pass
    import FreeCAD

    doc = FreeCAD.ActiveDocument
    if doc is None:
        return []
    # Headless fallback: active object or all objects
    if getattr(doc, "ActiveObject", None) is not None:
        return [doc.ActiveObject]
    return list(doc.Objects)


def run(args: dict[str, Any]) -> str:
    sel = _selected_objects()
    if not sel:
        return "Nothing selected."
    lines = []
    for obj in sel:
        typ = getattr(obj, "TypeId", type(obj).__name__)
        label = getattr(obj, "Label", obj.Name)
        lines.append(f"{label} ({obj.Name}): {typ}")
        if hasattr(obj, "Shape") and obj.Shape is not None:
            try:
                lines.append(
                    f"  shape={obj.Shape.ShapeType} volume={obj.Shape.Volume:.3f}"
                )
            except Exception:  # noqa: BLE001
                pass
    focus = args.get("focus")
    if focus:
        lines.append(f"focus={focus}")
    return "\n".join(lines)


RUNNER = ToolRunner(name="explain_selection", permission="auto", run=run)
