# Live walkthrough — shot list

> The README uses a silent product reel (`docs/reel/fixture-reel.gif`) built
> from the real renders and measured numbers; asset notes are in
> `docs/reel/README.md`. The shot list below is for a separate live
> walkthrough. A hosted video URL, if one exists, is separate from the GIF.

The walkthrough is evidence, not a trailer. Every clip shows the real harness: a
brief, a schema-validated plan, Apply/Cancel, undo, and a file that comes out.
Record one take per clip, then cut captions in. No fake UI, no edited output.

## Clip 1 — Under-desk shelf (30–40 s)

| time | shot |
|---|---|
| 0–5 s | cOS or a terminal: a one-line brief for an under-desk shelf; 360 mm wide, cables reachable. |
| 5–12 s | FreeCAD dock: the plan card lists named tools and args (`new_sketch`, `sketch_rectangle`, `pad_sketch`, `pocket_sketch`, `export_stl`). |
| 12–20 s | Apply one step; show the feature tree. Cancel a step; show the document unchanged. |
| 20–28 s | Apply the rest; export STEP/STL; open `manifest.json` and point at the measured volume/bbox. |
| 28–35 s | Cut to the printed shelf or the render; caption: "two mirror halves, half-lap, magnets, cable ports." |

## Clip 2 — Laptop cradle (25–35 s)

| time | shot |
|---|---|
| 0–5 s | Calipers on the closed laptop; record width and thickness. |
| 5–12 s | Set `CRADLE_INNER_W` / `CRADLE_SLOT` in the generator; rebuild. |
| 12–22 s | Show the regenerated rails + back halves; point at the 30 mm rear ledge and the front lip. |
| 22–30 s | Cut to the printed cradle under the desk, laptop sliding in. Caption: "measured fit, not a guessed one." |
| 30–35 s | Optional: show the STEP/STL manifest. |

## Clip 3 — Blender lane (15–20 s, optional)

The second app is the point of the name. A short Blender clip proves the
contract is not FreeCAD-only:

| time | shot |
|---|---|
| 0–5 s | Import the shelf STL into Blender; N-panel open. |
| 5–12 s | Run `clean_mesh` or `fit_view_selection` from the plan card; show the viewport change. |
| 12–18 s | Render or export; caption: "same harness, different executor." |

If the Blender addon is not installed on the recording machine, skip this clip
rather than faking it. The FreeCAD clips are enough for the first release.

## Fallback third case — SVG reference to plate

If the Blender clip is not ready, use the existing
`docs/fixtures/rect-outline.svg`:

1. Attach the SVG as a reference.
2. Import it as a sketch, pad it, add a hole, export STL.
3. Caption: "reference in, constrained solid out."

This uses the shipped Slice-B path and needs no new design.

## Recording checklist

- 1080p or 1440p, 30 fps; cursor visible; terminal font ≥ 16 px.
- Close unrelated windows, notifications, and personal folders.
- No `.env`, API keys, terminal history, private session state, local handoffs,
  or private design paths on screen.
- Keep raw clips private; publish only the edited reel.
- Host the live walkthrough on YouTube/Loom (unlisted is fine). The README
  `## Product reel` section keeps the silent GIF; add the live video URL
  separately rather than replacing the GIF or implying it is the same asset.
- Keep the clips short. A hiring manager will watch 60 seconds, not six minutes.

## Evidence to keep

- The plan card JSON for each clip.
- The exported STEP/STL and `manifest.json` for the desk mounts.
- The gate/run id for the benchmark, if the reel mentions benchmark numbers.
- A dated note of what was printed and measured (fit, not vibes).
