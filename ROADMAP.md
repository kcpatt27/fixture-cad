# Fixture — ROADMAP

Long-horizon plan, EASY → MEDIUM → HARD → VERY HARD → IMPOSSIBLE+ → VISION.
Complexity estimates are honest, not padded. Status markers: **[DONE]**,
**[NEXT]**, **[ ]**.

Classification: **MVP** (required for the personal daily-driver definition of
done), **P** (post-MVP), **HA** (high-assurance), **R** (research).

Datasets: **CAD-1K and BlenderLore are eval-only; no data is redistributed.**

The shipped surface is in `README.md`; design truth is in `ARCHITECTURE.md`;
decisions are in `DECISIONS.md`. A status without evidence is a bug - fix the
status, not the evidence column.

---

## Stage 0 — EASY (shipped foundation)

Conventional engineering; the code that already exists.

| Item | Purpose | Deps | Complexity | Class | Status |
| --- | --- | --- | --- | --- | --- |
| Phase A contracts | schemas + tool defs + api-contract frozen before code | — | S | MVP | **[DONE]** (2026-07) |
| Harness `:8766` | `/health` `/tools` `/chat` `/tools/result`, sanitize, repair | contracts | M | MVP | **[DONE]** (`aebf43c`) |
| FreeCAD workbench + Blender addon | same contract, dock/N-panel, runners, undo | harness | M | MVP | **[DONE]** (`aebf43c`) |
| Runtime model lanes | accurate / fast / auto resolved by mode | harness | S | MVP | **[DONE]** (`dcb1d80`) |
| PartDesign pad + finite pocket | editable Body → Sketch → Pad → Pocket | lanes | M | MVP | **[DONE]** (`4e8f730`, `4f69071`; Path A 100% `20260721T141741Z`, `20260721T160957Z`) |
| N1 capability-aware conversation | supported / ambiguous / partial / unsupported, fail-closed | contracts | M | MVP | **[DONE]** (`a9aa670`; Path A Accurate 96.5% `20260721T233824Z`) |
| N2 guided post-Apply verification | deterministic inspect + grounded explain | N1 | M | MVP | **[DONE]** (`a9aa670`; Path B 13/0) |
| N3 modeling pack | cylinder, placement, boolean cut/fuse, chamfer | N2 | M | MVP | **[DONE]** (`2faa54a`; Path A 100% `20260724T143442Z`; Path B 24/0) |
| Ideation Slice A | concept briefs, honest refusal/partial policy | N1 | M | MVP | **[DONE]** (`55f15f4`; Path A 100% `20260724T145835Z`) |
| Ideation Slice B | attach metadata, SVG import, `export_stl` | Slice A | M | MVP | **[DONE]** (`918466e`; Path A 100% `20260728T184205Z`, `20260728T183409Z`; Path B 16/0; manual GUI soak open) |
| Fast verification gate | fixtures + pytest + all Path B in one command | clients | S | MVP | **[DONE]** (gate PASS `20261106T125738Z` / `20261106T132007Z`: pytest 140, FreeCAD 92/0, Blender 29/0) |
| Planner regression fix | `align_tool_args` tuple contract dropped every tool call | harness | S | MVP | **[DONE]** (2026-10-04, working tree; harness tests 47+18fail → 77 pass) |
| OpenRouter lane | opt-in cloud refs, JSON-mode retry, health reporting | ADR-010 | M | P | **[DONE]** (2026-10-04; cloud H2H in `benchmark/headtohead-vs-freecad-ai.md`; rerank A/B pending) |
| Fallback chain + tool rerank | provider resilience; top-N keyword catalog | ADR-011 | S | P | **[DONE]** (2026-10-04, working tree; rerank A/B pending) |
| Competitor + data research | MCP/freecad-ai audit; CAD-1K + BlenderLore inventory | - | S | P | **[DONE]** (2026-10-04; `docs/research/competitive-landscape-2026-10.md`, `docs/research/cad-blender-data-strategy-2026-10.md`) |
| Foundation docs | this six-doc set at root; `docs/` stays contract layer | — | S | P | **[DONE]** (2026-10-04, ADR-012) |

## Stage 1 — MEDIUM (current frontier)

| Item | Purpose | Deps | Complexity | Class | Status |
| --- | --- | --- | --- | --- | --- |
| Playable FreeCAD mounting-plate recipe | human plan card → Apply/Cancel → one Undo → refinement loop | N3, Slice B | M | MVP | **[NEXT]** |
| Slice B GUI soak closure | restart FreeCAD, attach SVG → import+pad → Apply → verify → `export_stl` | FreeCAD GUI | S | MVP | **[NEXT]** |
| Raster-reference fail-closed guard | JPEG/PNG can never emit `import_svg_sketch` | Slice B | S | MVP | **[DONE]** |
| OpenRouter comparison run | does cloud quality change, and at what cost per point? | ADR-010 + API key | S | MVP | **[DONE]** (2026-10-06 H2H) |
| Rerank A/B on the suite | decide whether `FIXTURE_TOOL_RERANK` becomes a default | ADR-011 | S | P | **[ ]** |
| Mined Path A cases from CAD-1K | 200-500 held-out cases incl. refusal coverage | data strategy | M | MVP | **[ ]** (eval-only; no redistribution) |
| `clean_mesh` calibration | thresholds from real BlenderLore `.blend` meshes | BlenderLore | S | P | **[ ]** |
| Headless isolation for heavy export | GUI survives native OCCT crashes (freecad-mcp lesson) | client runners | M | HA | **[ ]** |

## Stage 2 — HARD (breadth + robustness)

| Item | Purpose | Deps | Complexity | Class | Status |
| --- | --- | --- | --- | --- | --- |
| GUI dispatch health/timeouts | stuck-operation detection with honest errors | client runners | M | HA | **[ ]** |
| Through-all Pocket, face-attached sketches, patterns | richer native PartDesign | ADR-008 | M | MVP | **[ ]** |
| DXF import | 2D exchange beyond SVG | Slice B | M | P | **[ ]** |
| Parts library named tools | discovery + safe insertion | breadth | M | P | **[ ]** |
| Blender recipe packs | mined beginner recipes (brackets/enclosures/hinges/adapters) | CAD-1K mining | M | P | **[ ]** |
| BlenderLore recipe mining | `tutorial.md` → Blender recipe cases | BlenderLore | M | P | **[ ]** |
| Blender N3 tool growth | parity with FreeCAD modeling pack | Blender addon | M | P | **[ ]** |
| Vision Slice C | pinned local VLM for reference images and verify | ADR-009 | L | P | **[ ]** (gate: model pinned + eval) |
| Few-shot retrieval experiment | retrieved plans into the prompt | mined cases | M | R | **[ ]** (only if the eval shows a ceiling) |

## Stage 3 — VERY HARD

| Item | Purpose | Deps | Complexity | Class | Status |
| --- | --- | --- | --- | --- | --- |
| FEM named tools | CalculiX reference from freecad-mcp, converted to named tools | breadth | L | P | **[ ]** |
| Assemblies / joints | multi-body work after reliable modeling | through-all Pocket | L | P | **[ ]** |
| MCP server exposure | let MCP hosts drive the safe named-tool pipeline | harness | M | P | **[ ]** |
| Cloud→local distillation | OpenRouter as teacher, 7B student, held-out eval | mined cases + GPU | L | R | **[ ]** (gate: proven ceiling) |
| Blender asset search/insert | semantic library over BlenderLore-style assets | BlenderLore | L | P | **[ ]** |

## Stage 4 — IMPOSSIBLE+ (what software cannot guarantee)

- **"Any sentence → production CAD"** — impossible in general. Engineering
  approximation: bounded named-tool recipes plus honest `partial` /
  `unsupported` statuses. Residual risk: a request that *looks* covered but
  isn't gets a clarifying question, not geometry.
- **"A local 4B model matches frontier cloud on open-ended design"** — not
  guaranteed. Approximation: measured lanes + benchmark; residual risk: unseen
  phrasings regress.
- **"Native CAD kernels never crash"** — impossible to promise. Approximation:
  headless subprocess isolation for heavy work; residual risk: an un-saved
  document can still be lost. Save before risky work.

## Stage 5 - VISION

- Cross-app design sessions (one brief, FreeCAD + Blender + KiCad).
- Beginner recipe library with verified, replayable outcomes.

---

## Working order

1. Playable mounting-plate recipe (Stage 1 frontier).
2. Slice B GUI soak closure (the raster fail-closed guard is done).
3. Rerank A/B (ADR-011); the cloud H2H is done.
4. CAD-1K mining → first mined eval pack (eval-only; no redistribution; held out by app/domain).
5. One Stage 2 robustness item (headless isolation *or* dispatch health).