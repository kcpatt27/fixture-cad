from __future__ import annotations

from typing import Any


def json_safe_property(value: Any) -> str | int | float | bool | None:
    """Convert FreeCAD property wrappers to JSON-safe scalar values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    # FreeCAD.Units.Quantity (Length, Width, Height, Radius, etc.) exposes its
    # canonical numeric value here. Never pass the native wrapper to json.dumps.
    quantity_value = getattr(value, "Value", None)
    if isinstance(quantity_value, (int, float)):
        return float(quantity_value)

    return str(value)


def build_context() -> dict[str, Any]:
    import FreeCAD
    import FreeCADGui as Gui

    doc = FreeCAD.ActiveDocument
    selected: list[dict[str, Any]] = []
    try:
        for obj in Gui.Selection.getSelection():
            entry: dict[str, Any] = {
                "name": obj.Name,
                "type": obj.TypeId if hasattr(obj, "TypeId") else type(obj).__name__,
            }
            if hasattr(obj, "Shape") and obj.Shape is not None:
                try:
                    entry["shape"] = obj.Shape.ShapeType
                except Exception:  # noqa: BLE001
                    pass
            props: dict[str, Any] = {}
            for prop in ("Length", "Width", "Height", "Radius", "Label"):
                if hasattr(obj, prop):
                    try:
                        props[prop] = json_safe_property(getattr(obj, prop))
                    except Exception:  # noqa: BLE001
                        pass
            if props:
                entry["properties"] = props
            selected.append(entry)
    except Exception:  # noqa: BLE001
        selected = []

    workbench = ""
    try:
        workbench = Gui.activeWorkbench().name()
    except Exception:  # noqa: BLE001
        workbench = ""

    return {
        "active_document": doc.Name if doc else "",
        "workbench_or_mode": workbench,
        "selected_objects": selected,
        "extra": {},
    }
