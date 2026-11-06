# KiCad consumer — design spec (proposal, 2026-10-17)

*A third consumer in the Fixture pattern: thin client + harness planner +
named tools + client-local confirm/undo. Same wire contract as the FreeCAD
workbench and Blender addon (`docs/api-contract.md`), same safety rules.
Status: **proposal** — no code yet. Implementation gate: tool JSONs under
`docs/tools/` land first (contract-first), then the client runner, then a
Path A case pack and a Path B smoke.*

## Why

The pilot board needs a PCB. Today Fixture's vocabulary is CAD modeling only —
it cannot touch a board. This spec defines the seam that changes that, and
doubles as the **first cross-domain MoS test**: does the same architecture
(planner → named tools → confirm → deterministic check) hold in EDA?

## Shape (mirrors the existing consumers)

- **Client:** a KiCad **action plugin** (Python, inside KiCad) hosting a small
  dock + a runner module. It loads tool definitions from `docs/tools/`,
  sends `POST /chat`, renders the plan card, and executes only after Apply.
- **Context sent with each request** (`context.extra.board`): board name and
  path, layer count, net class summary, footprint/track/via counts, current
  selection (refs + positions), DRC status, ratsnest count, KiCad version.
- **Execution:** each runner calls `pcbnew` on the open board. All mutations
  are `confirm` tier.
- **Undo (the honest bit):** `pcbnew` exposes no stable per-action undo from
  Python. v0 = **board snapshot** (copy the `.kicad_pcb` text before Apply;
  Cancel/Undo restores it by reopening) + confirm tier + save-before-apply.
  Documented as a limitation, not hidden.

## Named tools (v0 draft — JSON defs land with implementation)

| tool | tier | args (sketch) |
|---|---|---|
| `inspect_board` | auto | — (returns counts, DRC, nets) |
| `place_footprint` | confirm | `ref`, `lib_id`, `x`, `y`, `rot`, `side` |
| `move_footprint` | confirm | `ref`, `x`, `y`, `rot` |
| `add_track` | confirm | `x1,y1,x2,y2,layer,width` |
| `add_via` | confirm | `x,y,size,drill,net` |
| `draw_outline` | confirm | `points[[x,y],…]`, `layer` (Edge.Cuts only) |
| `run_drc` | auto | — |
| `export_gerbers` | confirm | `out_dir` |
| `save_board` | confirm | — |

No schematic editing, no netlist authoring, no autorouting in v0 (use
`freerouting`/KiCad's router). `deny` stays reserved.

## Eval plan (same two paths)

- **Path A (planner):** ~40 cases mined from real PCB tasks — "place U1 at
  (x,y)", "route a 0.25 mm track on F.Cu", "refuse: change the stackup".
  Scored on tool choice + args + confirm tier + refusal policy.
- **Path B (execution):** headless `pcbnew` (or `kicad-cli`) applies the plan
  to a fixture board; assert footprint positions/nets and a **clean DRC**.
  This is the board analog of the FreeCAD Path B smokes.

## MoS scope — the PCB specialist

Same recipe as Taiga (`docs/research/system1-executors-and-planner-pairing.md`):

| element | PCB placement specialist |
|---|---|
| state | board summary, outline, netlist constraints, selection, DRC, last N ops |
| actions | the currently-valid subset of the named tools (place/move/rotate/via/track) |
| teacher | scripted `pcbnew` flows: a state-based expert that labels the acceptable next placement/route from the rules (clearance, keepout, fan-out) |
| model | 1–5 M transformer over typed tokens + candidate actions (Taiga architecture, MIT) |
| eval | task success (placement legal + DRC clean) + step parity vs the teacher |

**Where it fits:** placement and local routing are enumerable-valid-action
problems — exactly Taiga-shaped. **Where it does not:** schematic design,
stackup, EMC strategy → LLM planner. If a 1.2 M policy can place a board's
components at ms latency with a teacher, PCB joins the Understory — that is the
MoS test.

## Planner generalization (the 1–10 M / 10–100 M question)

Layers, not apps. Taiga is an **executor**; the planner is (today) an LLM.
Evidence from the planner-floor ladder (60-case CAD suite):

| size | result |
|---|---|
| 0.27 B | 0/60 full pass |
| 1.2 B | 11/60 |
| **4 B** | **55/60 (97.2 %)** |
| 12 B | 57/60 |
| cloud | 59/60 |

Reads:

1. **Separate planner per app — no.** One planner, N executors; the apps differ
   in the executor vocabulary, not the planning faculty.
2. **A 10 M off-the-shelf planner — not credible.** 10 M is far below the
   measured floor; nothing at that size plans.
3. **A 10 M planner is credible as a trained artifact** — distilled on a
   **shared plan grammar** (ordered steps over a per-app tool vocabulary) with
   the deterministic scorers as the label filter. That is the cheap
   experiment: train one small model on CAD + PCB + Blender plan corpora and
   measure per-domain transfer. Expect it to hold where the schemas align and
   fail on novel tool semantics.
4. **10–100 M across domains:** plausible *only* with that shared grammar +
   multi-domain labels; not with pretrained general models. Until measured,
   the pragmatic stack is: general planner (LLM) + tiny Switchboard router +
   domain executors (Taiga-style).

## Open questions

- KiCad version/API surface (`pcbnew` vs `kicad-cli`); dock vs standalone app.
- Undo: is a snapshot/restore acceptable, or gate mutations behind "save
  first"?
- DRC as a hard gate before `export_gerbers` (recommended yes).
- Which lane runs first: placement (enumeration-friendly) or routing?
- Whether the split-keyboard PCB is the pilot board (it should be).

## Non-goals

Schematic capture/editing, netlist authoring, autorouting, 3D board modeling,
EMC/stackup advice. Those stay human (or a later planner) work.
