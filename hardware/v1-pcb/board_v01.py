"""Caseback V0.1 board: one source of truth for the outline, the parts, the nets and the fit checks.

    python3 board_v01.py              prints the checks and the stack
    python3 board_v01.py --draw DIR   also writes the SVG drawings into DIR

Standard library only. The Blender model (hardware/mechanical/scripts/generate_disc.py) imports this file, so the board
in the drawings and in the 3D renders is the same one. The positions of the parts come from the real KiCad board
(kicad/placement_v01.json, see apply_kicad_placement).

Frame: millimetres, disc centre at (0, 0), seen from the watch side (+Z, towards the caseback), x to the right, y up.
The keying notch is on -Y, the two charge contacts on the left and right of the optics. Z = 0 is the skin face.

Disc 25 mm across and 3.1 mm thick with the pad, no screws (D53, 2026-10-28). The optics sit in the middle of the skin face.
The BLE module is 8 x 8 mm and cannot share the middle with the 7.5 x 3.9 mm optical module inside a 21 mm circle, so the
optics are 0.6 mm above the centre and the module is below them, antenna towards the rim. The cell does not fit over the
board in 3.1 mm: it lies beside it, in the cap of the disc that the board leaves free (the board is cut along a chord).

Charging is through the SKIN face (D52, 2026-10-28): the watch lies dial up on the charger with the disc still stuck behind
its caseback, so the two charge contacts are flush metal slugs in the shell floor, pressed from inside by two SMD spring
contacts soldered on B.Cu pads. The earlier version had them on the watch side behind two holes in the lid, which needed
the disc to come off the watch every time. No magnet and no keeper plate: a magnet under a mechanical watch magnetises it.

This is a PLACEMENT, not a routed board: tracks, planes and Gerber files come from the PCB tool. Package sizes are
the ones in the datasheets read for this plan (SFH 7072, MAX86141) or typical sizes (the rest, marked "typ").
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import dataclass, field, replace

# ------------------------------------------------------------------ stack (z in mm, 0 = skin face)
H = 3.00                      # lid face; the pad stands PAD_PROUD above it, so the disc is 3.1 mm thick in all (D53)
FLOOR = 0.40                  # skin-side floor of the shell
PCB_T = 0.60                  # JLCPCB does not offer 0.4 mm in 4 layers (checked 2026-10-28); the extra 0.2 mm comes out of the watch-side headroom
PCB_Z0 = 1.45                 # board underside: the tallest skin-side part (ISP1807, 1.0) plus a 0.05 gap sits under it
PCB_Z1 = PCB_Z0 + PCB_T       # 2.05
LID_IN = 2.20                 # underside of the lid, top of the shell rim
PAD_T = 0.30                  # depth of the pad recess in the lid
PAD_PROUD = 0.10              # the pad is bought 0.4 mm thick: it stands this far above the lid face, touches the caseback first and
                              # the strap squeezes it flush. A flush pad is not pressed at all and only a perfectly flat back seals
PAD_FOAM_T = PAD_T + PAD_PROUD
ROOF = H - PAD_T - LID_IN     # lid material under the pad recess: 0.50. The board is 0.15 mm below it, so a load on the pad bends the
                              # roof at most that far before the board holds it up
ROOF_MIN = 0.5
GAP = 0.05
CELL_T = 1.50
CELL_Z0 = 0.50
FOAM_T = 0.15
SKIN_MAX_H = PCB_Z0 - FLOOR - GAP        # tallest skin-side part: 1.00
WATCH_MAX_H = LID_IN - PCB_Z1 - GAP      # tallest watch-side part: 0.10

R_DISC = 12.5                 # 25 mm across
R_CAV = 11.7                  # inside radius of the shell wall: 0.8 mm of wall
R_BOARD = 11.2                # the snap skirt of the lid is 0.1 mm outside it (inside radius 11.3)
R_PART = 10.7                 # parts stay inside this radius; the shell ledges that carry the board edge start at 10.85
R_RECESS = 8.5                # microsuction recess, Ø17. A curved caseback leaves a gap r^2 / 2R under the pad edge: 0.14 mm at R 55
CHORD_Y = 3.2                 # the board is cut away for y >= CHORD_Y: the cell lies there
_XC = math.sqrt(R_BOARD ** 2 - CHORD_Y ** 2)
CELL_CUT = (-_XC, CHORD_Y, _XC)           # the ends of the chord on the board edge (kept as x0, y0, x1 for the older callers)

# cell: custom pouch cell in the cap of the disc, 1.5 mm thick, flat side towards the board. Corners at r <= 11.2 so that the
# snap skirt of the lid (inside radius 11.3) clears it. No part number: nothing in a catalogue has this shape (see the cell notes)
CELL_POLY = ((-10.0, 3.6), (10.0, 3.6), (9.2, 6.0), (7.2, 8.3), (3.8, 10.2), (-3.8, 10.2), (-7.2, 8.3), (-9.2, 6.0))
CELL_MAH_PER_MM3 = 0.054      # 200 Wh/L of the whole cell (seals, tabs and protection board included) at 3.7 V: what small pouch cells reach

CONTACTS = ((-9.0, -1.0), (9.0, -1.0))     # charge contacts on the SKIN face (D52), beside the module and the optics
CONTACT_SLUG_D = 2.2          # 316L rivet-shaped slug through the shell floor, flush on the skin face; the board pad under it is 1.6
SLUG_HEAD_D = 3.0             # its head sits inside the cavity, so the spring cannot push it out through the floor
SLUG_HEAD_T = 0.10
CONTACT_FREE_H = 1.25         # spring contact before it is pressed; it works compressed to the part height below
NOTCH_W = 3.0                 # key notch in the outer wall at -Y, for the key of the charger


@dataclass
class Part:
    ref: str
    name: str
    side: str                 # "skin" (hangs under the board) or "watch" (stands on it)
    x: float
    y: float
    w: float                  # size along x at rot 0
    l: float                  # size along y at rot 0
    h: float
    rot: int = 0
    kind: str = "ic"
    mpn: str = ""
    note: str = ""

    def rect(self, pad: float = 0.0):
        w, l = (self.l, self.w) if self.rot % 180 else (self.w, self.l)
        return (self.x - w / 2 - pad, self.y - l / 2 - pad, self.x + w / 2 + pad, self.y + l / 2 + pad)


# ------------------------------------------------------------------ the ICs (positions chosen below, then checked)
SFH_APERTURES = ((-2.8, 0.0, 1.5, 3.0), (0.0, 0.0, 2.7, 3.0), (2.8, 0.0, 1.5, 3.0))   # (cx, cy, w, h) from the SFH centre
# die layout inside the SFH 7072 compartments is approximate (datasheet drawing, page 19-20)
SFH_DICE = (("green", -2.85, 0.75, 0.45), ("pd1", -2.8, -0.35, 0.89), ("pd2", 0.0, 0.0, 1.29),
            ("green", 2.9, 0.85, 0.4), ("red", 2.9, 0.3, 0.4), ("ir", 2.9, -0.45, 0.4))

PARTS: list[Part] = [
    # The optics are 0.6 mm above the centre: the module (8 x 8) has to go below them and both must fit in R_PART
    Part("U2", "SFH 7072 optical module (2 green, red, IR, 2 photodiodes)", "skin", 0.0, 0.6, 7.5, 3.9, 0.9, kind="optics",
         mpn="SFH 7072", note="12 pads 0.9 x 1.0 at 1.2 mm pitch; datasheet v1.6"),
    Part("U1", "MAX86141 optical front end, WLP-20 0.4 mm", "skin", 5.8, 0.9, 2.0, 1.8, 0.5, kind="ic", mpn="MAX86141ENP+T",
         note="20 balls in a 4 x 5 grid; size typ"),
    Part("U4", "TMP117 skin temperature", "skin", -5.4, 1.0, 2.0, 2.0, 0.8, kind="ic", mpn="TMP117MAIDRVR"),
    Part("U3", "BMI270 accelerometer + gyroscope", "skin", -6.2, -3.0, 2.5, 3.0, 0.83, kind="ic", mpn="BMI270"),
    Part("U5", "ISP1807 BLE module (nRF52840, antenna on the -Y edge)", "skin", 0.0, -5.7, 8.0, 8.0, 1.0, kind="module",
         mpn="ISP1807-LR-RS", note="antenna side assumed, verify in the module datasheet"),
    Part("U6", "BQ25101 charger, DSBGA-6", "skin", 7.0, -3.5, 1.4, 0.9, 0.5, kind="ic", mpn="BQ25101YFPR", note="size typ"),
    Part("U7", "1.8 V LDO (placeholder, not fitted if the module supplies 1.8 V)", "skin", 6.2, -5.6, 0.9, 0.9, 0.5,
         kind="ic", mpn="TBD", note="MAX86141 needs 1.8 V on VDD_ANA and VDD_DIG"),
    Part("Q1", "Reverse-polarity P-FET on the charge input, SOT-523", "skin", 8.0, -4.9, 1.6, 0.8, 0.7, kind="ic", mpn="TBD"),
    Part("CS1", "SMD spring contact under the charge slug", "skin", CONTACTS[0][0], CONTACTS[0][1], 2.0, 2.0, 0.95, kind="contact",
         mpn="TBD", note="height is the compressed one (0.95); free about 1.25; soft, about 30 gf; chosen at the next board revision"),
    Part("CS2", "SMD spring contact under the charge slug", "skin", CONTACTS[1][0], CONTACTS[1][1], 2.0, 2.0, 1.0, kind="contact",
         mpn="TBD", note="as CS1"),
]

# passives are placed next to what they serve: (ref, value, package, near, side, what)
PASSIVES = [
    ("C1", "0.1 uF", "0402", "U1", "skin", "VDD_ANA"), ("C2", "10 uF", "0402", "U1", "skin", "VDD_ANA"),
    ("C3", "1 uF", "0402", "U1", "skin", "VREF"), ("C4", "0.1 uF", "0402", "U1", "skin", "VDD_DIG"),
    ("C5", "10 uF", "0402", "U1", "skin", "VLED"), ("C6", "0.1 uF", "0402", "U1", "skin", "VLED"),
    ("R5", "100 k", "0402", "U1", "skin", "INT pull-up"),
    ("R1", "3.3", "0402", "U2", "skin", "ballast, green 1"), ("R2", "3.3", "0402", "U2", "skin", "ballast, green 2"),
    ("C7", "0.1 uF", "0402", "U4", "skin", "TMP117 supply"), ("R3", "4.7 k", "0402", "U4", "skin", "I2C pull-up"),
    ("R4", "4.7 k", "0402", "U4", "skin", "I2C pull-up"),
    ("C8", "0.1 uF", "0402", "U3", "skin", "BMI270 VDD"), ("C9", "0.1 uF", "0402", "U3", "skin", "BMI270 VDDIO"),
    ("C10", "1 uF", "0402", "U6", "skin", "charger in"), ("C11", "2.2 uF", "0402", "U6", "skin", "charger out"),
    ("R6", "ISET", "0402", "U6", "skin", "charge current"),
    ("C12", "1 uF", "0402", "U7", "skin", "LDO in"), ("C13", "1 uF", "0402", "U7", "skin", "LDO out"),
    ("C14", "4.7 uF", "0402", "U5", "skin", "VCC_nRF, 1.8 V"), ("C15", "0.1 uF", "0402", "U5", "skin", "VCC_nRF"),
    ("R8", "1 M", "0402", "U5", "skin", "battery divider"), ("R9", "750 k", "0402", "U5", "skin", "battery divider"),
    ("D1", "ESD", "0201", "Q1", "skin", "charge input"),
]
PASSIVE_SIZE = {"0402": (1.0, 0.5, 0.5), "0201": (0.6, 0.3, 0.3)}

# pads, no body: (ref, side, shape, x, y, w, h, function)
PADS = [
    ("CP1", "skin", "round", CONTACTS[0][0], CONTACTS[0][1], 1.6, 1.6, "charge input, one contact (skin face)"),
    ("CP2", "skin", "round", CONTACTS[1][0], CONTACTS[1][1], 1.6, 1.6, "charge input, other contact (skin face)"),
    ("BT1", "watch", "rect", -8.0, 2.3, 1.4, 1.0, "cell tab, polarity to confirm on the cell"),
    ("BT2", "watch", "rect", 8.0, 2.3, 1.4, 1.0, "cell tab, polarity to confirm on the cell"),
] + [(f"SWD{i + 1}", "watch", "round", -1.905 + 1.27 * i, -3.0, 0.8, 0.8, f)
     for i, f in enumerate(("V18", "SWDIO", "SWDCLK", "GND"))]

KEEPOUTS = {
    # (x0, y0, x1, y1): no parts and no copper on any layer, every side, except the module's own pads. The antenna end of the
    # module (the 3.65 mm of it nearest the rim, its datasheet 4.3) and the strip out to the board edge, 1.5 mm wider than the
    # module on each side: 11 mm across, where its datasheet draws 18 (13 in the 32 mm disc). Whether the antenna works so close
    # to the rim and to a steel caseback is not known (D53, to measure).
    "antenna": (-5.5, -11.5, 5.5, -6.05),
}

# ------------------------------------------------------------------ nets (what connects to what)
# pins from the SFH 7072 datasheet v1.6 and the MAX86140/MAX86141 datasheet pin table; "fn:" means assigned in the schematic
NETS = {
    "VBAT": ["cell +", "U6 OUT", "U1 A1 VLED", "U2 5 (green 1 anode)", "U2 11 (green 2 anode)", "U2 7 (red anode)",
             "U2 4 (IR anode)", "U7 IN", "divider R8/R9"],
    "V18": ["U7 OUT", "U5 VCC_nRF (pad 26)", "U1 D2 VDD_ANA", "U1 C2 VDD_DIG", "U3 VDD, VDDIO", "U4 V+", "R3, R4, R5"],
    "GND": ["U1 C3 GND_DIG", "U1 C4 GND_ANA", "U1 D3 PGND", "all ground pins"],
    "LED1_DRV": ["U1 D1", "R1 -> U2 6 (green 1 cathode)", "R2 -> U2 12 (green 2 cathode)"],
    "LED2_DRV": ["U1 C1", "U2 8 (red cathode)"],
    "LED3_DRV": ["U1 B1", "U2 9 (IR cathode)"],
    "PD1_IN": ["U1 D5", "U2 1 (photodiode 1 cathode)"],
    "PD2_IN": ["U1 D4", "U2 3 (photodiode 2 cathode)"],
    "PD_GND": ["U1 C5", "U2 2 (photodiode 1 anode)", "U2 10 (photodiode 2 anode)"],
    "VREF": ["U1 B5", "C3 to GND_ANA"],
    "SPI": ["U5 fn:SCK -> U1 A2 SCLK", "U5 fn:MOSI -> U1 A4 SDI", "U1 A3 SDO -> U5 fn:MISO", "U5 fn:CS -> U1 A5 CSB"],
    "INT_AFE": ["U1 B2 INT (open drain, active low)", "R5 to V18", "U5 fn:GPIO"],
    "I2C": ["U5 fn:SCL, fn:SDA", "U3 SCL, SDA", "U4 SCL, SDA", "R3, R4 to V18"],
    "INT_IMU": ["U3 INT1", "U5 fn:GPIO"],
    "VIN_CHG": ["CP1 / CP2", "D1 ESD", "Q1", "U6 IN"],
    "CHG": ["U6 CHG (open drain)", "U5 fn:GPIO"],
    "SWD": ["SWD1..4 (V18, SWDIO, SWDCLK, GND)", "U5 SWDIO (pad 28), SWDCLK (pad 30)"],
    "ANT": ["U5 OUT_ANT (pad 20) to OUT_MOD (pad 22)"],
}


# ------------------------------------------------------------------ geometry helpers
def board_polygon(n: int = 360):
    """Board outline: circle of R_BOARD, cut along the chord y = CHORD_Y (the top is the cell's)."""
    x0, y0, x1 = CELL_CUT
    a_hi = math.atan2(y0, x1)
    start, end = a_hi, math.pi - a_hi
    pts = []
    sweep = 2 * math.pi - (end - start)
    steps = int(n * sweep / (2 * math.pi))
    for i in range(steps + 1):
        a = start - sweep * i / steps
        pts.append((R_BOARD * math.cos(a), R_BOARD * math.sin(a)))
    return pts                                                    # the last point is (x0, y0): the polygon closes along the chord


def inside_board(x: float, y: float, r: float = R_PART) -> bool:
    if y > CHORD_Y - 0.25:
        return False
    return math.hypot(x, y) <= r


def rect_ok(rc, r: float = R_PART) -> bool:
    xa, ya, xb, yb = rc
    return all(inside_board(x, y, r) for x, y in ((xa, ya), (xa, yb), (xb, ya), (xb, yb)))


BODY_GAP = 0.1                # least gap between the bodies of two parts, for assembly (the check is two margins of 0.05)


def body_gap(a, b) -> float:
    ra, rb = a.rect(), b.rect()
    dx = max(rb[0] - ra[2], ra[0] - rb[2], 0.0)
    dy = max(rb[1] - ra[3], ra[1] - rb[3], 0.0)
    return math.hypot(dx, dy)


def overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def place_passives(parts: list[Part]) -> list[Part]:
    """Put every passive in the first free spot around the part it serves, nearest first."""
    out = list(parts)
    by_ref = {p.ref: p for p in out}
    for ref, value, pkg, near, side, what in PASSIVES:
        w, l, h = PASSIVE_SIZE[pkg]
        base = by_ref[near].rect()
        done = False
        for d in (0.25, 0.4, 0.6, 0.85, 1.1, 1.4):
            cands = []
            # positions all around the neighbour, both orientations
            for rot in (0, 90):
                pw, pl = (l, w) if rot else (w, l)
                xs = [base[0] - d - pw / 2, base[2] + d + pw / 2]
                ys = [base[1] - d - pl / 2, base[3] + d + pl / 2]
                span_x = [base[0] + pw / 2 + k * 0.6 for k in range(int((base[2] - base[0]) / 0.6) + 1)]
                span_y = [base[1] + pl / 2 + k * 0.6 for k in range(int((base[3] - base[1]) / 0.6) + 1)]
                cands += [(x, y, rot) for x in xs for y in span_y]
                cands += [(x, y, rot) for y in ys for x in span_x]
            for x, y, rot in cands:
                p = Part(ref, f"{value} {what}", side, x, y, w, l, h, rot=rot, kind="passive", mpn=f"{value} {pkg}")
                rc = p.rect()
                if not rect_ok(rc) or any(overlap(rc, k[:4]) for k in KEEPOUTS.values()):
                    continue
                if any(q.side == side and overlap(rc, q.rect(0.12)) for q in out):
                    continue
                out.append(p)
                by_ref[ref] = p
                done = True
                break
            if done:
                break
        if not done:
            raise RuntimeError(f"no room for {ref} near {near}")
    return out


PLACEMENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kicad", "placement_v01.json")


def apply_kicad_placement(parts: list[Part], path: str = PLACEMENT) -> list[Part]:
    """Take the position, the turn and the body size of every part from the KiCad board, which is the real one.

    The floorplan above is where the KiCad builder starts. It then moves the ICs a little (build_v01_pcb.py, MOVABLE) and
    puts each passive where it likes, so the two differ. `kicad/placement_v01.json` is written from the board by
    `kicad/tools/dump_footprints.py`; run that again after any change to the board. The centre of a part is the centre of
    its pads, and its long side runs along the longer span of its pads. Sizes come from the footprint name (L and W in it)
    when it has them."""
    if not os.path.exists(path):
        return parts
    fps = {f["ref"]: f for f in json.load(open(path))}
    out = []
    for p in parts:
        f = fps.get(p.ref)
        if f is None or p.kind == "contact" or not f["pads"]:
            out.append(p)
            continue
        xs = [q["x"] for q in f["pads"]]
        ys = [q["y"] for q in f["pads"]]
        w, l = p.w, p.l
        m = re.search(r"_L([\d.]+)-W([\d.]+)", f["name"])
        if m and p.kind != "passive":
            w, l = float(m.group(1)), float(m.group(2))
        long_side, short_side = max(w, l), min(w, l)
        along_x = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        w, l = (long_side, short_side) if along_x else (short_side, long_side)
        out.append(replace(p, x=(min(xs) + max(xs)) / 2, y=(min(ys) + max(ys)) / 2, w=w, l=l, rot=0))
    return out


ALL_PARTS = apply_kicad_placement(place_passives(PARTS))


# ------------------------------------------------------------------ checks
def checks():
    rows = []

    def add(name, ok, detail):
        rows.append((name, bool(ok), detail))

    for p in ALL_PARTS:
        rc = p.rect()
        lim = R_BOARD - 0.3 if p.kind == "contact" else R_PART   # the spring contacts sit near the edge, under the charge slugs
        add(f"{p.ref} inside the board", rect_ok(rc, lim), f"corner radius {max(math.hypot(x, y) for x, y in ((rc[0], rc[1]), (rc[0], rc[3]), (rc[2], rc[1]), (rc[2], rc[3]))):.2f} mm (limit {lim})")
    for side in ("skin", "watch"):
        ps = [p for p in ALL_PARTS if p.side == side]
        bad = [(a.ref, b.ref, round(body_gap(a, b), 3)) for i, a in enumerate(ps) for b in ps[i + 1:] if overlap(a.rect(0.05), b.rect(0.05))]
        add(f"parts {BODY_GAP} mm apart on the {side} side", not bad,
            f"{len(ps)} parts" + (f", closer than that (ref, ref, gap in mm): {bad}" if bad else ""))
    tall = max((p for p in ALL_PARTS if p.side == "skin"), key=lambda p: p.h)
    add("skin-side height", tall.h <= SKIN_MAX_H + 1e-9, f"tallest {tall.ref} {tall.h:.2f} of {SKIN_MAX_H:.2f} mm")
    add("watch-side height", all(p.h <= WATCH_MAX_H + 1e-9 for p in ALL_PARTS if p.side == "watch"), f"limit {WATCH_MAX_H:.2f} mm")
    for k, rc in KEEPOUTS.items():
        inside = [p.ref for p in ALL_PARTS if p.ref != "U5" and overlap(p.rect(), rc)]
        add(f"{k} keep-out is empty", not inside, f"{inside}" if inside else "no part inside")
    for ref, side, shape, x, y, w, h, fn in PADS:
        add(f"pad {ref} on the board", rect_ok((x - w / 2, y - h / 2, x + w / 2, y + h / 2), R_BOARD - 0.3), fn)
    for x, y in CONTACTS:
        r = math.hypot(x, y)
        add("charge slug inside the shell floor", r + CONTACT_SLUG_D / 2 <= R_CAV - 0.5, f"slug edge at {r + CONTACT_SLUG_D / 2:.2f} mm from the centre, cavity {R_CAV}")
    add("charge contacts as far apart as the charger pins", abs(CONTACTS[0][0] - CONTACTS[1][0]) >= 12.0, f"{abs(CONTACTS[0][0] - CONTACTS[1][0]):.1f} mm")
    add("optics in the middle of the skin face", math.hypot(next(p for p in ALL_PARTS if p.ref == "U2").x, next(p for p in ALL_PARTS if p.ref == "U2").y) <= 1.0,
        f"SFH 7072 centre {math.hypot(next(p for p in ALL_PARTS if p.ref == 'U2').x, next(p for p in ALL_PARTS if p.ref == 'U2').y):.2f} mm from the disc centre")
    cr = max(math.hypot(x, y) for x, y in CELL_POLY)
    add("cell inside the snap skirt", cr <= 11.3 - 0.25 + 1e-9, f"cell corner at {cr:.2f} mm, cavity {R_CAV}, snap skirt at 11.3")
    add("cell clear of the board", min(y for _, y in CELL_POLY) >= CHORD_Y + 0.3 - 1e-9, f"0.3 mm from the chord, which is at y = {CHORD_Y}")
    add("cell fits under the lid", CELL_Z0 + CELL_T + FOAM_T + GAP <= LID_IN + 1e-9, f"cell top {CELL_Z0 + CELL_T:.2f}, foam top {CELL_Z0 + CELL_T + FOAM_T:.2f}, lid {LID_IN}")
    add("lid roof under the pad", ROOF >= ROOF_MIN - 1e-9, f"{ROOF:.2f} mm (0.6 before D53; the board is {LID_IN - PCB_Z1:.2f} mm below it as a stop)")
    add("total thickness", H + PAD_PROUD <= 3.1 + 1e-9, f"{H + PAD_PROUD:.2f} mm with the pad")
    add("diameter", 2 * R_DISC <= 25.0 + 1e-9, f"{2 * R_DISC:.1f} mm")
    add("wall", R_DISC - R_CAV >= 0.8 - 1e-9, f"{R_DISC - R_CAV:.2f} mm")
    add("pad stands proud of the lid face", PAD_FOAM_T - PAD_T >= 0.1 - 1e-9, f"{PAD_FOAM_T - PAD_T:.2f} mm")
    add("lettering ring on the lid", R_DISC - R_RECESS >= 3.5, f"{R_DISC - R_RECESS:.1f} mm between the pad and the rim")
    mah = cell_mah()
    add("cell capacity", mah >= 7.0, f"about {mah:.1f} mAh from the outline {poly_area(CELL_POLY):.0f} mm2 x {CELL_T} mm (estimate at 200 Wh/L)")
    add("skin floor", FLOOR >= 0.4, f"{FLOOR} mm (the SLS rule of 0.6 mm is not met, open since D2)")
    return rows


def poly_area(pts) -> float:
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))) / 2


def cell_mah() -> float:
    return poly_area(CELL_POLY) * CELL_T * CELL_MAH_PER_MM3


def area():
    seg_d = CHORD_Y
    seg = R_BOARD ** 2 * math.acos(seg_d / R_BOARD) - seg_d * math.sqrt(R_BOARD ** 2 - seg_d ** 2)
    board = math.pi * R_BOARD ** 2 - seg
    used = sum(p.w * p.l for p in ALL_PARTS if p.side == "skin")
    return board, used


# ------------------------------------------------------------------ drawings
def _svg_header(w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="Helvetica, Arial, sans-serif">\n<rect width="{w}" height="{h}" fill="#f4f2ec"/>\n')


def draw_board(side: str, scale: float = 34.0) -> str:
    """Placement drawing of one face. The skin view is mirrored left-right, as you see it looking at the skin face."""
    W, Hh = 1000, 1080
    cx, cy = 500.0, 570.0
    sx = -1.0 if side == "skin" else 1.0

    def X(x):
        return cx + sx * x * scale

    def Y(y):
        return cy - y * scale

    def rectp(rc, **kw):
        xa, ya, xb, yb = rc
        x0, x1 = sorted((X(xa), X(xb)))
        y0, y1 = sorted((Y(ya), Y(yb)))
        attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
        return f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" height="{y1 - y0:.1f}" {attrs}/>\n'

    title = "Watch side (what the lid covers)" if side == "watch" else "Skin side (what the shell floor covers)"
    s = _svg_header(W, Hh)
    s += f'<text x="40" y="52" font-size="26" font-weight="bold" fill="#1b1b1b">Caseback V0.1 board, {title}</text>\n'
    s += f'<text x="40" y="80" font-size="15" fill="#555">Placement, not routed. Millimetres. Board diameter {2 * R_BOARD:.1f}, disc {2 * R_DISC:g}, thickness {H + PAD_PROUD:.1f}.</text>\n'

    # disc, cavity
    s += f'<circle cx="{cx}" cy="{cy}" r="{R_DISC * scale}" fill="none" stroke="#9a968c" stroke-width="1.5"/>\n'
    s += f'<circle cx="{cx}" cy="{cy}" r="{R_CAV * scale}" fill="none" stroke="#9a968c" stroke-width="1" stroke-dasharray="6 5"/>\n'
    s += f'<circle cx="{cx}" cy="{cy}" r="{R_RECESS * scale}" fill="none" stroke="#b9b5a8" stroke-width="1" stroke-dasharray="2 4"/>\n'
    if side == "watch":
        s += f'<text x="{cx}" y="{cy + R_RECESS * scale - 6}" font-size="12" fill="#a29e92" text-anchor="middle">microsuction pad, diameter {2 * R_RECESS:g}</text>\n'

    # board
    pts = board_polygon()
    d = "M" + " L".join(f"{X(x):.1f} {Y(y):.1f}" for x, y in pts) + " Z"
    s += f'<path d="{d}" fill="#1f3b34" stroke="#0e1f1b" stroke-width="2"/>\n'

    # cell (outline only, it is not on the board)
    cd = "M" + " L".join(f"{X(x):.1f} {Y(y):.1f}" for x, y in CELL_POLY) + " Z"
    s += f'<path d="{cd}" fill="#d9d6cc" stroke="#6c685d" stroke-width="1.5" stroke-linejoin="round"/>\n'
    ccx, ccy = 0.0, sum(y for _, y in CELL_POLY) / len(CELL_POLY)
    s += f'<text x="{X(ccx)}" y="{Y(ccy) - 6}" font-size="15" fill="#4a463d" text-anchor="middle">custom pouch cell with protection circuit</text>\n'
    s += f'<text x="{X(ccx)}" y="{Y(ccy) + 14}" font-size="13" fill="#6c685d" text-anchor="middle">1.5 mm thick, about {cell_mah():.0f} mAh (estimate), lies beside the board</text>\n'

    # antenna keep-out
    ax0, ay0, ax1, ay1 = KEEPOUTS["antenna"]
    s += f'<clipPath id="board-clip"><path d="{d}"/></clipPath>\n'
    s += '<g clip-path="url(#board-clip)">' + rectp((ax0, ay0, ax1, ay1), fill="#c4523b", fill_opacity="0.34", stroke="#e07a62", stroke_width="1.5", stroke_dasharray="5 4") + '</g>\n'
    s += f'<text x="{X(0)}" y="{Y(-8.0)}" font-size="13" fill="#f2c7bd" text-anchor="middle">antenna keep-out</text>\n'

    def draw_part(p: Part, faint=False):
        rc = p.rect()
        if faint:
            return rectp(rc, fill="none", stroke="#7d9a92", stroke_width="1", stroke_dasharray="3 3")
        fill = {"optics": "#2b2b2f", "module": "#20324a", "ic": "#2d2d31", "passive": "#7a5c34", "contact": "#8a6a2c"}[p.kind]
        out = rectp(rc, fill=fill, stroke="#cfcabd" if p.kind != "passive" else "#d8b57a", stroke_width="1")
        return out

    for p in ALL_PARTS:
        if p.side != side:
            s += draw_part(p, faint=True)
    for p in ALL_PARTS:
        if p.side == side:
            s += draw_part(p)

    # SFH detail on the skin side: compartments and dice
    sfh = next(p for p in ALL_PARTS if p.ref == "U2")
    if side == "skin":
        for (ax, ay, aw, ah) in SFH_APERTURES:
            s += rectp((sfh.x + ax - aw / 2, sfh.y + ay - ah / 2, sfh.x + ax + aw / 2, sfh.y + ay + ah / 2),
                       fill="#3a2a2a", stroke="#6b5959", stroke_width="1")
        colors = {"green": "#3DDC84", "red": "#FF4D3D", "ir": "#c9a0ff", "pd1": "#7fb0ff", "pd2": "#7fb0ff"}
        for kind, dx, dy, size in SFH_DICE:
            r = size / 2 * scale
            if kind.startswith("pd"):
                s += rectp((sfh.x + dx - size / 2, sfh.y + dy - (size * (2.69 / 1.29) / 2 if kind == "pd2" else size / 2), sfh.x + dx + size / 2,
                            sfh.y + dy + (size * (2.69 / 1.29) / 2 if kind == "pd2" else size / 2)), fill="none", stroke=colors[kind], stroke_width="1.2", stroke_dasharray="3 2")
            else:
                s += f'<circle cx="{X(sfh.x + dx):.1f}" cy="{Y(sfh.y + dy):.1f}" r="{r:.1f}" fill="{colors[kind]}"/>\n'

    # pads
    for ref, pside, shape, x, y, w, h, fn in PADS:
        if pside != side:
            continue
        if shape == "round":
            s += f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{w / 2 * scale:.1f}" fill="#e3b04b" stroke="#fff3cf" stroke-width="1"/>\n'
        else:
            s += rectp((x - w / 2, y - h / 2, x + w / 2, y + h / 2), fill="#e3b04b", stroke="#fff3cf", stroke_width="1")

    for ref, pside, shape, x, y, w, h, fn in PADS:
        if pside == side and ref.startswith("CP"):
            s += f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{CONTACT_SLUG_D / 2 * scale:.1f}" fill="none" stroke="#e3b04b" stroke-width="1.2" stroke-dasharray="4 3"/>\n'
            out = 1 if X(x) > cx else -1
            s += f'<text x="{X(x) + out * 62:.1f}" y="{Y(y) + 5:.1f}" font-size="13" fill="#b4852a" text-anchor="{"start" if out > 0 else "end"}">{ref}</text>\n'
    # labels for the main parts
    for p in ALL_PARTS:
        if p.side == side and p.kind != "passive":
            rc = p.rect()
            tx, ty = X((rc[0] + rc[2]) / 2), Y((rc[1] + rc[3]) / 2)
            big = (rc[2] - rc[0]) > 3.5
            if big:
                s += f'<text x="{tx:.1f}" y="{ty + (30 if p.ref == "U2" else 5):.1f}" font-size="15" font-weight="bold" fill="#f1efe8" text-anchor="middle">{p.ref} {p.mpn if p.ref in ("U2", "U5") else ""}</text>\n'
            else:
                s += f'<text x="{tx:.1f}" y="{Y(rc[3]) - 6:.1f}" font-size="12" font-weight="bold" fill="#f1efe8" text-anchor="middle">{p.ref}</text>\n'
    # scale bar and orientation
    s += f'<line x1="40" y1="{Hh - 60}" x2="{40 + 5 * scale}" y2="{Hh - 60}" stroke="#333" stroke-width="3"/>\n'
    s += f'<text x="40" y="{Hh - 40}" font-size="14" fill="#333">5 mm</text>\n'
    s += f'<text x="{cx}" y="{Hh - 30}" font-size="14" fill="#333" text-anchor="middle">keying notch in the rim at the bottom of the drawing; charge contacts at the left and right</text>\n'
    key = [("U1", "MAX86141"), ("U2", "SFH 7072"), ("U3", "BMI270"), ("U4", "TMP117"), ("U5", "ISP1807"), ("U6", "BQ25101"), ("U7", "1.8 V LDO"), ("Q1", "reverse FET")]
    for i, (r, n) in enumerate(key):
        s += f'<text x="{W - 40}" y="{120 + i * 20}" font-size="14" fill="#333" text-anchor="end">{r}  {n}</text>\n'
    s += "</svg>\n"
    return s


def draw_stack(scale: float = 150.0) -> str:
    """Section through the optics and through the cell, one beside the other, with every z value."""
    W, Hh = 1000, 700
    z0y = 610.0

    def Z(z):
        return z0y - z * scale

    s = _svg_header(W, Hh)
    s += '<text x="40" y="50" font-size="26" font-weight="bold" fill="#1b1b1b">Caseback V0.1 stack, 3.1 mm with the pad</text>\n'
    s += '<text x="40" y="76" font-size="15" fill="#555">Heights in millimetres from the skin face. Three columns: through the optics, through the cell and through a charge contact.</text>\n'

    def block(x, w, za, zb, fill, label=None, tc="#fff", fs=14):
        out = f'<rect x="{x}" y="{Z(zb):.1f}" width="{w}" height="{(zb - za) * scale:.1f}" fill="{fill}" stroke="#222" stroke-width="0.8"/>\n'
        if label:
            out += f'<text x="{x + w / 2}" y="{Z((za + zb) / 2) + 5:.1f}" font-size="{fs}" fill="{tc}" text-anchor="middle">{label}</text>\n'
        return out

    colx = [(110, 250, "Through the optics"), (400, 250, "Through the cell"), (690, 250, "Through a charge contact")]
    for x, w, name in colx:
        s += f'<text x="{x + w / 2}" y="108" font-size="17" font-weight="bold" fill="#333" text-anchor="middle">{name}</text>\n'
    # optics column
    x, w = colx[0][0], colx[0][1]
    s += block(x, w, 0, 0.5, "#6b4a4a", "window (clear resin)", fs=13)
    s += block(x, w, 0.5 + 0.05, PCB_Z0, "#2b2b2f", "SFH 7072 (0.9)", fs=13)
    s += block(x, w, PCB_Z0, PCB_Z1, "#1f3b34", f"board {PCB_Z1 - PCB_Z0:.1f}", fs=13)
    s += block(x, w, PCB_Z1, LID_IN, "#f4f2ec", f"free (watch-side parts up to {WATCH_MAX_H:.2f})", tc="#777", fs=12)
    s += block(x, w, LID_IN, LID_IN + ROOF, "#444a55", f"lid roof {ROOF:.1f}", fs=13)
    s += block(x, w, LID_IN + ROOF, H + PAD_PROUD, "#b8bcc4", f"pad {PAD_FOAM_T:.1f}, {PAD_PROUD:.1f} proud", tc="#222", fs=13)
    # cell column
    x, w = colx[1][0], colx[1][1]
    s += block(x, w, 0, FLOOR, "#444a55", "shell floor 0.4", fs=13)
    s += block(x, w, CELL_Z0, CELL_Z0 + CELL_T, "#a9aeb6", "cell 1.5", tc="#222", fs=13)
    s += block(x, w, CELL_Z0 + CELL_T, CELL_Z0 + CELL_T + FOAM_T, "#222", None)
    s += block(x, w, LID_IN, LID_IN + ROOF, "#444a55", f"lid roof {ROOF:.1f}", fs=13)
    s += block(x, w, LID_IN + ROOF, H + PAD_PROUD, "#b8bcc4", f"pad {PAD_FOAM_T:.1f}, {PAD_PROUD:.1f} proud", tc="#222", fs=13)
    # charge contact column: slug through the floor, spring contact under the board, nothing on the watch side
    x, w = colx[2][0], colx[2][1]
    s += block(x, w, 0, FLOOR, "#9aa0a8", "316L slug", tc="#222", fs=13)
    s += block(x, w, FLOOR, FLOOR + SLUG_HEAD_T, "#7f858d", None)
    s += block(x, w, FLOOR + SLUG_HEAD_T, PCB_Z0, "#8a6a2c", "spring contact (0.95 pressed)", fs=12)
    s += block(x, w, PCB_Z0, PCB_Z1, "#1f3b34", f"board {PCB_Z1 - PCB_Z0:.1f}, pad on B.Cu", fs=13)
    s += block(x, w, PCB_Z1, LID_IN, "#f4f2ec", "free", tc="#777", fs=12)
    s += block(x, w, LID_IN, LID_IN + ROOF, "#444a55", f"lid roof {ROOF:.1f}", fs=13)
    s += block(x, w, LID_IN + ROOF, H + PAD_PROUD, "#b8bcc4", f"pad {PAD_FOAM_T:.1f}, {PAD_PROUD:.1f} proud", tc="#222", fs=13)
    for z, label in ((0, "0  skin"), (FLOOR, "0.40  floor"), (PCB_Z0, "1.45  board"), (PCB_Z1, f"{PCB_Z1:.2f}"), (LID_IN, "2.20  lid"), (H, "3.00  lid face"), (H + PAD_PROUD, "3.10  pad")):
        s += f'<line x1="90" y1="{Z(z):.1f}" x2="930" y2="{Z(z):.1f}" stroke="#bbb" stroke-width="0.6" stroke-dasharray="2 4"/>\n'
        s += f'<text x="84" y="{Z(z) + 4:.1f}" font-size="12" fill="#444" text-anchor="end">{label}</text>\n'
    s += "</svg>\n"
    return s


def export_json(path):
    data = {
        "stack": {"H": H, "FLOOR": FLOOR, "PCB_Z0": PCB_Z0, "PCB_Z1": PCB_Z1, "LID_IN": LID_IN, "PAD_T": PAD_T, "PAD_PROUD": PAD_PROUD},
        "parts": [p.__dict__ for p in ALL_PARTS],
        "pads": PADS,
        "nets": NETS,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=1)


def main(argv):
    rows = checks()
    width = max(len(r[0]) for r in rows)
    for name, ok, detail in rows:
        print(f"{'ok  ' if ok else 'FAIL'} {name:<{width}}  {detail}")
    board, used = area()
    print(f"\nboard area {board:.0f} mm2, skin-side parts cover {used:.0f} mm2 ({100 * used / board:.0f} %), {len(ALL_PARTS)} parts, "
          f"{len([p for p in ALL_PARTS if p.kind == 'passive'])} passives")
    print(f"stack: floor {FLOOR}, board {PCB_Z0}..{PCB_Z1}, lid {LID_IN}, roof {ROOF:.2f}, thickness {H}")
    if "--draw" in argv:
        out = argv[argv.index("--draw") + 1]
        os.makedirs(out, exist_ok=True)
        for side in ("watch", "skin"):
            with open(os.path.join(out, f"board_v01_{side}.svg"), "w") as f:
                f.write(draw_board(side))
        with open(os.path.join(out, "stack_v01.svg"), "w") as f:
            f.write(draw_stack())
        print("drawings written to", out)
    return 0 if all(ok for _, ok, _ in rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
