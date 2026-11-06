# Blender Addon Design

Target: Blender **5.2**.

## Module layout

```
clients/blender_addon/
  fixture_blender/
    __init__.py               # bl_info, register/unregister
    config.py
    client.py                 # HarnessClient
    context.py                # scene / selection snapshot
    panel.py                  # VIEW_3D UI sidebar panel
    operators.py              # Send chat, explain, apply confirm
    action_runner.py
    tools/
      __init__.py
      explain_selection.py
      fit_view_selection.py
      clean_mesh.py
      clean_scan.py
```

## bl_info

```python
bl_info = {
    "name": "Fixture",
    "author": "Kalen",
    "version": (0, 2, 0),
    "blender": (5, 2, 0),
    "location": "View3D > Sidebar > Fixture",
    "description": "Chat-driven CAD tools via local Fixture harness",
    "category": "3D View",
}
```

## Panel UI

- Region: `VIEW_3D`, space `UI`, category **Fixture**
- Transcript (scrollable labels or `UIList` / text property)
- Message string property + Send operator
- Model selector: Accurate, Fast, or Auto; defaults to Accurate
- Confirm-tier tools stay pending behind **Apply** / **Cancel**
- Status string property
- Native Blender boxes separate status, conversation, composer, and confirmation
- Built-in Blender icons identify Send, Explain, Apply, Cancel, and status
- Long transcript entries wrap into bounded display lines instead of clipping
- Pending confirmation uses the host theme's alert state; no custom palette
- Bounded `history` plus intent/scope transcript lines; Send/Explain disabled
  while pending tools await Apply/Cancel

Blender UI is redraw-based; store transcript on an addon Scene property or module-level list and `tag_redraw`.

## Async pattern

Blender’s Python is mostly main-thread. Options for v1 skeleton:

1. **Synchronous HTTP with short timeout** + status message (acceptable for local Ollama if user accepts brief freeze), or
2. **`threading.Thread`** + `bpy.app.timers` to apply results on main thread (preferred).

Do not call `bpy` from the worker thread — only marshal a result dict back.

## Shared tools

| Tool | Implementation sketch |
|------|------------------------|
| `explain_selection` | Summarize `context.selected_objects` locally if needed |
| `fit_view_selection` | `bpy.ops.view3d.view_selected()` with context override |
| `clean_mesh` | Edit mode merge-by-distance on selected mesh objects |
| `clean_scan` | Import STL/OBJ/PLY scan, merge/fill/recalc, optional voxel remesh + decimate, export STL |

`clean_scan` produces a repaired **mesh** and STL, watertight when repair
succeeds, and reports the measured manifold status rather than assuming success.
It does not reconstruct editable B-Rep geometry.

After successful Apply of confirm-tier tools, the addon fits the view, gathers
mesh/selection facts, appends a deterministic `verify:` transcript, then may
send one grounded `mode=explain` chat with `context.extra.inspection`. Confirm-
tier tools from that verify reply are never staged.

`create_parametric_box` / `create_parametric_cylinder` / `transform_placement` /
`boolean_cut` / `boolean_fuse` / `add_fillet` / `add_chamfer` are FreeCAD-only —
addon must ignore unknown tools gracefully.

## Install

Run `clients/blender_addon/install_addon.py` with Blender 5.2. The script packages the source, installs it in the user profile, enables **Fixture**, and saves preferences. See the addon README for the command.
