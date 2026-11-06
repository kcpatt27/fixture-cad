#!/usr/bin/env python3
"""Generate the Fixture silent product reel (GIF).

This is a *product reel*, not a live screen recording. It uses the real
scripted-CAD renders and the measured benchmark/gate numbers. The live
walkthrough is recorded separately.

Usage:
    python docs/reel/make_reel.py
    python docs/reel/make_reel.py --social-preview

Requires Pillow. Fonts are discovered from common Windows, macOS, and Linux
locations with a Pillow default fallback, so the script runs on any platform
(system fonts differ in metrics, so the rendered bytes are not identical across
machines).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 900
BG = (13, 17, 23)
PANEL = (22, 27, 34)
LINE = (48, 54, 61)
FG = (230, 237, 243)
DIM = (139, 148, 158)
GREEN = (63, 185, 80)
BLUE = (88, 166, 255)
AMBER = (210, 153, 34)

ROOT = Path(__file__).resolve().parents[2]
SHELF = ROOT / "designs" / "desk-mounts" / "underdesk-shelf" / "export" / "render_shelf_assembly.png"
CRADLE = ROOT / "designs" / "desk-mounts" / "laptop-cradle" / "export" / "render_cradle_assembly.png"

# Gate id shown on the "Measured" card. Update this together with README.md and
# docs/SAFETY-2026-11-02.md after re-running `python harness/scripts/verify_fast.py`.
GATE_ID = "20261106T125738Z / 20261106T132007Z"
PYTEST_COUNT = 140
FREECAD_SMOKES = "92/0"
BLENDER_SMOKES = "29/0"
GATE_METRICS = f"pytest {PYTEST_COUNT} · FreeCAD {FREECAD_SMOKES} · Blender {BLENDER_SMOKES}"

FONT_DIRS = [
    Path("C:/Windows/Fonts"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/truetype/liberation"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
]
SANS_FILES = ["segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf"]
SANS_BOLD_FILES = ["segoeuib.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf"]
MONO_FILES = ["consola.ttf", "DejaVuSansMono.ttf", "LiberationMono-Regular.ttf", "Menlo.ttc"]
MONO_BOLD_FILES = ["consolab.ttf", "DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf", "Menlo.ttc"]


def _font(filenames: list[str], size: int) -> ImageFont.FreeTypeFont:
    for directory in FONT_DIRS:
        for filename in filenames:
            path = directory / filename
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size)
                except OSError:
                    continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


F_BRAND = _font(MONO_BOLD_FILES, 26)
F_BRAND_DIM = _font(MONO_FILES, 24)
F_KICK = _font(MONO_BOLD_FILES, 20)
F_H1 = _font(SANS_BOLD_FILES, 84)
F_H1_SMALL = _font(SANS_BOLD_FILES, 64)
F_CAP = _font(SANS_FILES, 30)
F_CAP_SMALL = _font(SANS_FILES, 25)
F_MONO = _font(MONO_FILES, 23)
F_MONO_BOLD = _font(MONO_BOLD_FILES, 23)
F_MONO_SMALL = _font(MONO_FILES, 19)
F_FOOT = _font(MONO_FILES, 20)
F_BIG = _font(SANS_BOLD_FILES, 112)
F_LABEL = _font(MONO_BOLD_FILES, 20)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for word in words[1:]:
            candidate = f"{line} {word}"
            if draw.textlength(candidate, font=font) <= max_width:
                line = candidate
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def _text_block(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill,
    max_width: int,
    line_gap: int = 8,
) -> int:
    x, y = xy
    for line in _wrap(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y = bbox[3] + line_gap
    return y


def _card() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def _brand(draw: ImageDraw.ImageDraw, kicker: str) -> None:
    draw.text((90, 62), "FIXTURE", font=F_BRAND, fill=FG)
    draw.text((90 + draw.textlength("FIXTURE", font=F_BRAND) + 14, 64), "· tool-constrained text-to-CAD", font=F_BRAND_DIM, fill=DIM)
    # Card kicker sits in the top-right corner, optically centred on the brand line.
    _, by0, _, by1 = draw.textbbox((90, 62), "FIXTURE", font=F_BRAND)
    _, ky0, _, ky1 = draw.textbbox((0, 0), kicker, font=F_KICK)
    kicker_y = (by0 + by1) // 2 - (ky0 + ky1) // 2
    draw.text((W - 90 - draw.textlength(kicker, font=F_KICK), kicker_y), kicker, font=F_KICK, fill=BLUE)


def _footer(draw: ImageDraw.ImageDraw, text: str = "github.com/kcpatt27/fixture-cad") -> None:
    draw.text((90, H - 66), text, font=F_FOOT, fill=DIM)


def _panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=14, fill=PANEL, outline=LINE, width=2)


def _paste_render(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    path: Path,
    box: tuple[int, int, int, int],
    crop: tuple[int, int, int, int] | None = None,
) -> None:
    x0, y0, x1, y1 = box
    _panel(draw, box)
    if not path.exists():
        draw.text((x0 + 30, y0 + 30), f"missing render: {path.name}", font=F_MONO, fill=AMBER)
        return
    render = Image.open(path).convert("RGB")
    if crop:
        render = render.crop(crop)
    max_w, max_h = (x1 - x0) - 40, (y1 - y0) - 40
    scale = min(max_w / render.width, max_h / render.height)
    size = (max(1, int(render.width * scale)), max(1, int(render.height * scale)))
    render = render.resize(size, Image.LANCZOS)
    px = x0 + (x1 - x0 - size[0]) // 2
    py = y0 + (y1 - y0 - size[1]) // 2
    img.paste(render, (px, py))
    draw.rectangle((px - 1, py - 1, px + size[0], py + size[1]), outline=LINE, width=2)


def card_title() -> Image.Image:
    img, d = _card()
    _brand(d, "01 — SILENT PRODUCT REEL")
    y = _text_block(d, (90, 180), "CAD that asks\nbefore it cuts.", F_H1, FG, 1400, 4)
    y = _text_block(d, (90, y + 24), "The model proposes. The harness verifies. FreeCAD and Blender execute. STEP/STL comes out.", F_CAP, DIM, 1180, 10)
    tiles = [
        ("named tools", "JSON schema + permission tier"),
        ("confirm + undo", "one transaction per apply"),
        ("local-first", "Ollama by default"),
    ]
    x = 90
    band_top = y + 48
    band_bottom = 790
    tile_h = 220
    tile_top = band_top + max(0, (band_bottom - band_top - tile_h) // 2)
    for title, detail in tiles:
        box = (x, tile_top, x + 450, tile_top + tile_h)
        _panel(d, box)
        ty = tile_top + (tile_h - 72) // 2
        d.text((x + 26, ty), title, font=F_MONO_BOLD, fill=FG)
        d.text((x + 26, ty + 44), detail, font=F_MONO_SMALL, fill=DIM)
        x += 480
    _footer(d)
    return img


def card_no_code() -> Image.Image:
    img, d = _card()
    _brand(d, "02 — NO ARBITRARY CODE")
    y = _text_block(d, (90, 180), "Every mutation is a named tool.", F_H1, FG, 1400, 4)
    y = _text_block(d, (90, y + 24), "A JSON schema, a permission tier, and an undo transaction. The model never writes Python.", F_CAP, DIM, 1400, 10)
    panel_top = y + 48
    _panel(d, (90, panel_top, 1510, panel_top + 390))
    lines = [
        ("plan  under-desk shelf", FG),
        ("  1  create_body        name=\"Shelf\"", DIM),
        ("  2  new_sketch         body_name=\"Shelf\" plane=\"XY\" name=\"ShelfSketch\"", DIM),
        ("  3  sketch_rectangle   sketch_name=\"ShelfSketch\" width=360 height=180", DIM),
        ("  4  pad_sketch         sketch_name=\"ShelfSketch\" length=6", DIM),
        ("  5  pocket_sketch      sketch_name=\"ShelfSketch\" length=4", DIM),
        ("  6  export_stl         path=\"shelf.stl\"", DIM),
        ("", FG),
        ("tier: confirm   undo: one transaction", GREEN),
    ]
    yy = panel_top + 32
    for text, color in lines:
        d.text((124, yy), text, font=F_MONO, fill=color)
        yy += 36
    _footer(d)
    return img


def card_apply() -> Image.Image:
    img, d = _card()
    _brand(d, "03 — PLAN, THEN APPLY")
    y = _text_block(d, (90, 180), "The plan is visible before it runs.", F_H1, FG, 1400, 4)
    y = _text_block(d, (90, y + 24), "Apply or cancel. One undo. A repair pass if the plan is wrong.", F_CAP, DIM, 1180, 10)
    panel_top = y + 48
    _panel(d, (90, panel_top, 1510, panel_top + 390))
    lines = [
        ("[plan]   6 tools · confirm tier", BLUE),
        ("[apply]  body → sketch → pad → pocket → export", FG),
        ("[undo]   one transaction", GREEN),
        ("[result] shelf_left.stl · 372.6 cm³ · 1 solid", FG),
        ("", FG),
        ("The client owns the document. The harness never holds it.", DIM),
    ]
    yy = panel_top + 40
    for text, color in lines:
        d.text((124, yy), text, font=F_MONO, fill=color)
        yy += 50
    _footer(d)
    return img


def card_render(kicker: str, title: str, caption: str, path: Path, badge: str | None = None) -> Image.Image:
    img, d = _card()
    _brand(d, kicker)
    y = _text_block(d, (90, 180), title, F_H1_SMALL, FG, 1400, 4)
    y = _text_block(d, (90, y + 20), caption, F_CAP_SMALL, DIM, 1180, 8)
    if badge:
        d.text((90, y + 8), badge, font=F_LABEL, fill=AMBER)
    panel_top = y + (56 if badge else 48)
    _paste_render(img, d, path, (90, panel_top, 1510, panel_top + 390))
    _footer(d)
    return img


def card_bench() -> Image.Image:
    img, d = _card()
    _brand(d, "07 — MEASURED")
    y = _text_block(d, (90, 180), "60 cases. 501 checks. 4 cloud models.", F_H1_SMALL, FG, 1400, 4)
    y = _text_block(d, (90, y + 20), "Single-turn case pass on the same suite.", F_CAP_SMALL, DIM, 1180, 8)
    big_y = y + 80
    d.text((90, big_y), "96.7-98.3%", font=F_BIG, fill=GREEN)
    d.text((90, big_y + 140), "Fixture", font=F_LABEL, fill=DIM)
    d.text((760, big_y), "57.6-74.6%", font=F_BIG, fill=AMBER)
    d.text((760, big_y + 140), "freecad-ai", font=F_LABEL, fill=DIM)
    h2h_y = big_y + 140 + 58
    d.text((90, h2h_y), "H2H avg: 97.9% vs 66.3% (+31.7 pts)", font=F_MONO_BOLD, fill=GREEN)
    gate_top = h2h_y + 48
    d.rounded_rectangle((90, gate_top, 1510, gate_top + 140), radius=14, fill=PANEL, outline=LINE, width=2)
    d.text((124, gate_top + 30), f"PASS {GATE_ID}", font=F_MONO_BOLD, fill=GREEN)
    d.text((124, gate_top + 74), GATE_METRICS, font=F_MONO, fill=FG)
    _footer(d)
    return img


def card_end() -> Image.Image:
    img, d = _card()
    _brand(d, "08 — FIXTURE")
    y = _text_block(d, (90, 265), "Local-first.\nTool-constrained.\nMeasured.", F_H1, FG, 1400, 4)
    _text_block(d, (90, y + 30), "github.com/kcpatt27/fixture-cad", F_CAP, BLUE, 1180, 10)
    _text_block(d, (90, y + 90), "A live walkthrough is planned.", F_CAP_SMALL, DIM, 1180, 8)
    _footer(d)
    return img


def card_not() -> Image.Image:
    img, d = _card()
    _brand(d, "06 — WHAT IT IS NOT")
    y = _text_block(d, (90, 180), "Small on purpose.", F_H1, FG, 1400, 4)
    y = _text_block(d, (90, y + 24), "The limits are part of the design, not a missing feature list.", F_CAP, DIM, 1180, 10)
    panel_top = y + 48
    _panel(d, (90, panel_top, 1510, panel_top + 390))
    lines = [
        ("No arbitrary code.", "Named tools with a schema, a tier, and an undo transaction."),
        ("No cloud by default.", "Local Ollama; OpenRouter is opt-in."),
        ("No fake numbers.", "Every score has a run id; pending is not claimed."),
        ("KiCad is next.", "A proposal, not shipped code."),
    ]
    yy = panel_top + 32
    for headline, detail in lines:
        d.text((124, yy), headline, font=F_MONO_BOLD, fill=FG)
        d.text((500, yy), detail, font=F_MONO, fill=DIM)
        yy += 76
    _footer(d)
    return img


# Social-card text elements. Each draw call below is independent: edit the
# string to change it, delete or comment the call to remove it, and adjust the
# y coordinate to close the gap. Rebuild with:
#   python docs/reel/make_reel.py --social-preview
# Brand: FIXTURE + shipped apps (KiCad is demoted: proposed, not shipped).
# Headline. Safety line. Head-to-head + local-vs-cloud proof rows.
# Panel caption/footer.
def build_social_preview() -> Image.Image:
    w, h = 1280, 640
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    brand = _font(MONO_BOLD_FILES, 22)
    brand_dim = _font(MONO_FILES, 20)
    brand_muted = _font(MONO_FILES, 16)
    h1 = _font(SANS_BOLD_FILES, 72)
    mono_bold = _font(MONO_BOLD_FILES, 17)
    mono19 = _font(MONO_FILES, 19)
    proof_num = _font(MONO_BOLD_FILES, 26)
    proof_label = _font(MONO_FILES, 20)
    eyebrow = _font(MONO_BOLD_FILES, 15)
    cap = _font(MONO_FILES, 17)
    foot = _font(MONO_FILES, 18)
    muted = (110, 119, 129)
    footer_col = (190, 198, 208)

    d.text((64, 40), "FIXTURE", font=brand, fill=FG)
    x = 64 + d.textlength("FIXTURE", font=brand) + 12
    shipped = "· FreeCAD · Blender"
    d.text((x, 42), shipped, font=brand_dim, fill=DIM)
    x += d.textlength(shipped, font=brand_dim) + 10
    d.text((x, 44), "· KiCad (proposed)", font=brand_muted, fill=muted)

    pass_part = "PASS · "
    gate_part = GATE_METRICS
    status_len = d.textlength(pass_part, font=mono_bold) + d.textlength(gate_part, font=mono_bold)
    x = w - 64 - status_len
    d.text((x, 42), pass_part, font=mono_bold, fill=GREEN)
    d.text((x + d.textlength(pass_part, font=mono_bold), 42), gate_part, font=mono_bold, fill=DIM)

    y = _text_block(d, (64, 132), "CAD that asks\nbefore it cuts.", h1, FG, 650, 4)
    y = _text_block(
        d,
        (64, y + 14),
        "Text in → Named tools. Confirm before mutate → STEP/STL out.",
        mono19,
        BLUE,
        660,
        6,
    )
    d.text((64, 400), "HEAD-TO-HEAD · 4-MODEL AVERAGE", font=eyebrow, fill=DIM)
    num1 = "97.9% vs 66.3%"
    d.text((64, 426), num1, font=proof_num, fill=GREEN)
    d.text(
        (64 + d.textlength(num1, font=proof_num) + 14, 430),
        "Fixture vs freecad-ai",
        font=proof_label,
        fill=DIM,
    )
    d.text((64, 482), "LOCAL VS CLOUD", font=eyebrow, fill=DIM)
    num2 = "Local 4B model 97.2%"
    d.text((64, 508), num2, font=proof_num, fill=GREEN)
    d.text(
        (64 + d.textlength(num2, font=proof_num) + 14, 512),
        "· cloud 99.8%",
        font=proof_label,
        fill=DIM,
    )

    _paste_render(
        img,
        d,
        SHELF,
        (744, 104, 1216, 484),
        crop=(0, 0, 876, 704),
    )
    d.text((744, 500), "under-desk shelf · STEP + STL + print spec", font=cap, fill=DIM)
    d.text((64, h - 48), "github.com/kcpatt27/fixture-cad", font=foot, fill=footer_col)
    return img


def build_cards() -> list[Image.Image]:
    return [
        card_title(),
        card_no_code(),
        card_apply(),
        card_render(
            "04 — REAL PARTS",
            "Under-desk shelf.",
            "Two mirror halves, half-lap, cable ports, magnet pockets. STEP + STL + print spec.",
            SHELF,
        ),
        card_render(
            "05 — REAL PARTS",
            "Laptop cradle.",
            "Four printed pieces, measured slide-in height, 30 mm rear ledge.",
            CRADLE,
        ),
        card_not(),
        card_bench(),
        card_end(),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate the Fixture silent product reel")
    ap.add_argument("--out-dir", default=str(ROOT / "docs" / "reel"))
    ap.add_argument(
        "--social-preview",
        action="store_true",
        help="Regenerate docs/social-preview.png only",
    )
    args = ap.parse_args()

    if args.social_preview:
        out = ROOT / "docs" / "social-preview.png"
        build_social_preview().save(out)
        print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cards = build_cards()
    frames = [card.resize((850, 478), Image.LANCZOS) for card in cards]
    gif = out_dir / "fixture-reel.gif"
    frames[0].save(
        gif,
        save_all=True,
        append_images=frames[1:],
        duration=2500,
        loop=0,
        disposal=2,
        optimize=True,
    )
    print(f"wrote {gif} ({gif.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
