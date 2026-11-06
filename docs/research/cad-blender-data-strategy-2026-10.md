# CAD + Blender dataset strategy - 2026-10

> **Eval-only:** CAD-1K and BlenderLore are used for evaluation only; no data is
> redistributed.

**Assets on hand:** the local CAD-1K mirror (confirmed, 207 GB / 1,018 h)
and a 600 GB+ Blender corpus (location unconfirmed). This document turns them
into decision-ready options and a phased plan. Nothing here requires committing
to training on day one.

## 0. Inventory results (2026-10-04)

### CAD corpus - confirmed: the local CAD-1K mirror (207 GB, "CAD-1K Open v2")

509 end-to-end Windows screen recordings across seven CAD applications,
1,018.1 hours, 5,455 public task objects. Every task directory contains:

| File | What it gives us |
|------|------------------|
| `task_desc.json` | Task prompt, domain, app, reference inputs, deliverables |
| `narration.json` | Frame-level `action` + `intent` + `details` annotations |
| `frame_events.json` | Raw input telemetry: mouse moves, clicks, screen config (10s–100s of MB) |
| `rubrics.json` | Dimensioned, verifiable requirements per task |
| `clip.mp4` | Screen recording (30 fps) |
| `output_files/` | Native deliverables (sldprt, slddrw, dwg, skp, rvt, prt, catpart, pdf…) |
| `input_files/` | Reference sheets (pdf/jpeg/dwg/png) |

Distribution: AutoCAD 312 tasks / 675 h · Revit 24 / 117 h · SOLIDWORKS 114 /
101 h · SketchUp 30 / 95 h · CATIA 7 / 18 h · NX 20 / 10 h · V-Ray 2 / 2.5 h.
Domains: **Mechanical CAD 242 tasks / 197 h**, Architectural 193 / 566 h,
Interior 35 / 111 h, BIM 23 / 90 h.

**Best-fit subset for Fixture:** SOLIDWORKS + NX + CATIA + mechanical AutoCAD
≈ 360 tasks. The architectural/BIM majority does not map to FreeCAD/Blender
mechanical tooling.

**Why this is good news:** `narration.json` already contains human-written
`action`/`intent` pairs, and `rubrics.json` carries dimensioned acceptance
criteria. That is an *instruction → action → verification* triple without any
video processing. `frame_events.json` is raw input telemetry usable later for
vision/UI-action research, not for tool-call labels.

**Source confirmed 2026-10-04:** HuggingFace
[`markov-ai/cad-1000-hours`](https://huggingface.co/datasets/markov-ai/cad-1000-hours)
— public, ungated, **111,561 downloads**, 530 likes, 5,457 files. The local
The local CAD-1K mirror matches the official card and stats exactly.
**License: none declared** — no `license:` tag, empty card metadata, and no
LICENSE file in the local copy. Treat as **eval/research only**; do not
redistribute clips or derived assets until the author grants terms. The
similarly named re-uploads (QMlink001, hiwuxiyi, …) are a different variant
(597 workflows / 1,021.64 h); markov-ai is the official source.

### GPU — RTX 5060 Ti, 16 GB

Comfortable for 7B QLoRA at 4-bit; 14B QLoRA is not practical locally. Plan
distillation around a 7B-class student, with the 27B local Qwen3.8 as a
teacher/eval companion rather than a fine-tune target.

### Blender corpus — identified: `FreedomIntelligence/BlenderLore` (HuggingFace)

The 600 GB material is the BlenderLore dataset, not a local folder. Public,
ungated, self-declared **apache-2.0** license (verify provenance before shipping
derived artifacts), 21.7k downloads; target 22,360 video-associated Blender
project instances, uploads in progress so the published subset grows. Per sample:

| File | What it gives us |
|------|------------------|
| `asset.blend` | Final editable Blender scene |
| `preview.png` | Rendered reference image |
| `tutorial.md` | Step-by-step text+image creation tutorial |
| optional `mp4` | Video preview |

Fit: `tutorial.md` is the narration-equivalent for recipe mining; `.blend`
files give real-world scenes for `clean_mesh` calibration and Path B fixtures;
`preview.png` pairs are future Slice C vision material. Status: not cloned yet —
Phase 1 pulls a subset when the data pipeline starts.

### Adjacent assets already on disk

The local dataset root also holds general tool-use SFT sets: `hermes-function-calling-v1`,
`Nemotron-RL-Agentic-Conversational-Tool-Use-Pivot-v1`, and
`Nemotron-RL-instruction_following`. They are not CAD-specific, but they are
candidate format-discipline data for a planner fine-tune. Contamination and
format-mismatch review required before use.

## 1. Options, ranked by value/effort

| # | Option | Value | Effort | Risk | Requires |
|---|--------|-------|--------|------|----------|
| A | Mine tutorial requests → scored Path A cases | High | Low | Low | Inventory; framing |
| B | Beginner recipe packs (roadmap item 5) | High | Low/M | Low | Same corpus as A |
| C | Few-shot retrieval for the planner (RAG) | Med/High | M | Low | A's pairs |
| D | Distill cloud quality into local models (SFT/LoRA) | Med | High | Med | GPU; A's scorer as filter |
| E | Blender asset search/insert tool | High (if asset library) | M | Med | BlenderLore scenes; metadata |
| F | Mesh-quality stats to calibrate `clean_mesh`/exports | Med | Low | Low | BlenderLore `.blend` parsing |
| G | Vision lane data (screenshots ↔ facts) | High later | High | Med | Slice C opened |
| H | Synthetic parametric variants for Path B tests | Med | M | Low | Parametric sources |

## 2. Option details

### A. Evaluation corpus (do first)

The 60 hand-written Path A cases are the project's best asset; CAD-1K is a case
factory with labels already present. Pipeline:

1. Read `task_desc.json` + `rubrics.json` for the request and acceptance facts.
2. Pull `narration.json` intervals (`action`, `intent`, `details`) as the
   operation trace — no audio transcription needed.
3. Extractor LLM (cheap OpenRouter model) maps each trace onto the Fixture
   tool vocabulary: user request phrasing, expected named tools, expected args,
   intent status.
4. Deterministically validate against the 19-tool catalog; unmappable requests
   become `unsupported`/`ambiguous` cases — refusal behavior is part of the
   product and is under-tested today.
5. Human review pass; keep case files in the existing format with `tags:
   ["mined", "<app>", "<task_id>"]`.
6. **Hold out entire apps or domains** from any training/retrieval set to avoid
   contamination (e.g. train on SOLIDWORKS traces, eval on NX/CATIA).

Target: 200–500 reviewed cases. This also feeds `benchmark/CASE-BACKLOG.md`.

### B. Recipe packs (product, not ML)

The corpus is instructional material. Extract repeating beginner recipes
(bracket, enclosure, hinge, adapter, phone stand) and encode them as
deterministic named-tool expansions — exactly roadmap item 5. No model required
at runtime; the planner picks a recipe and expands it. Ships visible value
immediately.

### C. Few-shot retrieval

Index `(request, context) → reviewed plan` pairs with local embeddings
(`nomic-embed-text` is already installed). At plan time, retrieve k=1–3 examples
into the user prompt. Measure against A: does the 7b/14b close the gap to cloud?

Prompt budget warning: the FreeCAD system prompt is already ~20.7 KB (~5.2k
tokens). Keep retrieved examples short (request + tool list, not full JSON) and
gate them behind a flag until scored.

### D. Distillation / fine-tune (only if the ceiling is proven)

Use cloud models through OpenRouter as teachers: generate plans for A's inputs,
keep only outputs that pass schema validation + the existing scorer, then QLoRA
a local 7B/14B. Realistic outcomes:

- Format/refusal adherence improves fastest (cheap wins).
- Reasoning quality may not move much; don't assume it will.
- 7B QLoRA ≈ 16 GB VRAM; 14B QLoRA ≈ 24–32 GB. Budget the GPU time honestly.

The benchmark must stay the judge: train on a split, score on held-out series.

### E. Blender asset retrieval tool

If the 600 GB includes `.blend`/asset libraries: extract name/tags/thumbnail/
polycount metadata, embed thumbnails or text, and add two named tools:
`search_asset` (read-only) and `insert_asset` (confirm-tier, appended/linked).
This converts storage into a product feature — a semantic parts library for
Blender, mirroring what `freecad-mcp` does for the FreeCAD parts library but
local to your corpus.

### F. Mesh-quality calibration

Parse a sample of `.blend` files headlessly (`blender -b`): polygon counts,
non-manifold edges, n-gons, non-uniform scale, loose geometry. Use the
distribution to set `clean_mesh` thresholds and to seed Path B test fixtures
with real-world messy meshes.

### G. Vision data (defer until Slice C)

Screen recordings and renders give image↔geometry pairs for a local VLM
(Qwen-VL class) or for verification prompts. Highest effort; revisit when the
vision slice opens.

### H. Synthetic parametric variations

From parametric sources, generate dimension variants programmatically and run
them through Path B runners. Cheap robustness coverage for FreeCAD/Blender
execution (not planner scoring).

## 3. Phased plan

| Phase | Deliverable | Exit criteria |
|-------|-------------|---------------|
| 0 | Inventory + rights | CAD done; BlenderLore identified (apache-2.0 self-declared); clone deferred to Phase 1 |
| 1 | 200–500 mined Path A cases + `--tag mined`; `clean_mesh` stats | Local models scored on mined cases; misses triaged |
| 2 | Retrieval (C) behind a flag | A/B on phase-1 cases: measurable gain or it is dropped |
| 3 | Distillation (D) or asset tool (E) — pick one | Phase 2 proves a ceiling, or assets prove valuable |
| — | Never | Train/retrieve on the eval split; ship assets without rights |

## 4. Cost sketch

- Full Path A suite: ~275k input tokens + ~24k output per model → **$0.05
  (GLM/DeepSeek-class) to ~$1.60 (Opus-class)** per model run.
- 1,000 h transcription: local Whisper on your GPU, days of wall-clock, ~$0 API.
- Mining extraction: one cheap cloud pass over transcript segments, a few dollars.
- Embeddings: local, free. QLoRA: GPU time only.

## 5. Decisions for the maintainer

- [ ] Confirm the CAD-1K license (eval-only until then). BlenderLore is
      apache-2.0 per its HF card, uncloned until Phase 1.
- [ ] Approve a mined-into-eval policy that keeps apps/domains held out.
- [ ] Is fine-tuning in scope for the 16 GB GPU, or is retrieval the ceiling?
- [ ] Does the Blender corpus include shippable assets (enables E) or is it
      internal-only (F/G only)?