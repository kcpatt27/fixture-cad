# Tool Registry — Fixture

Tools are the only way the harness mutates (or asks to mutate) CAD state in v1. Definitions live in [`tools/`](tools/) as JSON and are loaded by the harness at startup.

## Tool record shape

```json
{
  "name": "create_parametric_box",
  "description": "Create a box solid with width/height/depth in mm.",
  "permission": "confirm",
  "apps": ["freecad"],
  "args_schema": {
    "type": "object",
    "required": ["width", "height", "depth"],
    "properties": {
      "width": { "type": "number", "exclusiveMinimum": 0 },
      "height": { "type": "number", "exclusiveMinimum": 0 },
      "depth": { "type": "number", "exclusiveMinimum": 0 },
      "name": { "type": "string" }
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `name` | Stable id used in `tool_call.tool_name` |
| `description` | Shown to the model |
| `permission` | `auto` \| `confirm` \| `deny` (see [safety-ux.md](safety-ux.md)) |
| `apps` | Which clients implement this tool |
| `args_schema` | JSON Schema for `args` |

## Seed tools (v1)

| Name | Apps | Permission | Purpose |
|------|------|------------|---------|
| `explain_selection` | freecad, blender | auto | Summarize selection (often reply-only; tool may return structured facts for the harness) |
| `fit_view_selection` | freecad, blender | auto | Frame camera on selection |
| `list_document_objects` | freecad | auto | Read-only list of document objects (name/type/label) |
| `get_object` | freecad | auto | Read-only facts for one object by name |
| `create_parametric_box` | freecad | confirm | Create box solid |
| `create_parametric_cylinder` | freecad | confirm | Create cylinder solid |
| `transform_placement` | freecad | confirm | Set absolute placement (mm + Euler degrees) |
| `boolean_cut` | freecad | confirm | Part::Cut base minus tool (new result) |
| `boolean_fuse` | freecad | confirm | Part::Fuse base with tool (new result) |
| `add_fillet` | freecad | confirm | Fillet edges on selection |
| `add_chamfer` | freecad | confirm | Chamfer edges on selection |
| `clean_mesh` | blender | confirm | Basic mesh cleanup (merge by distance / remove doubles style) |
| `clean_scan` | blender | confirm | Scan mesh (STL/OBJ/PLY) → repaired STL with reported manifold status (not B-Rep) |
| `create_body` | freecad | confirm | Create native PartDesign Body |
| `new_sketch` | freecad | confirm | Attach empty sketch to a Body origin plane |
| `sketch_rectangle` | freecad | confirm | Add one constrained rectangle to an empty sketch |
| `pad_sketch` | freecad | confirm | Pad a closed sketch into a solid |
| `pocket_sketch` | freecad | confirm | Cut a finite-length Pocket from a closed sketch |
| `attach_reference_image` | freecad | auto | Attach a local reference image; basename metadata only |
| `import_svg_sketch` | freecad | confirm | Import the client-attached SVG as a sketch (fail-closed) |
| `export_stl` | freecad | confirm | Export solids under `fixture_exports/*.stl` |

### Part multi-solid (N3)

Box, cylinder, placement, boolean cut/fuse, fillet, and chamfer operate on
document-level `Part::Feature` solids (and `Part::Cut` / `Part::Fuse` /
`Part::Chamfer` / `Part::Fillet` results). Booleans create a **new** result
object and leave base and tool in the tree. Placement uses absolute millimetres
and Euler degrees (`rx`/`ry`/`rz`); omitted axes keep current values. This path
is independent of PartDesign Body chains. Assemblies/joints and `hole_feature`
remain deferred.

### PartDesign chain

A padded rectangle is four explicit calls:

1. `create_body({"name": "BracketBody"})`
2. `new_sketch({"body_name": "BracketBody", "plane": "XY", "name": "Profile"})`
3. `sketch_rectangle({"sketch_name": "Profile", "width": 40, "height": 20})`
4. `pad_sketch({"sketch_name": "Profile", "length": 10, "name": "Pad"})`

All four calls are confirm-tier. Clients keep the full chain pending until
Apply, or discard it without changing the document on Cancel.

A finite rectangular pocket adds three calls after the Pad:

5. `new_sketch({"body_name": "BracketBody", "plane": "XY", "name": "CutProfile"})`
6. `sketch_rectangle({"sketch_name": "CutProfile", "x": 10, "y": 5, "width": 20, "height": 10})`
7. `pocket_sketch({"sketch_name": "CutProfile", "length": 5, "reversed": true, "name": "BracketPocket"})`

The second sketch still attaches to the Body-local origin plane. Face-attached
profiles and through-all Pocket mode remain deferred.

## Model guidance

System prompt must instruct:

1. Prefer `tool_call` over inventing FreeCAD/Blender Python.
2. Only use tools listed for the current `app`.
3. Never emit `type: "python"`.
4. Use `meta` with `need_confirm` when proposing confirm-tier tools.

## Extending

1. Add `docs/tools/<name>.json`.
2. Document in this table.
3. Implement runner in each listed client.
4. Restart harness (registry reload).
