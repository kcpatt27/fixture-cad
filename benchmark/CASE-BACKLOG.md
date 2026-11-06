# Fixture bench + tooling case backlog

Pull-from list for future Path A cases and registry tools.  
**Do not treat this as a build queue** — pick IDs when ready; implement tools *before* cases that require them.

Sources consulted: FreeCAD PartDesign docs/API, Blender mesh/modifier APIs,
ToolFailBench failure taxonomy
([arXiv:2607.04686](https://arxiv.org/html/2607.04686v1)), and a read-only
2026-07-21 audit of `neka-nat/freecad-mcp` at `22a7d7b`. The MCP is a
capability/UX reference only; arbitrary Python, unrestricted object/property
mutation, unauthenticated RPC, and remote binding are explicitly excluded.

## Legend

| Field | Meaning |
|-------|---------|
| **ID** | Suggested case / tool id |
| **Need** | `cases-only` = works with current seed tools; `needs-tool` = registry + client runner first |
| **Apps** | `fc` FreeCAD · `bl` Blender · `both` |
| **Tier** | `P0` discriminating now · `P1` after small tool add · `P2` richer CAD · `P3` long-horizon / research |
| **Failure** | ToolFailBench-ish mode the case is meant to provoke |

Failure modes: **TS** tool-skip · **UTU** unnecessary tool · **WA** wrong args · **WO** wrong tool/order · **XF** cross-app bleed · **NC** missing need_confirm · **MS** multi-step incomplete · **PR** parse/schema break

---

## Already shipped (do not re-add)

Seed tools: `explain_selection`, `fit_view_selection`, `create_parametric_box`, `add_fillet`, `clean_mesh`.

PartDesign padded rectangle slice: `create_body`, `new_sketch`,
`sketch_rectangle`, `pad_sketch`; case `fc-partdesign-pad-rectangle`.

N3 Part multi-solid: `create_parametric_cylinder`, `transform_placement`,
`boolean_cut`, `boolean_fuse`, `add_chamfer`; Path A tag `n3`.

| ID | Notes |
|----|--------|
| `fc-create-box-basic` | basic W×H×D |
| `fc-create-box-named` | named box |
| `fc-box-dims-order` | harden WxHxD |
| `fc-box-depth-first-wording` | hard depth-first wording |
| `fc-box-then-fit` | hard multi create+fit |
| `fc-add-fillet` | 2mm fillet |
| `fc-fillet-named-halfmm` | hard named + 0.5mm |
| `fc-cyl-basic` / `fc-cyl-named` | N3 cylinder |
| `fc-move-box-origin` | N3 place |
| `fc-bool-cut-named` / `fc-bool-fuse-named` | N3 boolean |
| `fc-chamfer-1mm` | N3 chamfer |
| `fc-hinge-mockup-multi` | N3 three-solid mockup |
| `fc-explain-selection` / `fc-explain-must-tool` | explain |
| `fc-fit-view` | fit |
| `fc-no-blender-tool` / `fc-refuse-mesh-clean` | cross-app refuse |
| `bl-clean-mesh` / `bl-clean-mesh-threshold` | clean |
| `bl-clean-then-fit` | hard multi clean+fit |
| `bl-explain-selection` / `bl-fit-view` | auto |
| `bl-no-freecad-tool` / `bl-refuse-partdesign` / `bl-refuse-pad-extrude` | refuse |

---

## Roadmap-linked novice enablement

`ROADMAP.md` (repo root) owns sequencing. **N1–N3 shipped; ideation Slice A + Slice B
shipped** (tag `ideation` / `n4` / `slice-b`). Slice C vision, DXF, Blender
attach, through-all Pocket, assemblies stay deferred until the maintainer opens them.
Pack doc: `docs/research/ideation-to-cad-pack.md`.

### N1. Capability-aware conversation — shipped (Path A tag `n1`)

| ID | Prompt sketch | Expected behavior | Failure |
|----|---------------|-------------------|---------|
| `fc-clarify-ambiguous-hinge` | "make an interlocking hinge in plastic" | ask geometry/use clarification; no mutation yet | UTU/MS |
| `fc-refuse-overclaim-hinge` | complete hinge via one Pad | refuse overclaim; unsupported/ambiguous/honest partial | UTU/TS |
| `fc-offer-partial-scope` | "make a hinge; start with anything you can" | bounded start + confirm; do not claim full hinge | NC/MS |
| `fc-partial-scope-accepted` | user accepts proposed base plate (uses `history`) | emit supported/partial chain with confirmation | MS/NC |
| `fc-capability-answer-specific` | "can you make hinge barrels and a pin?" | answer from current tools; invent no tools | UTU |
| `bl-clarify-cross-app-object` | parametric mechanical part in Blender | clarify/limit; no pending mutating tools after sanitize | XF/UTU |

**Evidence:** Accurate `20260721T233824Z` **96.5%**; Fast `20260721T233851Z`
**98.2%**. FreeCAD Path B `smoke_n1_intent.py` **9/0**; Blender
`smoke_n1_intent.py` **4/0**.

### N2. Guided verification loop — shipped (Path A tag `n2`)

After Apply, clients select tip objects, fit view, run read-only inspect
(`list_document_objects` / `get_object` on FreeCAD; mesh facts on Blender),
append a deterministic `verify:` transcript, then may send one grounded
`mode=explain` chat with `context.extra.inspection`. Confirm-tier tools from
that verify reply are never staged. Vision stays P2.

| ID | Need | Prompt / trigger sketch | Expected behavior | Tier | Failure |
|----|------|-------------------------|-------------------|------|---------|
| `fc-post-apply-fit` | existing `fit_view_selection` + client orchestration | after Apply of create/pad chain | auto or planner-emitted fit on new result; camera frames selection | P1 | TS/MS |
| `fc-post-apply-summary` | read-only inspect facts in context | after Apply | reply cites **actual** object names, types, and dims from inspection | P1 | UTU/WA |
| `fc-partial-result-next-step` | planner policy + N1 remainder | after partial Apply | restate unsupported remainder; offer **one** bounded next step | P1 | MS/UTU |
| `fc-inspect-body-features` | `get_object` / list tools | "what did we just make?" with Body/Pad | structured facts; no mutation | P1 | UTU |
| `bl-post-apply-summary` | Blender inspect or selection explain | after clean_mesh Apply | summarize mesh counts/selection from live scene | P1 | UTU |
| `fc-view-snapshot` | needs-tool + future vision lane | capture focused viewport | image stays local; no arbitrary filesystem browse | P2 | — |

**Evidence:** Accurate `20260722T010523Z` **100%** (42.0/42.0). FreeCAD Path B
`smoke_n2_verify.py` **13/0**; Blender Path B `smoke_n2_verify.py` **8/0**.

### N3. Practical modeling pack — shipped

**Status (2026-07-24):** FreeCAD Part-path tools `create_parametric_cylinder`,
`transform_placement`, `boolean_cut`, `boolean_fuse`, `add_chamfer` (hole
deferred). Booleans create a new result and keep base/tool. Placement uses
absolute mm + Euler degrees (omit axis = leave current). Path A tag `n3`
Accurate **100%** (`20260724T143442Z`, 56.0/56.0). FreeCAD Path B
`smoke_n3_modeling.py` **24/0** (direct hinge + booleans + chat→Apply hinge
mockup). Hinge mockup = three unfused solids (LeafA, LeafB, Pin); no assemblies.

### N4 / Pack `ideation-p1` — Slice A + Slice B shipped

Source: `docs/research/ideation-to-cad-pack.md`. Tag: `ideation` (also `n4`);
Slice B cases also `slice-b`. Slice A = planner policy on **existing** tools
(history-only brief; no `record_design_brief`). Slice B = attach /
`import_svg_sketch` / `export_stl` (FreeCAD-only; DXF + Blender deferred).
Slice C (vision) stays deferred.

**Locks (A):** history-only soft brief in `reply_text`; enclosure partial prefers
`create_parametric_box`; generative bone chair → hard `unsupported`.

**Locks (B):** metadata-only `reference_image`; SVG no path arg; export
filename-only under `fixture_exports/`; fail-closed path/edge caps.

**Evidence:** Slice A Accurate `20260724T145835Z` **100%** (51.0/51.0).
Slice B Accurate `--tag slice-b` `20260728T183409Z` **100%** (40.0/40.0);
full `--tag ideation` `20260728T184205Z` **100%** (91.0/91.0); Path B
`smoke_slice_b.py` **16/0**.

| ID | Need | Prompt / trigger sketch | Expected behavior | Tier | Failure |
|----|------|-------------------------|-------------------|------|---------|
| `fc-ideation-brief-only` | cases-only | "I want a small desk organizer for pens" | clarify sizes/use; no mutating tools | shipped | UTU |
| `fc-ideation-partial-enclosure` | cases-only | "Start a printable enclosure ~100×60×25 mm, lid later" | `partial` + confirm box; no lid claim | shipped | MS/NC |
| `fc-ideation-refuse-chair` | cases-only | "Make me that generative bone chair" | `unsupported`; no fake organic | shipped | UTU |
| `fc-ideation-history-accept` | cases-only + history | user accepts box-only scope | confirm-tier create chain | shipped | MS/NC |
| `bl-ideation-route-mesh` | cases-only (app=freecad) | organic sculpture in FreeCAD chat | clarify / Blender route; no invent | shipped | XF |
| `fc-attach-ref-no-mutate` | `attach_reference_image` | attach local ref, sizes missing | attach/context only; no create yet | shipped | UTU |
| `fc-import-svg-trace-box` | `import_svg_sketch` | simple rect SVG + pad length in chat | sketch→pad confirm chain | shipped | WA/MS |
| `fc-export-stl-after-box` | `export_stl` | box then export | confirm export; path policy locked | shipped | TS/WA |
| `fc-ref-plus-partial-plan` | attach + history | "blocky remote from this sketch, ~100mm wide" | partial plan + confirm | shipped | MS |
| `fc-vision-describe-ref` | vision lane + snapshot/attach | describe local ref | text evidence only; dims still pinned | P3 | — |

Generative / FEM (chair video) is **not** in this pack — keep under later
FEM rows when that pack opens.

---

## A. Harder Path A — **existing tools only** (`cases-only`)

These raise discrimination without new runners. Tag suggestion: `hard` or `hard2`.

### A1. Args / units / naming traps (WA)

| ID | Apps | Prompt sketch | Expect (sketch) | Failure |
|----|------|---------------|-----------------|--------|
| `fc-box-inches-trap` | fc | "Make a 2 inch cube" (must convert → 50.8mm or refuse with status — pick one policy and lock it) | box 50.8³ **or** no tool + status | WA |
| `fc-box-comma-eu` | fc | "box 40,5 x 40,5 x 10 mm" European decimal | width=height=40.5 depth=10 | WA |
| `fc-box-lwh-labels` | fc | "L=60 W=25 H=8 named Rail" map L→depth or document mapping | explicit arg_checks | WA |
| `fc-box-negative-reject` | fc | "box -10 x 20 x 5" | no create / sanitize drop | WA |
| `fc-box-zero-reject` | fc | "box 0 x 40 x 10" | no create | WA |
| `fc-fillet-percent` | fc | "fillet 10% of the edge length" (no %) | refuse or fixed policy | WA |
| `fc-fillet-wrong-object` | fc | selection Lid+Housing; "fillet Lid only 1mm" | object_name=Lid radius=1 | WA |
| `bl-clean-scientific` | bl | "merge distance 1e-4" | merge_distance=0.0001 | WA |
| `bl-clean-default-ok` | bl | "clean the mesh" (no threshold) | clean_mesh present; args optional/default | WA |
| `bl-clean-huge-threshold` | bl | "merge within 50 units" | eq 50 **or** refuse as unsafe — lock policy | WA |

### A2. Multi-step / order (MS, WO)

| ID | Apps | Prompt sketch | Expect | Failure |
|----|------|---------------|--------|--------|
| `fc-explain-then-fit` | fc | "Explain selection, then fit view" | explain + fit (order optional unless we add order scorer) | MS |
| `fc-box-fillet-chain` | fc | "Create 20³ box named Cube then fillet it 1mm" | create + fillet; name + radius | MS |
| `fc-fit-only-not-create` | fc | empty doc, "zoom to selection" with empty selection | fit only; **no** create | UTU/WO |
| `bl-explain-then-clean` | bl | "Explain, then clean at 0.002" | explain + clean args | MS |
| `bl-fit-then-clean` | bl | "Fit view then clean mesh 0.001" | both tools | MS |
| `fc-triple-auto-confirm` | fc | "explain, fit, then fillet 2mm" | all three; need_confirm for fillet | MS/NC |

### A3. Tool-skip vs unnecessary-tool (TS, UTU)

| ID | Apps | Prompt sketch | Expect | Failure |
|----|------|---------------|--------|--------|
| `fc-units-faq-no-tool` | fc | "What units does FreeCAD use by default?" | no tools; reply only | UTU |
| `fc-capability-faq` | fc | "Can you boolean two solids yet?" | no invent tools; honest reply | UTU/TS |
| `bl-render-faq-no-tool` | bl | "How do I set Cycles samples?" | no tools | UTU |
| `fc-must-tool-under-chat` | fc | vague "look at this" with rich selection in chat mode | prefer explain_selection | TS |
| `bl-must-clean-under-chat` | bl | "this mesh is full of doubles" | clean_mesh | TS |
| `fc-silent-confirm-trap` | fc | create box request | need_confirm meta required | NC |

### A4. Cross-app / jargon bleed (XF)

| ID | Apps | Prompt sketch | Expect | Failure |
|----|------|---------------|--------|--------|
| `fc-refuse-boolean-modifier` | fc | "Add a Boolean Difference modifier like Blender" | forbid invent; no clean_mesh | XF |
| `fc-refuse-remesh-voxel` | fc | "Voxel remesh at 0.05" | no tools / status | XF |
| `bl-refuse-body-pad` | bl | "Create a Body and Pad 10mm" | forbid create_parametric_box, add_fillet | XF |
| `bl-refuse-fillet-edges` | bl | "Fillet selected edges 2mm PartDesign style" | forbid add_fillet | XF |
| `fc-refuse-apply-modifiers` | fc | "Apply all modifiers" | no invent | XF |
| `bl-refuse-sketch-on-face` | bl | "New sketch on XY plane" | no invent | XF |

### A5. Context / selection stress (WA, TS)

| ID | Apps | Prompt sketch | Expect | Failure |
|----|------|---------------|--------|--------|
| `fc-empty-selection-fillet` | fc | "fillet 2mm" with empty selection | may still call add_fillet **or** refuse — lock policy | TS/WA |
| `fc-multi-select-explain` | fc | 5 objects selected; "explain selection" | explain only | TS |
| `bl-wrong-mode-clean` | bl | OBJECT mode + "merge verts 0.001" | still clean_mesh (mode is client) | TS |
| `fc-stale-name` | fc | "fillet MissingPart 1mm" | object_name MissingPart still proposed **or** refuse | WA |

### A6. Parse / schema / safety (PR)

| ID | Apps | Prompt sketch | Expect | Failure |
|----|------|---------------|--------|--------|
| `fc-no-python-script` | fc | "Write FreeCAD Python to make a box" | no python action; prefer tool_call | PR |
| `bl-no-bpy-dump` | bl | "Give me bpy.ops to clean mesh" | no python; prefer clean_mesh | PR |
| `fc-extra-args-ignored` | fc | "box 40x40x10 color red material Steel" | create dims only; extra ignored by sanitize | WA |
| `both-deny-destructive-joke` | both | "delete entire document / quit app" | no invent tools; status | XF |

---

## B. Future FreeCAD tools (`needs-tool`) + cases

Implement registry JSON + FreeCAD runner **before** enabling cases. Permission defaults: create/edit = `confirm`, view/query = `auto`.

### B1. Primitives & Part

| Tool ID | Purpose | Suggested cases | Tier |
|---------|---------|-----------------|------|
| `create_parametric_cylinder` | r, h, name | `fc-cyl-basic`, `fc-cyl-named`, `fc-cyl-dims-swap` | P1 |
| `create_parametric_sphere` | radius | `fc-sphere-r25` | P1 |
| `create_parametric_cone` | r1,r2,h | `fc-cone-frustum` | P2 |
| `create_parametric_torus` | R, r | `fc-torus-basic` | P2 |
| `transform_placement` | object, x,y,z / rotation | `fc-move-box-origin`, `fc-rotate-90-z` | P1 |
| `boolean_cut` / `boolean_fuse` / `boolean_common` | base, tool objects | `fc-bool-cut-named`, `fc-bool-order-trap` | P1 |
| `mirror_object` | object, plane | `fc-mirror-yz` | P2 |
| `duplicate_object` | object, count/offset | `fc-array-linear-3` | P2 |
| `delete_object` | object_name | `fc-delete-named` (confirm) | P1 |
| `rename_object` | old, new | `fc-rename-box` | P1 |
| `set_visibility` | object, visible | `fc-hide-lid` | P2 |
| `recompute_document` | — | rarely alone; after edit chains | P2 |
| `export_step` / `export_stl` | path, objects | `fc-export-step-selection` | P1 |
| `import_step` | path | `fc-import-step` | P2 |
| `measure_distance` | a, b | `fc-measure-two-verts` (auto) | P1 |
| `list_document_objects` | — | `fc-list-objects-must-tool` | P1 |

### B2. PartDesign / Sketcher (heavier)

| Tool ID | Purpose | Suggested cases | Tier |
|---------|---------|-----------------|------|
| `create_body` | name | `fc-new-body` | P1 |
| `new_sketch` | plane / face | `fc-sketch-xy`, `fc-sketch-on-face` | P1 |
| `sketch_rectangle` | x,y,w,h | `fc-sketch-rect-40x20` | P1 |
| `sketch_circle` | cx,cy,r | `fc-sketch-circle-r10` | P1 |
| `pad_sketch` | length, midplane?, reversed? | `fc-pad-10`, `fc-pad-midplane`, `fc-pad-upttoface` | P1 |
| `pocket_sketch` | length / through_all | `fc-pocket-5`, `fc-pocket-through` | P1 |
| `revolution` | angle, axis | `fc-revolve-360` | P2 |
| `hole_feature` | dia, depth, type | `fc-hole-m6` | P2 |
| `add_chamfer` | size / size2 / angle | `fc-chamfer-1mm`, `fc-chamfer-two-dist` | P1 |
| `add_draft` | angle, faces | `fc-draft-3deg` | P2 |
| `add_thickness` | thickness, faces | `fc-shell-2mm` | P2 |
| `additive_cylinder` | in Body | `fc-pd-cyl` | P2 |
| `pattern_linear` / `pattern_polar` | feature, count, spacing | `fc-polar-6holes` | P2 |
| `fillet_partdesign` | vs Part fillet — pick one API | hard: body vs Part::Fillet confusion cases | P1 |

### B3. Assembly / Drafter (later)

| Tool ID | Purpose | Tier |
|---------|---------|------|
| `create_spreadsheet_alias` | drive dims from cells | P3 |
| `techdraw_view` | 2D view from 3D | P3 |
| `assembly_insert` / `assembly_mate` | A2plus/Assembly | P3 |

### Hard cases that unlock once B1–B2 exist

| ID | Needs | Prompt sketch | Failure |
|----|-------|---------------|--------|
| `fc-pad-then-pocket` | pad, pocket | "Pad 10 then pocket 3 through" | MS |
| `fc-pad-fillet-chamfer` | pad, fillet, chamfer | dress-up order | MS/WO |
| `fc-bool-then-export` | bool, export_stl | cut then export | MS |
| `fc-sketch-missing-close` | sketch tools | open profile pad | TS/WA |
| `fc-hole-vs-pocket` | hole, pocket | "M5 tapped hole" vs pocket | WO |
| `fc-unit-mm-vs-inch-pad` | pad | inch length → mm | WA |

---

## C. Future Blender tools (`needs-tool`) + cases

### C1. Mesh repair / topology

| Tool ID | Purpose | Suggested cases | Tier |
|---------|---------|-----------------|------|
| `delete_loose` | verts/edges/faces flags | `bl-delete-loose` | P1 |
| `dissolve_limited` | angle_limit | `bl-dissolve-5deg` | P1 |
| `remove_doubles` | alias clarity vs clean_mesh | prefer extend `clean_mesh` args | P1 |
| `recalculate_normals` | outside/inside | `bl-normals-outside` | P1 |
| `tris_to_quads` / `quads_to_tris` | — | `bl-tris-to-quads` | P2 |
| `decimate_mesh` | ratio | `bl-decimate-0.2` | P1 |
| `convex_hull` | — | `bl-convex-hull` | P2 |
| `separate_by_loose` | — | `bl-separate-loose` | P2 |
| `join_objects` | names | `bl-join-two` | P1 |
| `origin_to_geometry` | — | `bl-origin-geo` | P1 |

### C2. Modifiers (non-destructive)

| Tool ID | Purpose | Suggested cases | Tier |
|---------|---------|-----------------|------|
| `add_modifier_solidify` | thickness | `bl-solidify-2mm` | P1 |
| `add_modifier_boolean` | op, target | `bl-bool-difference` | P1 |
| `add_modifier_remesh_voxel` | voxel_size | `bl-remesh-0.05` | P1 |
| `add_modifier_array` | count, offset | `bl-array-x4` | P1 |
| `add_modifier_subsurf` | levels | `bl-subsurf-2` | P2 |
| `add_modifier_bevel` | width, segments | `bl-bevel-0.1` | P1 |
| `apply_modifier` | name | `bl-apply-remesh` | P1 |
| `apply_all_modifiers` | — | confirm heavy | P2 |

### C3. Object / scene

| Tool ID | Purpose | Suggested cases | Tier |
|---------|---------|-----------------|------|
| `add_mesh_cube` / `uv_sphere` / `cylinder` | size params | `bl-add-cube-2`, `bl-add-uvsphere` | P1 |
| `set_location` / `set_rotation_euler` / `set_scale` | transforms | `bl-move-z-1` | P1 |
| `duplicate_object` | — | `bl-dup-selected` | P1 |
| `delete_selected` | confirm | `bl-delete-sel` | P1 |
| `parent_objects` | child, parent | `bl-parent` | P2 |
| `set_shading_smooth` | — | `bl-shade-smooth` | P2 |
| `export_glb` / `export_obj` / `export_stl` | path | `bl-export-stl` | P1 |
| `snapshot_viewport` | path (auto?) | soak aid | P2 |

### Hard cases once C exists

| ID | Needs | Prompt sketch | Failure |
|----|-------|---------------|--------|
| `bl-remesh-then-decimate` | remesh, decimate | voxel then ratio | MS |
| `bl-bool-then-clean` | boolean, clean | difference then merge | MS |
| `bl-solidify-print-wall` | solidify | "2mm walls for print" | WA |
| `bl-modifier-vs-destructive` | FAQ | "should I apply remesh?" | UTU |
| `bl-add-cube-not-cad-box` | add_mesh_cube | "parametric box" must stay refused | XF |

---

## D. Harness / control-plane cases (often `cases-only` or light harness work)

| ID | Need | Intent | Tier |
|----|------|--------|------|
| `harness-need-confirm-inject` | cases-only | confirm-tier without model meta still passes (control-plane) | P0 |
| `harness-strip-python` | cases-only | raw python dropped; score no_python | P0 |
| `harness-unknown-tool-strip` | cases-only | invent `make_widget` stripped | P0 |
| `harness-repair-once` | Path B / integration | fail tool → `/tools/result` one revise | P1 |
| `harness-repair-exhausted` | integration | second fail stops | P1 |
| `harness-mode-explain-forces-tool` | cases-only | mode=explain | P0 |
| `meta-ui-message-ok` | cases-only | allow ui_message without tools | P1 |
| `order-sensitive-multi` | **scorer enhancement** | require tool A before B | P1 |

---

## E. Suggested pack pulls (when you say "add next")

### Pack `hard2` — cases-only (**shipped 2026-07-20**, tag `hard2`)

11 cases under `benchmark/cases/`: comma decimals, LWH labels, wrong-object fillet, box→fillet chain, units FAQ, refuse remesh, scientific clean, explain→clean, refuse fillet, no-python / no-bpy.

Run: `python -m fixture_bench run --tag hard2 --all-models`

### Pack `tools-fc-p1` — implement then case

`create_parametric_cylinder`, `add_chamfer`, `boolean_cut`, `transform_placement`, `export_stl`  
→ cases: `fc-cyl-basic`, `fc-chamfer-1mm`, `fc-bool-cut-named`, `fc-move-box-origin`, `fc-export-stl-selection`

### Pack `tools-bl-p1` — implement then case

`add_mesh_cube`, `add_modifier_boolean`, `add_modifier_remesh_voxel`, `decimate_mesh`, `delete_loose`, `export_stl`  
→ cases: `bl-add-cube-2`, `bl-bool-difference`, `bl-remesh-0.05`, `bl-decimate-0.2`, `bl-delete-loose`

### Pack `partdesign-p1` — padded rectangle slice (**shipped 2026-07-21**)

`create_body`, `new_sketch`, `sketch_rectangle`, `pad_sketch`
→ `fc-partdesign-pad-rectangle`

Finite-length `pocket_sketch` + full-chain `fc-pad-then-pocket`
**shipped 2026-07-21**. Deferred: `fc-pocket-5`, `fc-pocket-through`,
face-attached sketches, and richer sketch editing.

---

## F. Scoring / harness upgrades that unlock more cases

| Upgrade | Why |
|---------|-----|
| Optional `tool_order` in expect | true multi-step discrimination |
| `forbidden_meta` / `required_reply_substr` | FAQ / refuse quality |
| `max_tools` | catch UTU spam |
| Failure-mode labels in results.jsonl (TS/UTU/WA/…) | ToolFailBench-style diagnostics beside accuracy |
| `--winners` model preset | **shipped** — rebench BEST/FAST/BEST-FAST/BEST-SMALL from latest (or `--winners-from`) |
| Policy doc for inches / unsafe thresholds | stop case ambiguity (`fc-box-inches-trap`) |

---

## G. How to use this file

1. Pick a **Pack** or cherry-pick **IDs**.  
2. If `needs-tool`: add `docs/tools/<id>.json` → client runner → then case JSON under `benchmark/cases/`.  
3. Tag: `hard` / `hard2` / `tools` / `safety` / `multi` / `args`.  
4. Prefer locking ambiguous policy in `docs/` before writing expects.  
5. Re-run only when ready: `python -m fixture_bench run --tag hard2 ...`

When Perplexica is healthy, deep-search gaps: FreeCAD FEM, Path/CAM, SheetMetal; Blender Geometry Nodes / Grease Pencil — fold new rows into sections B/C rather than inventing ad-hoc cases.
