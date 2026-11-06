"""Desk mounts - scripted CAD for two public design cases.

1. **Laptop cradle** (`laptop-cradle/`, 4 printable pieces: left/right rails and
   left/right back halves): under-desk slide-in holder; the laptop rests on two
   30 mm edge arms; adjustable slide-in clearance; 3 mm front retention lip;
   #6-class screws across wide top flanges.
2. **Under-desk shelf** (`underdesk-shelf/`, 2 mirror halves, centre half-lap):
   printable pieces; organic cable/vent openings; corner gussets so geometry
   (not just material) carries sustained load.

Runs headless on FreeCAD's bundled Python (no GUI, no kept document state):

  "C:\\Program Files\\FreeCAD 1.1\\bin\\python.exe" designs/desk-mounts/desk_mounts.py

Each case exports into `<case>/export/`: `<piece>.step` / `<piece>.stl` for every
printable piece, plus `manifest.json` with the resolved parameters and per-piece
dimensions.

Coordinate conventions (assembled frame, mm):
  X = across the desk (cradle: left/right; shelf: width)
  Y = depth (front = +Y, back = -Y)
  Z = up; **desk underside = z 0**; everything hangs in negative Z.
"""

from __future__ import annotations

import json
from pathlib import Path

import FreeCAD as App
import Part
import Mesh

V = App.Vector
HERE = Path(__file__).resolve().parent

CASES = {
    "laptop-cradle": (
        "cradle_rail_left",
        "cradle_rail_right",
        "cradle_back_left",
        "cradle_back_right",
    ),
    "underdesk-shelf": ("shelf_left", "shelf_right"),
}
CASE_PREFIX = {"laptop-cradle": "CRADLE_", "underdesk-shelf": "SHELF_"}
SHARED_PARAMS = {"LAP", "SCREW_R", "RIB_T"}

# ---------------------------------------------------------------------------
# Parameters (mm). Brief ranges in comments where the brief constrains them.
# ---------------------------------------------------------------------------
PARAMS = {
    # Cradle
    "CRADLE_INNER_W": 360.0,   # slot width for the laptop; measure the real laptop
    "CRADLE_LEN": 180.0,       # rail length (front-back); laptop overhangs (fine, stiff)
    "CRADLE_SLOT": 53.0,       # desk underside -> floor top. Laptop is 23.2 mm
                               # closed and a 15-30 mm item may slide on top of
                               # it -> 53 mm. Laptop-only build = 32.
    "CRADLE_FLOOR_T": 5.0,
    "CRADLE_ARM": 30.0,        # floor arm width (edge contact strip)
    "CRADLE_WALL_T": 4.0,
    "CRADLE_FLANGE_W": 18.0,   # outboard screw flange width
    "CRADLE_FLANGE_T": 6.0,
    "CRADLE_LIP": 3.0,         # front retention lip (brief: assumed 3 mm)
    "CRADLE_BACK_LEDGE": 30.0, # rear support ledge depth (30 mm; was a 3 mm nub)
    "CRADLE_BACK_T": 5.0,
    # Shelf
    "SHELF_W": 360.0,          # brief: 200-400
    "SHELF_D": 180.0,          # brief: 120-200
    "SHELF_FLOOR_T": 6.0,
    "SHELF_WALL_T": 5.0,
    "SHELF_WALL_TOP": 25.0,    # below-desk extension (brief: 20-30): desk -> wall band
    "SHELF_WALL_H": 55.0,      # wall band under the extension (brief walls 40-85)
    "SHELF_FLANGE_W": 18.0,
    "SHELF_FLANGE_T": 6.0,
    "SHELF_LIP_H": 15.0,
    "SHELF_LIP_T": 5.0,
    "SHELF_MAG_X": (40.0, 110.0),  # front-lip magnet pocket centres (per half)
    "SHELF_MAG_R": 3.15,       # Ø6.3 pocket for Ø6 x 3 mm disc magnets
    "SHELF_MAG_D": 3.2,
    "SHELF_CORNER_R": 8.0,     # outer vertical corner fillet (styling)
    "SHELF_INNER_R": 4.0,      # inner wall corner fillet (styling)
    # Shared
    "LAP": 15.0,               # half-lap length at the centre joint
    "SCREW_R": 2.1,            # Ø4.2 clearance for #6-class / M4
    "RIB_T": 3.0,
}


def box(x0: float, y0: float, z0: float, dx: float, dy: float, dz: float) -> Part.Shape:
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


def port(length: float, height: float, depth: float) -> Part.Shape:
    """Rounded-slot (stadium) cutter: `length` along X, `height` along Z,
    extruded along Y. `length == height` degenerates to a circle."""
    core_len = max(length - height, 0.0)
    pieces = [box(-core_len / 2, -depth / 2, -height / 2, core_len, depth, height)] if core_len else []
    for cx in (-core_len / 2, core_len / 2):
        pieces.append(Part.makeCylinder(height / 2, depth, V(cx, -depth / 2, 0), V(0, 1, 0)))
    out = pieces[0]
    for p in pieces[1:]:
        out = out.fuse(p)
    return out


def port_x(length: float, height: float, depth: float, x: float, y: float, z: float) -> Part.Shape:
    """Stadium cutter for X-normal walls: `length` along Y, `height` along Z."""
    return port(length, height, depth).rotate(V(0, 0, 0), V(0, 0, 1), 90).translate(V(x, y, z))


def screw_z(x: float, y: float, z0: float, depth: float) -> Part.Shape:
    return Part.makeCylinder(PARAMS["SCREW_R"], depth, V(x, y, z0), V(0, 0, 1))


def tri_yz(y0: float, z0: float, dy: float, dz: float, x0: float, t: float) -> Part.Shape:
    """Right-triangle gusset in the Y-Z plane at x0, extruded +X by t.
    Points: (y0,z0) -> (y0+dy,z0) -> (y0,z0+dz)."""
    w = Part.makePolygon([V(x0, y0, z0), V(x0, y0 + dy, z0), V(x0, y0, z0 + dz), V(x0, y0, z0)])
    return Part.Face(w).extrude(V(t, 0, 0))


def tri_xz(x0: float, z0: float, dx: float, dz: float, y0: float, t: float) -> Part.Shape:
    """Right-triangle gusset in the X-Z plane at y0, extruded +Y by t.
    Points: (x0,z0) -> (x0+dx,z0) -> (x0,z0+dz)."""
    w = Part.makePolygon([V(x0, y0, z0), V(x0 + dx, y0, z0), V(x0, y0, z0 + dz), V(x0, y0, z0)])
    return Part.Face(w).extrude(V(0, t, 0))


def round_outer_corner(
    shape: Part.Shape,
    x0: float, x1: float, y0: float, y1: float,
    ccx: float, ccy: float, r: float,
    z0: float, z1: float,
) -> Part.Shape:
    """Round an outer corner by cutting the wedge between the corner and a
    quarter circle of radius r centred at (ccx, ccy). The rectangle
    (x0..x1, y0..y1) must cover the corner region plus a little margin."""
    region = box(x0, y0, z0 - 1.0, x1 - x0, y1 - y0, (z1 - z0) + 2.0)
    disc = Part.makeCylinder(r, (z1 - z0) + 2.0, V(ccx, ccy, z0 - 1.0), V(0, 0, 1))
    return shape.cut(region.cut(disc))


def round_inner_corner(
    shape: Part.Shape,
    x0: float, y0: float, r: float,
    ccx: float, ccy: float,
    z0: float, z1: float,
) -> Part.Shape:
    """Round an inner (concave) corner by fusing the square minus the quarter
    circle of radius r centred at (ccx, ccy); (x0, y0) is the square's corner
    sitting in the void."""
    square = box(x0, y0, z0, r, r, z1 - z0)
    disc = Part.makeCylinder(r, (z1 - z0) + 2.0, V(ccx, ccy, z0 - 1.0), V(0, 0, 1))
    return shape.fuse(square.cut(disc))


# ---------------------------------------------------------------------------
# Laptop cradle
# ---------------------------------------------------------------------------

def cradle_rail(side: str) -> Part.Shape:
    """'right' (+X) or 'left'. Outboard wall, inboard floor arm, top flange."""
    p = PARAMS
    hw = p["CRADLE_INNER_W"] / 2
    wt = p["CRADLE_WALL_T"]
    fw, ft = p["CRADLE_FLANGE_W"], p["CRADLE_FLANGE_T"]
    arm, ln = p["CRADLE_ARM"], p["CRADLE_LEN"]
    zt = -p["CRADLE_SLOT"]                 # floor top
    zb = zt - p["CRADLE_FLOOR_T"]          # floor bottom
    zw = -ft                               # wall top = flange bottom
    wt_x0, wt_x1 = hw, hw + wt             # wall
    fl_x0, fl_x1 = wt_x0, wt_x1 + fw       # flange (overlaps the wall top for a solid fuse)

    shape = box(wt_x0 - arm, -ln / 2, zb, arm, ln, p["CRADLE_FLOOR_T"])     # floor arm
    shape = shape.fuse(box(wt_x0, -ln / 2, zb, wt, ln, zw - zb))           # outboard wall
    shape = shape.fuse(box(fl_x0, -ln / 2, zw, fw + wt, ln, ft))           # top flange
    lip = p["CRADLE_LIP"]
    shape = shape.fuse(box(wt_x0 - arm, ln / 2 - lip, zt, arm, lip, lip))  # front retention lip

    for yy in (-45.0, 0.0, 45.0):  # arm->wall gussets
        shape = shape.fuse(tri_xz(wt_x0 - 15.0, zt, 15.0, 15.0, yy - p["RIB_T"] / 2, p["RIB_T"]))
    for yy in (-65.0, -25.0, 25.0, 65.0):  # flange screw holes
        shape = shape.cut(screw_z((fl_x0 + fl_x1) / 2, yy, zw - 1.0, ft + 2.0))
    return shape if side == "right" else shape.mirror(V(0, 0, 0), V(1, 0, 0))


def cradle_back(side: str) -> Part.Shape:
    """Back stop plate (abuts the rail ends at y=-L/2) + outboard top flange +
    a 3 mm rear retention lip on the plate face (matches the rail front lips).
    Two printable halves; half-lap at the centre; each half screwed to the
    desk independently."""
    p = PARAMS
    hw = p["CRADLE_INNER_W"] / 2
    wt = p["CRADLE_WALL_T"]
    bt = p["CRADLE_BACK_T"]
    fw, ft = p["CRADLE_FLANGE_W"], p["CRADLE_FLANGE_T"]
    zb = -(p["CRADLE_SLOT"] + p["CRADLE_FLOOR_T"])
    zw = -ft
    outer = hw + wt                          # rail wall outer face
    y_in = -p["CRADLE_LEN"] / 2              # front face (abuts rail ends)
    y_out = y_in - bt                        # plate back face
    y_mid = (y_in + y_out) / 2
    fl_mid = (y_out - fw + y_in) / 2         # flange split mid
    f_mid = y_out - fw / 2                   # flange screw hole centre (free strip)
    lap = p["LAP"]

    dx = outer + lap if side == "left" else outer
    x0 = -outer if side == "left" else 0.0
    shape = box(x0, y_out, zb, dx, bt, zw - zb)                     # plate
    shape = shape.fuse(box(x0, y_out - fw, zw, dx, fw + bt, ft))   # outboard flange (overlaps plate top)
    lip = p["CRADLE_LIP"]
    ledge = p["CRADLE_BACK_LEDGE"]
    zt = -p["CRADLE_SLOT"]
    ledge_mid = y_in + ledge / 2
    # rear support ledge: 30 mm deep, top flush with the rail arms, so the
    # laptop's back edge rests on it (the plate remains the travel stop)
    shape = shape.fuse(box(x0, y_in, zt - p["CRADLE_FLOOR_T"], dx, ledge, p["CRADLE_FLOOR_T"]))

    # Half-lap over x in [0, lap]: left keeps the outboard slabs, right the
    # inboard ones (complementary cuts).
    if side == "left":
        shape = shape.cut(box(0.0, y_mid, zb - 1.0, lap, (y_in - y_mid) + 0.5, zw - zb + 1.0))
        shape = shape.cut(box(0.0, fl_mid, zw - 0.5, lap, (y_in - fl_mid) + 0.5, ft + 1.0))
        shape = shape.cut(box(0.0, ledge_mid, zt - p["CRADLE_FLOOR_T"] - 0.5, lap, (y_in + ledge - ledge_mid) + 0.5, p["CRADLE_FLOOR_T"] + 1.0))
    else:
        shape = shape.cut(box(0.0, y_out - 0.5, zb - 1.0, lap, (y_mid - y_out) + 0.5, zw - zb + 1.0))
        shape = shape.cut(box(0.0, y_out - fw - 0.5, zw - 0.5, lap, (fl_mid - (y_out - fw)) + 0.5, ft + 1.0))
        shape = shape.cut(box(0.0, y_in - 0.5, zt - p["CRADLE_FLOOR_T"] - 0.5, lap, (ledge_mid - y_in) + 0.5, p["CRADLE_FLOOR_T"] + 1.0))

    for xx in (-45.0, -140.0) if side == "left" else (45.0, 140.0):  # flange screw holes (2 per half)
        shape = shape.cut(screw_z(xx, f_mid, zw - 1.0, ft + 2.0))
    return shape


# ---------------------------------------------------------------------------
# Under-desk shelf
# ---------------------------------------------------------------------------

def shelf_half(side: str) -> Part.Shape:
    p = PARAMS
    hw, hd = p["SHELF_W"] / 2, p["SHELF_D"] / 2
    f_t, wt = p["SHELF_FLOOR_T"], p["SHELF_WALL_T"]
    zfb = -(p["SHELF_WALL_TOP"] + p["SHELF_WALL_H"] + f_t)   # floor bottom
    zft = zfb + f_t                                          # floor top
    zw = -p["SHELF_FLANGE_T"]                                # wall/band top
    zfl = -p["SHELF_FLANGE_T"]                               # flange bottom
    fw = p["SHELF_FLANGE_W"]
    lip_h, lip_t = p["SHELF_LIP_H"], p["SHELF_LIP_T"]
    lap = p["LAP"]
    x0 = -hw if side == "left" else 0.0                      # body origin
    dx = hw + lap if side == "left" else hw                  # body length (left laps past centre)
    sx = -hw if side == "left" else hw - wt                  # outer side wall
    fl_mid = -hd - (fw + wt) / 2                             # back flange split mid

    # floor + back wall/band + outboard back flange + outer side wall/band + side flange + front lip
    shape = box(x0, -hd, zfb, dx, 2 * hd, f_t)
    shape = shape.fuse(box(x0, -hd, zft, dx, wt, zw - zft))
    shape = shape.fuse(box(x0, -hd - fw, zfl, dx, fw + wt, p["SHELF_FLANGE_T"]))
    shape = shape.fuse(box(sx, -hd, zft, wt, 2 * hd, zw - zft))
    fl_x = sx - fw if side == "left" else sx
    shape = shape.fuse(box(fl_x, -hd, zfl, fw + wt, 2 * hd, p["SHELF_FLANGE_T"]))
    shape = shape.fuse(box(x0, hd - lip_t, zft, dx, lip_t, lip_h))

    # gussets: back wall x2 (clear of ports/vents), outer side wall x1, front lip x2 (clear of notches)
    for xx, lx in ((20.0, 30.0), (165.0, 160.0)):
        xg = -xx if side == "left" else xx
        xl = -lx if side == "left" else lx
        shape = shape.fuse(tri_yz(-hd + wt, zft, 35.0, 30.0, xg - wt / 2, wt))
        shape = shape.fuse(tri_yz(hd - lip_t, zft, -20.0, 12.0, xl - p["RIB_T"] / 2, p["RIB_T"]))
    if side == "left":
        shape = shape.fuse(tri_xz(sx + wt, zft, 30.0, 30.0, 68.5, p["RIB_T"]))
    else:
        shape = shape.fuse(tri_xz(sx, zft, -30.0, 30.0, 68.5, p["RIB_T"]))

    # organic openings ------------------------------------------------------
    xb = -90.0 if side == "left" else 90.0                   # back wall port centre
    shape = shape.cut(port(90.0, 30.0, wt + 6.0).translate(V(xb, -hd + wt / 2, zft + 27.5)))
    for xx in (150.0, 34.0):
        shape = shape.cut(port(14.0, 14.0, wt + 6.0).translate(V((-xx if side == "left" else xx), -hd + wt / 2, zft + 14.0)))
    for xx in (30.0, 92.0, 154.0):                           # band slots
        shape = shape.cut(port(36.0, 12.0, wt + 6.0).translate(V((-xx if side == "left" else xx), -hd + wt / 2, zw - 9.5)))
    shape = shape.cut(port_x(60.0, 26.0, wt + 6.0, sx + wt / 2, 20.0, zft + 27.5))       # side wall port
    shape = shape.cut(port_x(14.0, 14.0, wt + 6.0, sx + wt / 2, -55.0, zft + 14.0))      # side wall vent
    for yy in (-50.0, 50.0):                                                 # side band slots
        shape = shape.cut(port_x(36.0, 12.0, wt + 6.0, sx + wt / 2, yy, zw - 9.5))
    for xx in (55.0, 135.0):                                                 # front lip notches
        xg = -xx if side == "left" else xx
        shape = shape.cut(Part.makeCylinder(9.0, lip_t + 4.0, V(xg, hd - lip_t - 2.0, zft + lip_h), V(0, 1, 0)))

    # flange screw holes (back 2 + side 2 per half)
    for xx in (45.0, 135.0):
        shape = shape.cut(screw_z(-xx if side == "left" else xx, -hd - fw / 2, zfl - 1.0, p["SHELF_FLANGE_T"] + 2.0))
    hole_x = sx - fw / 2 if side == "left" else sx + wt + fw / 2
    for yy in (-35.0, 35.0):
        shape = shape.cut(screw_z(hole_x, yy, zfl - 1.0, p["SHELF_FLANGE_T"] + 2.0))

    # magnet pockets in the front lip: Ø6.3 x 3.2 recesses for Ø6 x 3 mm
    # disc magnets (superglue / JB Weld), flush with the lip face
    for xx in p["SHELF_MAG_X"]:
        xg = -xx if side == "left" else xx
        shape = shape.cut(
            Part.makeCylinder(
                p["SHELF_MAG_R"], p["SHELF_MAG_D"] + 1.0,
                V(xg, hd - p["SHELF_MAG_D"], zft + lip_h / 2), V(0, 1, 0),
            )
        )

    # centre half-lap over x in [0, lap] -----------------------------------
    # left keeps lower/outer slabs; right keeps upper/inner slabs.
    if side == "left":
        shape = shape.cut(box(0.0, -hd - 1.0, zfb + f_t / 2, lap, 2 * hd + 2.0, f_t / 2 + 0.5))    # floor
        shape = shape.cut(box(0.0, -hd + wt / 2, zft - 0.5, lap, wt / 2 + 0.5, zw - zft + 1.0))    # back wall+band
        shape = shape.cut(box(0.0, fl_mid, zfl - 0.5, lap, (fw + wt) / 2 + 0.5, p["SHELF_FLANGE_T"] + 1.0))  # back flange
        shape = shape.cut(box(0.0, hd - lip_t / 2, zft - 0.5, lap, lip_t / 2 + 0.5, lip_h + 1.0))   # front lip
    else:
        shape = shape.cut(box(0.0, -hd - 1.0, zfb - 0.5, lap, 2 * hd + 2.0, f_t / 2 + 0.5))         # floor
        shape = shape.cut(box(0.0, -hd - 0.5, zft - 0.5, lap, wt / 2 + 0.5, zw - zft + 1.0))       # back wall+band
        shape = shape.cut(box(0.0, -hd - fw - 0.5, zfl - 0.5, lap, (fl_mid - (-hd - fw)) + 0.5, p["SHELF_FLANGE_T"] + 1.0))  # back flange
        shape = shape.cut(box(0.0, hd - lip_t - 0.5, zft - 0.5, lap, lip_t / 2 + 0.5, lip_h + 1.0))  # front lip

    # styling: soften the outer and inner vertical wall corners (boolean
    # rounding, robust in OCC where edge fillets are not)
    cr, ir = p["SHELF_CORNER_R"], p["SHELF_INNER_R"]
    if side == "left":
        shape = round_outer_corner(shape, -hw - 1.0, -hw + cr, -hd - 1.0, -hd + cr, -hw + cr, -hd + cr, cr, zfb, zw)
        shape = round_outer_corner(shape, -hw - 1.0, -hw + cr, hd - cr, hd + 1.0, -hw + cr, hd - cr, cr, zfb, zw)
        shape = round_inner_corner(shape, -hw + wt, -hd + wt, ir, -hw + wt + ir, -hd + wt + ir, zft, zw)
        shape = round_inner_corner(shape, -hw + wt, hd - lip_t - ir, ir, -hw + wt + ir, hd - lip_t - ir, zft, zw)
    else:
        shape = round_outer_corner(shape, hw - cr, hw + 1.0, -hd - 1.0, -hd + cr, hw - cr, -hd + cr, cr, zfb, zw)
        shape = round_outer_corner(shape, hw - cr, hw + 1.0, hd - cr, hd + 1.0, hw - cr, hd - cr, cr, zfb, zw)
        shape = round_inner_corner(shape, hw - wt - ir, -hd + wt, ir, hw - wt - ir, -hd + wt + ir, zft, zw)
        shape = round_inner_corner(shape, hw - wt - ir, hd - lip_t - ir, ir, hw - wt - ir, hd - lip_t - ir, zft, zw)
    return shape


# ---------------------------------------------------------------------------
# Build + export
# ---------------------------------------------------------------------------

def _case_pieces(case: str) -> dict[str, Part.Shape]:
    if case == "laptop-cradle":
        return {
            "cradle_rail_left": cradle_rail("left"),
            "cradle_rail_right": cradle_rail("right"),
            "cradle_back_left": cradle_back("left"),
            "cradle_back_right": cradle_back("right"),
        }
    if case == "underdesk-shelf":
        return {"shelf_left": shelf_half("left"), "shelf_right": shelf_half("right")}
    raise SystemExit(f"unknown case: {case}")


def build_case(case: str) -> dict:
    pieces = _case_pieces(case)
    export = HERE / case / "export"
    export.mkdir(parents=True, exist_ok=True)
    doc = App.newDocument(case)
    prefix = CASE_PREFIX[case]
    params = {
        key: value
        for key, value in PARAMS.items()
        if key.startswith(prefix) or key in SHARED_PARAMS
    }
    manifest: dict = {"params": params, "pieces": {}}
    for name, shape in pieces.items():
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
        doc.recompute()
        bb = shape.BoundBox
        info = {
            "valid": shape.isValid(),
            "solids": len(shape.Solids),
            "volume_mm3": round(shape.Volume, 1),
            "bbox": [round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)],
            "bbox_min": [round(bb.XMin, 1), round(bb.YMin, 1), round(bb.ZMin, 1)],
        }
        if not info["valid"] or info["solids"] != 1:
            raise SystemExit(f"{name}: invalid shape ({info})")
        Part.export([obj], str(export / f"{name}.step"))
        Mesh.export([obj], str(export / f"{name}.stl"))
        info["step"] = f"{name}.step"
        info["stl"] = f"{name}.stl"
        manifest["pieces"][name] = info
    (export / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def build_all() -> dict[str, dict]:
    return {case: build_case(case) for case in CASES}


if __name__ == "__main__":
    for case, manifest in build_all().items():
        for name, info in manifest["pieces"].items():
            print(
                f"{case}/{name:20s} vol={info['volume_mm3']:>9.1f} mm^3  "
                f"bbox={info['bbox']}  solids={info['solids']}"
            )
        print(f"wrote {len(manifest['pieces'])} STEP + STL pairs -> {HERE / case / 'export'}")