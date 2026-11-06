# Fixture product-reel assets

`fixture-reel.gif` is a **silent product reel**, not a live screen recording. It
uses the real scripted-CAD renders and the measured benchmark/gate numbers. A
live walkthrough is planned and would be recorded separately.

| file | what | size |
|---|---|---|
| `fixture-reel.gif` | 8 cards, 850×478, ~20 s | ~308 KB |
| `docs/social-preview.png` | 1280×640 GitHub social card | ~91 KB |

`docs/social-preview.png` is the GitHub social preview. Upload it in the
repository settings after the repo is public; GitHub does not use a repo file
automatically.

## Regenerate

```powershell
python docs/reel/make_reel.py
python docs/reel/make_reel.py --social-preview
```

The first command rebuilds the GIF. The second rebuilds only
`docs/social-preview.png`. Both use Pillow, the same palette, fonts, and gate
metrics; no ffmpeg is required. Fonts come from common Windows, macOS, or Linux
locations, with a Pillow default fallback. The desk renders are read from
`designs/desk-mounts/`. No private design assets are read, and the committed reel
contains no keyboard render. The committed GIF was generated on Windows;
regenerating on another OS changes font metrics and Pillow output, so treat the
bytes as illustrative rather than bit-identical.

The "Measured" card uses the `GATE_ID` and `GATE_METRICS` constants in
`make_reel.py`; the social card uses `GATE_METRICS`. Update them with
`README.md` and `docs/SAFETY-2026-11-02.md` after re-running
`python harness/scripts/verify_fast.py`. The benchmark line (60 cases, 501
checks, H2H average) must match the table in `README.md`.

## Editing the social card

The card text is drawn in `build_social_preview()` in `make_reel.py`. Each
`d.text(...)` or `_text_block(...)` call is one element:

| element | where / search for |
|---|---|
| brand + apps | `"FIXTURE"`, `"· FreeCAD · Blender · KiCad (planned)"` |
| gate status | `status = f"PASS · {GATE_METRICS}"` |
| headline | `"CAD that asks"` |
| safety line | `"Text in -> Named tools...` |
| checks / H2H | `"60 cases · 501 checks"`, `"H2H · Fixture"` |
| local metric | `"Local 4B"` |
| panel caption / footer | `"under-desk shelf"`, `"github.com/kcpatt27/fixture-cad"` |

To change text, edit the string. To remove a section, delete or comment the
`d.text` / `_text_block` call and move the following `y` values up to close the
gap. To resize, change the `_font(..., size)` value. Rebuild:

```powershell
python docs/reel/make_reel.py --social-preview
```

Direct PNG edits work too, but the next generator run overwrites them; use
`#0d1117` for the background color.

## What it shows

1. The loop: model proposes, harness verifies, FreeCAD/Blender execute.
2. No arbitrary code: named tools, schema, permission tier, undo.
3. Plan before apply: confirm, one undo, a repair pass.
4. Under-desk shelf render.
5. Laptop cradle render.
6. What it is not: no arbitrary code, no cloud by default, no fake numbers,
   KiCad next — a proposal, not shipped code.
7. 60 cases / 501 checks, 4-model head-to-head average, and the gate result.
8. Repo URL.

The gate numbers are the ones in `README.md` and `docs/SAFETY-2026-11-02.md`;
the benchmark numbers match `README.md`. The reel does not invent a UI or a
result.
