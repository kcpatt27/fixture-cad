# Video insights → Fixture backlog map

**Date:** 2026-07-24  
**Sources (desktop transcripts):**

1. *Best CAD Software for 2026 — TOP 9 CAD Tools Compared* (Plasticity, Shapr3D, Fusion, FreeCAD, Onshape, enterprise set; ideation via Light Loop–style sketch→image→ortho).
2. *Стул, сопромат и ИИ* (generative design from strength-of-materials / load constraints; wood + 3D-printed structural skeleton; additive manufacture as the path for organic load paths).

This note is roadmap fuel only. It does **not** open a build pack. Concrete next pack sketch: [`ideation-to-cad-pack.md`](ideation-to-cad-pack.md).

---

## What the videos actually argue

### CAD roundup

- **Direct vs parametric vs hybrid.** Plasticity = direct (fast start, no history). Fusion/Onshape = parametric history. Shapr3D sells toggle between both. Creatives fear parametric because early edits break later features; engineers want history and assemblies.
- **FreeCAD callout.** Broad capability (parametric, FEM, experimental CFD, arch, basic CAM) with a cluttered UI and a steeper beginner ramp than polished commercial tools.
- **Ideation before CAD.** Napkin sketch → AI product images / video → flattened orthographic CAD sketch → import and trace in CAD. Goal: never stare at a blank document.
- **Indie focus.** Prefer tools that do not need enterprise IT; TechDraw / 2D for manufacture called out as a differentiator (Shapr/Onshape).

### Chair / сопромат / AI

- **Generative design = constrained FEA story.** Fix mounts, loads, keep-outs; solver keeps only material that carries load. Organic “bone” forms are a result of the calculation, not a sculpt.
- **Fabrication split.** Traditional wood for some parts; printed ABS skeleton for the complex load path. Additive is treated as the only practical way to realize that geometry.
- **Nature as metaphor, not a product feature.** Evolution / trees as analogy for topology + support trees.

---

## Map onto Fixture

| Claim / workflow | Status in project | Action |
|------------------|-------------------|--------|
| FreeCAD powerful but hard for beginners | Core product thesis (`productContext`) | Keep: chat + named tools + Apply/Cancel + post-Apply verify |
| Direct vs parametric duality | FreeCAD (parametric/engineering) + Blender (mesh/direct) already | Keep dual clients; teach planner to route intent by app; do not build a Plasticity clone |
| Parametric “early edit breaks later” fear | N1 intent honesty + N2 inspect + confirm tier | Keep; do not add silent history rewriting |
| Ideation → ortho → CAD | Vision / snapshot P2; import/export on later sequence | **Open as Ideation pack** after N3 commit (see pack doc) |
| TechDraw / manuf drawings | Explicit backlog (`roadmap`, `progress`) | Later; after multi-solid + export habits |
| FEM / generative from loads | Listed with FEM in later sequence | **Separate pack after Ideation + export**; do not fold into N4 |
| Cloud collab (Onshape) | Non-goal (local-only) | Reject |
| Enterprise CAD (SW / Creo / NX) | Out of scope | Ignore |
| Clone Light Loop / cloud image gen | Cloud + product dependency | Reject; allow **local** reference images + optional local vision later |
| Arbitrary Python to “just generate the mesh” | Hard rule | Reject |

**Takeaway:** Video 1 mostly validates what Fixture already is. The actionable gap is the **blank-document problem** (ideation → bounded tool plan). Video 2 is a real north-star for FreeCAD FEM, but it sits behind export and solid modeling maturity.

---

## Priority implications (do not reorder N3)

1. **Finish/commit N3** (cylinder, placement, boolean, chamfer) — substrate for any concept build.
2. **Ideation → CAD pack** (text-first, then optional local image/ortho import) — see pack doc.
3. **Export STL** (and later STEP) — closes “concept → printable” without generative.
4. **TechDraw / drawing views** — manuf communication.
5. **FEM constraint + solve + (much later) topology keep-material** — chair-video story as named tools, still no arbitrary Python.

Cloud LLMs and through-all Pocket / assemblies stay on their existing gates.

---

## Explicit rejects (so we do not drift)

- Building a new FreeCAD UI to “look like Shapr.”
- Shipping topology optimization before boring export + inspect loops work.
- Calling a Blender sculpt “generative design.”
- Pulling commercial ideation SaaS into the harness.
- Treating video marketing claims as FreeCAD API capability without a runner prototype.
