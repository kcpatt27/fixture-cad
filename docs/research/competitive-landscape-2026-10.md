# Competitive landscape and MCP verdict — 2026-10

**Scope.** Read-only audit of the attached `freecad-mcp-main.zip` (neka-nat/freecad-mcp
v0.1.25, Oct 2026 snapshot) against Fixture, plus an ecosystem scan of AI-CAD
projects on GitHub (GitHub API, 2026-10-04) and the live OpenRouter model catalog.
This updates the 2026-07-21 audit at `22a7d7b` recorded in
`benchmark/CASE-BACKLOG.md`.

## 1. What `freecad-mcp` is now

Architecture: a FreeCAD addon (XML-RPC server on `:9875` inside FreeCAD) plus a
separate MCP server (`uvx freecad-mcp`) launched by an MCP host such as Claude
Desktop. The host model drives FreeCAD; the MCP process only bridges.

| Fact | Value |
|------|-------|
| Tools | 17 (`create_object`, `edit_object`, `get_objects`, `execute_code`, `execute_code_async`, `execute_code_headless`, `get_async_status`, `get_rpc_status`, `run_fem_analysis`, parts-library, screenshots, …) |
| Execution model | Arbitrary Python: GUI thread, background thread with `commit()`, or separate `freecadcmd` process |
| Robustness | FIFO GUI dispatch with queue/execution budgets (90 s default, 1800 s cap), `GUI_DISPATCH_STUCK` detection, addon/server version handshake, bearer-token auth, IP filter |
| Feature breadth | FEM via CalculiX, parts library, view screenshots (9 orientations), reload-document, headless crash isolation |
| Code | ~3,655 Python LOC (src + addon), 114 test functions, docs, CI matrix: py3.12/3.13 × MCP SDK 1.x/2.x |
| Repo | 2,664★, 326 forks, 50 open issues, last push 2026-09-24, MIT |

The engineering is genuinely good. The failure-isolation patterns (headless
subprocess for crash-prone OCCT work, GUI-dispatch health, explicit timeout
budgets) are stronger than anything Fixture currently has.

## 2. What Fixture is

An end-to-end, local-first product: FastAPI harness + in-app chat docks for
**FreeCAD and Blender**. The model proposes **named tools only** — never Python.
The client validates, confirms, undo-wraps, and executes. Harness output is
schema-validated, intent-gated (`supported` / `ambiguous` / `partial` /
`unsupported`), and scored by a 60-case planner benchmark.

| Fact | Value |
|------|-------|
| Tools | FreeCAD 19, Blender 3 (named, args-schema, permission tier) |
| Execution model | `tool_call` + `meta` only; client-owned mutation; Apply/Cancel; one bounded repair |
| Verification | 60-case Path A planner bench, Path B mod-exec smokes, `verify_fast.py` gate |
| Code | ~7,864 Python LOC (harness + clients + bench), 98 test functions |
| Model source | Local Ollama by default; opt-in OpenRouter lane (2026-10) |

## 3. Head-to-head

| Dimension | freecad-mcp | Fixture | Who wins |
|-----------|-------------|-----------|----------|
| Who it's for | Power users with Claude Desktop / MCP hosts | CAD beginners inside FreeCAD/Blender | Different products |
| Model freedom | Any MCP host model (external) | Ollama local, OpenRouter opt-in | MCP (broader), Fixture (self-contained) |
| Safety model | Arbitrary Python with full privileges; host-level confirmation | Named tools, args schemas, confirm tier, undo, fail-closed gates | **Fixture** |
| Reproducibility | Depends on host model; no eval suite | Deterministic planner bench + smokes | **Fixture** |
| Blender | No | Yes (shared harness) | **Fixture** |
| Crash isolation | Headless `freecadcmd` subprocess | None (same-process runners) | **freecad-mcp** |
| Async/long ops | Background jobs + status polling | None (synchronous tools) | **freecad-mcp** |
| GUI health/timeout | Dispatch health, stuck detection, version handshake | Basic | **freecad-mcp** |
| Feature breadth | FEM, parts library, screenshots, reload | Sketches/pads/pockets, booleans, fillet/chamfer, SVG import, STL export, inspection, verify loop | MCP on breadth, Fixture on workflow depth |
| Distribution | MCP ecosystem (Claude Desktop et al.) | In-app docks | **freecad-mcp** |
| Test/CI depth | 114 tests, CI matrix | 98 tests, local fast gate | Comparable |

**Conclusion:** they are complementary, not substitutes. The MCP is a bridge for
external agents; Fixture is a product with its own UX and guarantees.

## 4. Should you just use the MCP?

- **As a tool today:** yes. Install it (or freecad-ai, below) to drive FreeCAD
  from Claude Desktop for power-user modeling. Zero cost, more capable than the
  current Fixture tool set for one-off work.
- **As a replacement for Fixture:** no. It cannot provide named-tool safety,
  dual-app support, intent gating, undo/confirm UX, or the planner benchmark.
  Adopting it would mean adopting "the agent writes Python" — the exact policy
  Fixture exists to reject.
- **Keep building:** yes, with narrowed positioning. Fixture cannot win a tool-
  breadth war; it can win on reliability, beginner recipes, and cross-app
  workflows.

## 5. Ecosystem context (GitHub, 2026-10-04)

| Project | Stars | What it is | Threat/lesson |
|---------|-------|------------|---------------|
| `ahujasid/mcp-for-blender` | 29,970 | Blender + any LLM via MCP/codegen | Shows ecosystem scale; not a named-tool product |
| `neka-nat/freecad-mcp` | 2,664 | The MCP analyzed here | Borrow infrastructure patterns; complementary |
| `ghbalf/freecad-ai` | 541 | FreeCAD workbench: chat, 50 named tools, 21 providers **including OpenRouter**, MCP server, skills, vision, Plan/Act, codegen fallback, keystore | **Closest product competitor** — see below |
| `spkane/freecad-addon-robust-mcp-server` | 244 | MCP bridge server | Confirms bridge pattern is commoditized |
| `bonninr/freecad_mcp` etc. | ≤229 | Earlier MCP bridges | Commoditized |

### The real competitive finding: `ghbalf/freecad-ai`

It validates the named-tool direction (tool calling is its default mode) but
already covers ground Fixture has not: ~50 tools, 21 providers, OpenRouter,
vision routing, skills, session resume, MCP server exposure, Plan/Act review.
Its codegen fallback and "Dangerous mode" mean its safety guarantee is weaker,
and it is FreeCAD-only.

Fixture's defensible differentiators against it:

1. **Strict named-tools guarantee** — no codegen path at all, so every mutation
   is schema-checked, confirm-tiered, and undo-wrapped.
2. **Cross-app harness** — one contract and one evaluator for FreeCAD + Blender.
3. **Eval discipline** — a scored planner benchmark and fail-closed intent gates
   that `freecad-ai` does not publish.
4. **Local-first default** with an auditable opt-in cloud lane.

Do not try to match its provider/tool breadth feature-for-feature.

## 6. What to borrow from the MCP (ranked, concrete)

| Pattern | Where it lands in Fixture | Effort |
|---------|-----------------------------|--------|
| Headless subprocess isolation for crash-prone geometry | FreeCAD client: run risky export/import or heavy OCCT in `freecadcmd`; GUI survives | M |
| GUI dispatch health + explicit timeouts | Client runner wrapper: per-tool budget, stuck marker, clear error to chat | M |
| Async job + status polling | Future long operations (`export_stl` of big assemblies, FEM later) | M/L |
| Screenshot plumbing (view/orientation/focus) | Slice C vision groundwork; already partly present via `fit_view_selection` | S/M |
| FEM/parts-library reference designs | Only if opened by the maintainer; convert to named tools, never raw code | L |
| MCP server exposure of Fixture tools | Distribution bet: let Claude Desktop drive the *safe* named-tool pipeline | M/L |

**Implemented 2026-10-04 (freecad-ai lessons):** fallback model chains
(`FIXTURE_FALLBACK_MODELS`, the response reports the model that answered) and
opt-in keyword tool reranking (`FIXTURE_TOOL_RERANK`, measurable with
`fixture_bench run --tool-rerank N`). Headless subprocess isolation and
GUI-dispatch health remain the top MCP patterns to borrow when client runners
are next touched.

## 7. Recommended position

1. **Use `neka-nat/freecad-mcp` as a power tool** alongside Fixture; keep the
   audit trail (roadmap "MCP-informed backlog" stays accurate).
2. **Continue Fixture** as the safe, cross-app, benchmark-verified product.
   Finish the playable FreeCAD mounting-plate slice before adding breadth.
3. **Borrow the two robustness patterns** (headless isolation, dispatch
   health/timeouts) the next time client runners are touched.
4. **Keep the OpenRouter lane** as the quality yardstick; it does not change the
   default local product.
5. **Revisit MCP server exposure** as the cheapest distribution step once the
   playable slice is stable.

### Decisions for the maintainer

- [ ] Install the MCP for power-user use? (recommended: yes)
- [ ] Prioritize headless isolation / dispatch health in the next client slice?
- [ ] Add an MCP server wrapper around the harness to the roadmap?
- [ ] Keep the strict no-codegen rule even where `freecad-ai` is more capable?