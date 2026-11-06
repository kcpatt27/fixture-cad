"""Tiny STL previewer — renders binary STLs to PNG for visual QA.

Pure stdlib (struct/zlib): parses binary STL, orthographic isometric/front/side
panels, flat shading + painter's algorithm, writes RGB PNG. Exists so the
desk-mount exports can be eyeballed without opening CAD or a viewer.

  python designs/desk-mounts/stl_render.py            # renders both assemblies

Parts are exported in assembled coordinates, so combining files reconstructs
the assembly.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

EXPORTS = {
    "laptop-cradle": Path(__file__).resolve().parent / "laptop-cradle" / "export",
    "underdesk-shelf": Path(__file__).resolve().parent / "underdesk-shelf" / "export",
}
PANELS = {
    "iso": (0.72, 0.95, 0.62),      # from front-right-above
    "front": (0.0, 1.0, 0.0),       # looking at the +Y face
    "side": (1.0, 0.0, 0.0),        # looking at the +X face
}
LIGHT = (0.45, 0.35, 0.82)
PANEL_W, PANEL_H = 860, 680
GUTTER = 12
BG = (246, 246, 244)


def load_stl(path: Path) -> list[tuple[tuple[float, float, float], tuple, tuple]]:
    data = path.read_bytes()
    (count,) = struct.unpack_from("<I", data, 80)
    tris = []
    off = 84
    for _ in range(count):
        vals = struct.unpack_from("<12f", data, off)
        tris.append((vals[3:6], vals[6:9], vals[9:12]))
        off += 50
    return tris


def norm(v):
    m = math.sqrt(sum(c * c for c in v)) or 1.0
    return (v[0] / m, v[1] / m, v[2] / m)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def render_assembly(
    parts: list[tuple[list, tuple[int, int, int], str]],
    out: Path,
) -> None:
    all_pts = [v for tris, _, _ in parts for tri in tris for v in tri]
    lo = [min(p[i] for p in all_pts) for i in range(3)]
    hi = [max(p[i] for p in all_pts) for i in range(3)]
    center = tuple((lo[i] + hi[i]) / 2 for i in range(3))
    radius = max(hi[i] - lo[i] for i in range(3)) / 2

    width = 3 * PANEL_W + 4 * GUTTER
    height = PANEL_H + 2 * GUTTER
    img = bytearray(bg for bg in BG) * (width * height)

    for pano, (name, eye) in enumerate(PANELS.items()):
        e = norm(eye)
        upw = (0.0, 0.0, 1.0)
        right = norm(cross(upw, e))
        upv = cross(e, right)
        ox = GUTTER + pano * (PANEL_W + GUTTER)
        oy = GUTTER
        scale = radius * 2.25
        zbuf = [-1e18] * (width * height)

        for tris, color, _label in parts:
            for tri in tris:
                pu = [dot(sub(v, center), right) for v in tri]
                pv = [dot(sub(v, center), upv) for v in tri]
                pd = [dot(sub(v, center), e) for v in tri]
                sx = [ox + PANEL_W / 2 + u / scale * PANEL_W for u in pu]
                sy = [oy + PANEL_H / 2 - v / scale * PANEL_H for v in pv]
                n = norm(cross(sub(tri[1], tri[0]), sub(tri[2], tri[0])))
                shade = 0.42 + 0.58 * max(0.0, dot(n, norm(LIGHT)))
                col = tuple(min(255, int(c * shade)) for c in color)
                fill_triangle(img, zbuf, width, height, list(zip(sx, sy)), pd, col)

    out.parent.mkdir(parents=True, exist_ok=True)
    write_png(out, width, height, img)
    total = sum(len(t) for t, _, _ in parts)
    print(f"{out.name}: {total} triangles, {len(parts)} pieces -> {out}")


def fill_triangle(img: bytearray, zbuf: list, w: int, h: int, pts, depths, color) -> None:
    (x0, y0), (x1, y1), (x2, y2) = pts
    d0, d1, d2 = depths
    minx, maxx = max(0, int(min(x0, x1, x2))), min(w - 1, int(max(x0, x1, x2)) + 1)
    miny, maxy = max(0, int(min(y0, y1, y2))), min(h - 1, int(max(y0, y1, y2)) + 1)
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denom) < 1e-9:
        return
    r, g, b = color
    for y in range(miny, maxy + 1):
        for x in range(minx, maxx + 1):
            a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / denom
            bb = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / denom
            cc = 1 - a - bb
            if a >= -0.002 and bb >= -0.002 and cc >= -0.002:
                idx = y * w + x
                depth = a * d0 + bb * d1 + cc * d2
                if depth > zbuf[idx]:
                    zbuf[idx] = depth
                    i = idx * 3
                    img[i], img[i + 1], img[i + 2] = r, g, b


def write_png(path: Path, w: int, h: int, rgb: bytearray) -> None:
    raw = b"".join(b"\x00" + bytes(rgb[y * w * 3 : (y + 1) * w * 3]) for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main() -> int:
    cases = {
        "laptop-cradle": [
            ("cradle_rail_left", (86, 132, 190), "rail L"),
            ("cradle_rail_right", (86, 132, 190), "rail R"),
            ("cradle_back_left", (196, 132, 84), "back L"),
            ("cradle_back_right", (196, 132, 84), "back R"),
        ],
        "underdesk-shelf": [
            ("shelf_left", (86, 132, 190), "shelf L"),
            ("shelf_right", (116, 168, 96), "shelf R"),
        ],
    }
    assembly_names = {
        "laptop-cradle": "render_cradle_assembly.png",
        "underdesk-shelf": "render_shelf_assembly.png",
    }
    for case, pieces in cases.items():
        export = EXPORTS[case]
        for name, color, _label in pieces:
            render_assembly(
                [(load_stl(export / f"{name}.stl"), color, name)],
                export / f"render_{name}.png",
            )
        render_assembly(
            [(load_stl(export / f"{name}.stl"), color, label) for name, color, label in pieces],
            export / assembly_names[case],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())