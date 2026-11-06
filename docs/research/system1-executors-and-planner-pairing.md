# System-1 executors and planner pairing — 2026-10-06

*Research note: what "System-1" means, where small next-action policies help,
how Taiga-S1 could pair with Fixture, whether dual-process can be baked into
one model, and what a desktop (computer-use) System-1 would take. This is not a
commitment; the last section lists the queued experiment.*

## What "System-1" means here

Kahneman's two-systems analogy applied to agents:

- **System 2** = deliberate reasoning: the LLM planner. Slow, expensive, good
  at novel problems ("what should I build?").
- **System 1** = fast reflex: a tiny model that reads a rich state and picks
  the **next action** from the set of currently-valid actions. It recognizes
  "in this state the next click is X"; it does not reason.

Taiga-S1 is the concrete case: 1.2M params, ~4 ms/decision on CPU, trained on
24k synthetic sessions / ~590k teacher-labeled decisions plus two DAgger
rounds. It picks the **command**, not the numbers — dimensions come from the
goal. Its generalization tricks (randomized position IDs, ordinal coupling,
modular "done?" policy, factorized feature types) are architecture-level
lessons independent of CAD.

## When System-1 works (and when it doesn't)

Rule: a System-1 policy works when the task is **"given rich state, pick the
next action from an enumerable, valid-at-this-step set, where a teacher can
label correctness."** It fails when the point is open-ended generation or
novel reasoning.

| Domain | Verdict | Why |
|---|---|---|
| Computer use (a11y tree) | **Strong** | Taiga's own thesis; per-app state→action spaces |
| Gaming sidekick | **Strong** for reflex/next-action; no for banter/strategy |
| CAD execution | **Proven** (96–98% reproduced on this machine) |
| Coder | No as primary; narrow variants only (next-tool routing, edit-category choice) |
| Creative writing | No — generation quality *is* the product |
| Knowledge librarian | Partial — router over retrieval actions, not the search itself |
| Context compacter | Partial — keep/drop scorer (System 1) + LLM writes the summary |

## Pairing Taiga with a planner for CAD

The natural architecture, and it fits Fixture's existing split:

```
LLM planner (System 2)          Taiga policy (System 1)
NL request → ordered feature goal → reads live FreeCAD state,
                                   picks the next command (~ms),
                                   recovers from mistakes
        Fixture harness                 freecad_s1 runtime (socket/worker)
```

- **What exists:** Taiga's goal schema, runtime, trained policy; Fixture's
  planner, safety contract, and client-owned execution model.
- **What's missing:** an NL → Taiga-goal compiler; joining Taiga's runtime to
  the Fixture client; a safety envelope (bounded steps, Apply/Cancel, undo).
- **Why it could win:** one LLM call per plan instead of per step; execution in
  milliseconds; state-sensitive recovery is trained, not prompted.
- **Honest limits:** Taiga covers synthetic PartDesign-style features — no
  organic/futuristic geometry; sketches attach only to XY base or Face+Z, so
  vertical L-flanges are out; flat plates + holes + pockets + patterns +
  fillets are in. Named tools stay for everything else.
- **Coexistence:** named tools for covered operations; Taiga as an executor
  lane for GUI-command sequences; recipes could be executed by the policy.

## Dual-process in one model: could System 1 + 2 be baked in?

| Approach | What it is | Maturity |
|---|---|---|
| **Cascade / router** (what we do) | LLM planner + tiny policy, a gate decides who handles the step | Shipping everywhere; cheapest; debuggable |
| **Adaptive compute in one model** | Early-exit layers, mixture-of-depths, latent reasoning, variable thinking budgets trained with a compute penalty | Research-grade; no clean product recipe |
| **Speculative decoding** | Tiny draft proposes, big model verifies — a literal System1/2 loop | Shipping, but only accelerates tokens; it does not plan |
| **Joint hierarchical network** | One network with planner and executor modes trained on mode-switch labels | Frontier research; data recipe unsettled |

**Cost guestimates (order of magnitude, rented H100-class):**

- **1B dual-process proof**, 100–200B tokens: ~4e21–1e22 FLOPs →
  **1–3k GPU-hours → $3k–15k**, plus weeks of rollout/teacher engineering.
  Personal-lab feasible.
- **7B**, 1–2T tokens: ~1e23 FLOPs → **30–80k GPU-hours → $2M–8M**.
- **Frontier 100B+**: **$50M–$500M+**, still a research question.

Pragmatic read: two-model pairing gets ~90% of the benefit for ~1% of the
cost. Baking in pays when two models are infeasible (edge/memory) or when you
own proprietary mode-switch data.

## Computer-use System-1: does it already exist?

No drop-in Taiga equivalent for the desktop was found:

- Today's computer-use agents are **big VLMs** (Claude computer use,
  OpenAI operator-class, Gemini computer use, UI-TARS, …).
- Small GUI specialists exist (~2–7B: UI-TARS-2B, ShowUI, OS-Atlas,
  OmniParser) but they are vision-language grounders, not 1.2M a11y-tree
  policies.
- Taiga's author names the accessibility-tree step as future work, so this is
  an open lane.

**Recipe to build one** (mirrors Taiga):

1. **Environment:** Windows UIA tree (`pywinauto`/`uiautomation`) → tokenize
   elements (role, name, value, enabled, bbox, focus); browser DOM alternative.
2. **Action space:** per-state valid actions — invoke / set_value / expand /
   select / scroll / key chords ("which buttons are enabled").
3. **Teacher:** scripted pywinauto flows for 20–100 tasks in **one app**;
   resets via restart/profile swap.
4. **Datagen:** 10k–50k sessions, 0.5–2M decisions with noise injection (CPU
   workers; no GPU needed).
5. **Model:** 1–5M param transformer over state tokens + candidate actions
   (Taiga's architecture is public, MIT).
6. **DAgger ×2**, fit temperature, eval on held-out tasks.
7. **Safety:** allowlisted apps/controls, undo (`Ctrl+Z`), dry-run, confirms.

The grind is environment + teacher scripting (weeks per app), not training.
a separate local agent stack is a plausible host for the reusable runtime (a11y tree + action
server). Gaming follows the same shape with game-state APIs plus ToS/anti-cheat
caveats.

## Queued experiment: goal compiler

Their runtime builds a target for **any** goal (`build_target` runs the clean
expert headlessly), so the experiment is:

1. Craft feature-list goals for the desk parts (flat plates + holes + pockets +
   fillets; no vertical flanges).
2. Run Taiga's policy headless against those goals and score IoU/steps.
3. If feasible: sketch the pairing (harness emits goal JSON; Taiga executes;
   human Apply), then decide executor-lane vs recipe-executor vs drop.

## Result: desk goals through the runtime (2026-10-06)

Executed via `benchmark/competitors/taiga_desk_eval.py`; run evidence +
probe in `benchmark/results/20261006T214840Z/`. Setup: Taiga-S1 `release/hf`,
CPU, clean PartDesign start, argmax, 1 episode per goal (deterministic policy).

| goal | features | expert | policy | IoU | steps vs expert |
|---|---|---|---|---|---|
| `desk_laptop_cradle_plate` | 220×90×6 box + 4 hole_std + fillet_top | feasible | success, clean | 1.0000 | 40/40 |
| `desk_shelf_plate` | 300×160×10 box + pocket_rect + 2 hole_std + fillet_top | feasible | success, clean | 1.0000 | 34/34 |
| `desk_cradle_side_plate` | 90×60×6 box + 2 hole_std + fillet_top | feasible | success, clean | 1.0000 | 26/26 |

All three built exactly: agreement 1.0, zero deviations, exact step parity.
Dimensions far outside the training ranges (220/300 mm vs 20–80 mm sampled)
did not matter — numbers come from the goal, normalized by `scale`.

Vocabulary-boundary probe (same run dir, `flange_probe.json`):

- a 90×6×60 **vertical wall as `base_box`** → feasible, 10/10 steps built;
- an **`l_flange` feature** → fails fast at the expert boundary
  (`KeyError: 'l_flange'`) before the policy ever runs — out-of-vocabulary
  compiler output cannot produce silently wrong geometry.

Coverage read against the desk-mount print spec: plates, vertical-axis
holes/pockets, fillets, and upright slabs as separate boxes are **in**. The
cradle's L/U pieces, fused multi-face geometry, retention lips, ribs, screw
holes through vertical faces, and organic cable openings are **out** (sketches
attach only to the XY base or `Face+Z`; profiles are rectangle/circle/hexagon
only). The desk parts therefore stay a scripted-CAD job; Taiga's lane is
flat-part execution from an ordered goal, with the compiler pinned to the goal
vocabulary.

## Result: vocabulary-matched (design-for-Taiga) experiment (2026-10-09)

Reworked the desk parts - and two additional motifs - into Taiga's *actual
recipe vocabulary* (flat `base_box` plates, `boss_box` walls, `shell`,
`fillet_vertical`, `hole_std`) and ran them headless
(`benchmark/competitors/taiga_vocab_goals.json`, run `20261009T195705Z`):

| reworked goal | composition | result | IoU | steps |
|---|---|---|---|---|
| shelf tub | base_box + shell | success/clean | 1.0000 | 12/12 |
| shelf floor, perforated | box + 3× hole_std + fillet_top | success/clean | 1.0000 | 33/33 |
| wall on floor | box + boss_box | success/clean | 1.0000 | 18/18 |
| three walls | box + 3× boss_box | success/clean | 1.0000 | 34/34 |
| cradle back plate | standing box + fillet_top | success/clean | 1.0000 | 12/12 |
| rail as T-section | arm box + edge boss + fillet_top | success/clean | 1.0000 | 20/20 |
| trackball ring | box + Ø34 hole_std | success/clean | 1.0000 | 17/17 |
| tub + rounded corners | shell → fillet_vertical | **budget** | 0.22 | 34/14, 12 deviations |
| tub + rounded corners (reordered) | fillet_vertical → shell | success/clean | 1.0000 | 14/14 |
| tub + chamfered top | shell → chamfer_top | success/clean | 1.0000 | 16/14 |
| walls + vertical fillet | box + boss + fillet_vertical | **expert-infeasible** | — | — |

Reads:

- **Design-for-vocabulary works.** Everything expressible from the recipe
  ingredients builds at IoU 1.0000 with exact step parity — including
  multi-boss stacking (`base_box` + 3 `boss_box` walls) and a shelled tub.
  One ingredient list, many real parts.
- **Failures are compositional, not ingredient-level.** `shell →
  fillet_vertical` is unseen in training: the policy loops
  `PartDesign_Thickness` / `Std_Undo` to the step budget (history captured).
  The same end shape is reachable by reordering (`fillet_vertical → shell`,
  14/14) or substitution (`shell → chamfer_top`, 16/14) — design-for-
  vocabulary escape hatches exist for every observed failure.
- **One composition is infeasible for the reference expert itself**
  (`boss → fillet_vertical`, "expert path produced an invalid feature") — it
  fails closed at feasibility, before any policy risk.
- **Implication for the goal compiler:** it must encode accepted
  *compositions*, not just ingredients; and each missing composition is a
  cheap, targeted synthetic-data job (the teacher already labels the states).