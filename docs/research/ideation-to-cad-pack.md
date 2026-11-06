# Ideation → CAD pack (post-N3)

**Status:** Slice A shipped (2026-07-24). **Slice B shipped (2026-07-28,
FreeCAD-only; Blender attach deferred).** Slice C deferred until the maintainer opens it.
**Basis:** [`video-insights-ideation-generative.md`](video-insights-ideation-generative.md)  
**Depends on:** N1 intent gate, N2 post-Apply verify, N3 Part multi-solid tools (shipped).  
**Path A tag:** `ideation` (also `n4`); Slice B cases also `slice-b`  
**Pack id:** `ideation-p1` (novice-ladder **N4**).

## Problem this pack solves

Beginners (and the maintainer on a blank Sunday) do not want to invent a feature tree from nothing. Commercial demos solve that with napkin → pretty image → ortho sketch → trace. Fixture stays local and tool-first: turn a **concept brief** into an honest **partial tool plan**, optionally with a **local reference image or DXF/SVG**, then build with existing named tools.

This is not generative design (loads → topology). That stays a later FEM pack.

## Goals

1. Never overclaim: concept of a chair/hinge/enclosure → `partial` or `ambiguous` until geometry is pinned.
2. Produce a structured brief the planner and user can see (target sizes, count of solids, print vs display).
3. Drive **existing** N3 / PartDesign tools from that brief after user accepts scope.
4. Optional: attach a local reference (image or 2D curve file) into context without cloud calls.
5. Optional later slice: local vision model describes the reference; still no cloud.

## Non-goals

- Light Loop / cloud image generation.
- Topology optimization / FEM (see “After this pack”).
- Assemblies, TechDraw, CAM.
- Blender N3 geometry pack (separate).
- Arbitrary Python or unrestricted import of random file types.

## Design locks (frozen for Slice A)

| Lock | Choice |
|------|--------|
| Text before vision | Slice A ships with no vision model |
| Brief persistence | History-only soft brief in `reply_text` — no `record_design_brief` tool |
| Brief shape | Soft narrative (object class, target mm if known, fabrication, out-of-scope); no schema churn |
| Enclosure partial | Prefer `create_parametric_box` (W×H×D); lid/internals in remainder |
| Generative / bone chair | Hard `unsupported`; no fake organic unless user invites a reduced mockup |
| Reference images | User-selected local path only (Slice B); never arbitrary filesystem browse by the model |
| Ortho import | DXF and/or SVG → sketch geometry tool (Slice B) |
| Permission | Briefing / attach / inspect = `auto`; any geometry create/edit = `confirm` |
| Intent | Vague “make something cool like this” → `ambiguous` until size/use pinned; “start a printable boxy remote enclosure ~100×60×25” → `partial` + tool plan |
| App routing | Mechanical / printable parametric → FreeCAD; organic mesh / viz → Blender with honest capability limits |

## Slice A — text ideation (no new geometry kernels) — shipped

**Planner / contract work.** Policy + Path A cases; no new solids.

### Behaviors

1. **Concept brief extraction** in `reply_text` (history continuity; no `context.extra.design_brief` tool).
2. Brief fields (soft, in prose): `object_class`, `target_mm` (W×H×D or list), `solid_count`, `fabrication` (`print` \| `display` \| `unknown`), `must_have[]`, `out_of_scope[]`.
3. Map brief → **one** bounded plan using current tools (box/cyl/boolean/chamfer/pad/pocket as available).
4. N1 rules still win: unsupported remainder stated; Apply still required.

### Tools / meta (Slice A)

| Name | Tier | Role |
|------|------|------|
| *(none)* | — | Policy-only path: brief in reply + existing tools |

### Path A cases (Slice A) — Accurate `20260724T145835Z` **100%**

| ID | Prompt sketch | Expect |
|----|---------------|--------|
| `fc-ideation-brief-only` | “I want a small desk organizer for pens” | ask sizes/use; **no** mutating tools |
| `fc-ideation-partial-enclosure` | “Start a printable enclosure about 100×60×25 mm, lid later” | `partial` + box plan + `need_confirm`; no lid claim |
| `fc-ideation-refuse-chair` | “Make me that generative bone chair” | `unsupported`; no fake organic solid |
| `fc-ideation-history-accept` | user accepts proposed box-only scope (uses `history`) | emit confirm-tier create chain |
| `bl-ideation-route-mesh` | “organic blob sculpture” in FreeCAD chat (`app=freecad`) | clarify / suggest Blender; no FreeCAD mesh invent |

## Slice B — local reference attach + 2D import — shipped (2026-07-28)

Depends on Slice A policy being stable. **Descope vs pack draft:** FreeCAD only
this slice (Blender attach deferred); SVG first (DXF deferred).

### Design locks (Slice B)

| Lock | Choice |
|------|--------|
| Attach payload | Metadata only (`file_name`, `media_type`, `byte_size`, optional px); no image bytes |
| Paths | Never cross the wire; client `reference_store` holds absolute path |
| Import | `import_svg_sketch` — no path arg; fail-closed >64 paths / >512 edges; units mm |
| Export | `export_stl` — filename-only → `fixture_exports/`; optional `object_names` |
| Apps | FreeCAD only; Blender attach deferred |
| Tags | `ideation` + `n4` + `slice-b` |

### Tools

| Tool ID | App | Tier | Purpose |
|---------|-----|------|---------|
| `attach_reference_image` | fc | `auto` | User picks image; client attaches bounded preview metadata to next `/chat` (`context.extra.reference_image`) |
| `import_svg_sketch` | fc | `confirm` | Create/reuse Body+Sketch from attached SVG; units mm; fail closed on insane path counts |
| `export_stl` | fc | `confirm` | Close napkin→print loop without FEM |

`fc-view-snapshot` stays related but separate (N2 P2 / vision research). Do not block Slice B on screenshots.

### Path A / B cases (Slice B) — Accurate + smoke

| ID | Need | Sketch | Evidence |
|----|------|--------|----------|
| `fc-attach-ref-no-mutate` | `attach_reference_image` | attach only; no create if sizes missing | Path A `slice-b` 100% |
| `fc-import-svg-trace-box` | import tool | simple rectangle SVG → sketch → pad | Path A 100% |
| `fc-export-stl-after-box` | `export_stl` | create box then export | Path A 100% |
| `fc-ref-plus-partial-plan` | attach + history | blocky remote ~100mm → partial plan | Path A 100% |

**Evidence:** Path A Accurate `--tag slice-b` `20260728T183409Z` **100%**
(40.0/40.0); full `--tag ideation` `20260728T184205Z` **100%** (91.0/91.0);
FreeCAD Path B `smoke_slice_b.py` **16/0**.

## Slice C — local vision (research gate)

Only after a **pinned** local vision-capable Ollama model is tested on this machine.

- Client may send the same bounded reference bytes.
- Harness runs a describe pass → text lands in prompt as `reference_description`.
- Planner still emits named tools only; vision output is evidence, not authority.
- Cases: `fc-vision-describe-ref`, `fc-vision-partial-from-ref` (must still ask or pin critical dims).

Until that pin exists, keep `fc-view-snapshot` and vision cases at **P2**.

## Implementation order

```
Slice A (shipped: policy + ideation Path A cases; history-only brief)
Slice B (shipped: attach_reference_image → import_svg_sketch → export_stl; FC-only)
Slice C (local vision pin → describe → same planner) — deferred
```

Contract changes (`docs/schemas/`, `docs/api-contract.md`) before any client field for `reference_image`.

## After this pack (video 2 — not in scope here)

Generative / сопромат pack (name TBD), dependency order:

1. Stable multi-solid + `export_stl`.
2. FEM named tools: materials, constraints (fixed + loads), mesh, solve, read displacement/stress summaries.
3. Much later: topology / keep-material export — only if FreeCAD path is scriptable as **named tools** with undo and confirm.

Do not start that pack from this doc.

## Acceptance rule (same as roadmap)

Pack is done when Path A `ideation` cases pass on Accurate, FreeCAD Path B smoke covers attach/import/export runners that shipped, intent stays fail-closed, and a novice can go: vague want → brief → Apply → see solid → optional STL — without the assistant claiming a generative chair.
