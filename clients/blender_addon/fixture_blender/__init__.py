bl_info = {
    "name": "Fixture",
    "author": "Kalen",
    "version": (0, 2, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > Fixture",
    "description": "Chat-driven CAD tools via local Fixture harness",
    "category": "3D View",
}

try:
    import bpy  # noqa: F401
except ModuleNotFoundError:  # headless tests: no Blender
    operators = panel = None
else:
    from . import operators, panel


def register() -> None:
    if operators is None or panel is None:
        return
    operators.register()
    panel.register()


def unregister() -> None:
    if operators is None or panel is None:
        return
    panel.unregister()
    operators.unregister()


if __name__ == "__main__":
    register()
