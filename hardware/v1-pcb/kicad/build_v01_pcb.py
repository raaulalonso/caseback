"""Place the Caseback V0.1 parts in KiCad from netlist_v01.py and the outline of ../board_v01.py.

Run it with the Python that ships with KiCad (it has pcbnew):

    $KICAD/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 build_v01_pcb.py [--out DIR]

It writes caseback_v01.kicad_pcb (placed, with vias in the pads, not routed) and caseback_v01.kicad_pro (rules).
Frame: the disc frame of board_v01.py (millimetres, y up, seen from the watch side) becomes KiCad's (y down) here, so
the watch side is the front copper (F.Cu) and the skin side is the back copper (B.Cu); every IC is on B.Cu.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
import board_v01 as B  # noqa: E402
import netlist_v01 as N  # noqa: E402

LCSC = os.path.join(HERE, "lib", "lcsc.pretty")
SYMBOLS = os.path.join(HERE, "lib", "lcsc_symbols")
KICAD_FP = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
OUT = HERE
if "--out" in sys.argv:
    OUT = sys.argv[sys.argv.index("--out") + 1]

TRACK = 0.1                  # JLCPCB 4-layer minimum is 3.5 mil; 0.1 keeps some margin
CLEAR = 0.1
VIA = (0.15, 0.25)           # drill, diameter: the smallest through via JLCPCB lists for 4 layers; used inside pads
VIA_ROUTE = (0.15, 0.30)     # vias the router and the ground fan-out place; their holes stay at least 0.25 mm apart
EDGE_CLEAR = 0.25
ROUTE_CLEAR = 0.125          # gap kept free round a pad when the escape stubs and vias in pads are placed (route_v01.py itself works at CLEAR)
CLEAR_SENSITIVE = 0.15       # clearance of the photodiode inputs
PART_GAP = 0.15              # copper to copper between different parts, for assembly

board = pcbnew.BOARD()
nets: dict[str, pcbnew.NETINFO_ITEM] = {}
fps: dict[str, pcbnew.FOOTPRINT] = {}
u5_pins: dict[str, str] = {}      # signal net -> U5 pad number


def P(x, y):
    """Disc frame (y up) to KiCad (y down)."""
    return VECTOR2I(FromMM(x), FromMM(-y))


def mm(v):
    return FromMM(v)


def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    return nets[name]


def symbol_pins(code):
    """Pin number -> pin name, read from the LCSC symbol of a part."""
    s = open(os.path.join(SYMBOLS, code + ".kicad_sym")).read()
    out = {}
    for m in re.finditer(r'\(pin \w+ \w+\s+\(at [-\d.]+ [-\d.]+ [-\d.]+\)\s+\(length [-\d.]+\)\s+\(name "([^"]*)".*?\(number "([^"]*)"', s, re.S):
        out[m.group(2)] = m.group(1)
    return out


# ------------------------------------------------------------------ footprints
def new_fp(name, ref, value, side):
    if ":" in name:
        lib, n = name.split(":")
        fp = pcbnew.FootprintLoad(os.path.join(KICAD_FP, lib + ".pretty"), n)
    else:
        fp = pcbnew.FootprintLoad(LCSC, name)
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    board.Add(fp)              # flipping needs the board to look the layers up
    if side == "B":
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    return fp


def put(fp, x, y, rot):
    fp.SetPosition(P(x, y))
    fp.SetOrientationDegrees(rot)


def pad_xy(fp, number):
    p = fp.FindPadByNumber(number)
    return None if p is None else (ToMM(p.GetPosition().x), -ToMM(p.GetPosition().y))


def pad_boxes(fp, grow=0.0):
    """Rectangle of every pad in the disc frame, grown by `grow`."""
    out = []
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        out.append((ToMM(bb.GetLeft()) - grow, -ToMM(bb.GetBottom()) - grow, ToMM(bb.GetRight()) + grow, -ToMM(bb.GetTop()) + grow))
    return out


NATIVE: dict[str, tuple[float, float]] = {}      # body size of each IC along x and y of its footprint at rotation 0


def set_native(ref, fp):
    """Orient board_v01's body size to the footprint: its long side lies along the long side of the pad box."""
    part = next(p for p in B.ALL_PARTS if p.ref == ref)
    x0, y0, x1, y1 = pad_extent(fp)
    w, l = part.w, part.l
    if (x1 - x0 >= y1 - y0) != (w >= l):
        w, l = l, w
    NATIVE[ref] = (max(w, x1 - x0), max(l, y1 - y0))


def pad_boxes_net(fp):
    return [(b, p.GetNetname()) for b, p in zip(pad_boxes(fp), fp.Pads())]


def pad_extent(fp):
    boxes = pad_boxes(fp)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def body_box(ref, fp, grow=0.0):
    """Body of an IC as a box, turned with the footprint: nothing else sits under it."""
    turned = int(round(fp.GetOrientationDegrees())) % 180
    w, l = NATIVE[ref]
    if turned:
        w, l = l, w
    x, y = ToMM(fp.GetPosition().x), -ToMM(fp.GetPosition().y)
    return (x - w / 2 - grow, y - l / 2 - grow, x + w / 2 + grow, y + l / 2 + grow)


# ------------------------------------------------------------------ outline, holes, rule areas
def add_outline():
    """The circle of R_BOARD, closed by the chord y = CHORD_Y (the cell's side): one arc and one line."""
    R = B.R_BOARD
    x0, y0, x1 = B.CELL_CUT

    arc = pcbnew.PCB_SHAPE(board)
    arc.SetShape(pcbnew.SHAPE_T_ARC)
    arc.SetLayer(pcbnew.Edge_Cuts)
    arc.SetWidth(mm(0.1))
    arc.SetArcGeometry(P(x1, y0), P(0, -R), P(x0, y0))
    board.Add(arc)
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(mm(0.1))
    s.SetStart(P(x0, y0))
    s.SetEnd(P(x1, y0))
    board.Add(s)


def rule_area(name, rect=None, circle=None):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetZoneName(name)
    ol = z.Outline()
    ol.NewOutline()
    if rect:
        x0, y0, x1, y1 = rect
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    else:
        cx, cy, r = circle
        pts = [(cx + r * math.cos(2 * math.pi * k / 24), cy + r * math.sin(2 * math.pi * k / 24)) for k in range(24)]
    for x, y in pts:
        ol.Append(FromMM(x), FromMM(-y))
    board.Add(z)


def add_holes():
    """No screws since D53: the shell and the lid snap together, the board has no holes."""
    return


# ------------------------------------------------------------------ parts
def add_pads_not_parts():
    """CP1, CP2 (skin side, B.Cu) and the cell tabs and programming pads (watch side, F.Cu) as one-pad footprints. A skin-side
    one is drawn on F.Cu and flipped, as the ICs are: a pad that is only given the B.Cu layer on a footprint that is
    already on the back is read by the router (the Specctra export) as a pad on the front, and it routes over it."""
    for ref, (nname, shape, x, y, size) in N.PADS.items():
        fp = pcbnew.FOOTPRINT(board)
        # each pad gets a footprint name of its own: with no name, an exported board reads them all as one package
        kind = "SKIN_PAD" if ref in N.SKIN_PADS else "SWD_PAD" if ref.startswith("SWD") else "CELL_TAB"
        fp.SetFPID(pcbnew.LIB_ID("caseback", f"{kind}_{ref}"))
        fp.SetReference(ref)
        fp.SetValue(ref)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        skin = ref in N.SKIN_PADS
        pad = pcbnew.PAD(fp)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetNumber("1")
        if shape == "round":
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(VECTOR2I(mm(size), mm(size)))
        else:
            pad.SetShape(pcbnew.PAD_SHAPE_RECTANGLE)         # a plain rectangle: the router does not turn a rounded pad of a back footprint to the back
            pad.SetSize(VECTOR2I(mm(size[0]), mm(size[1])))
        ls = pcbnew.LSET()
        ls.AddLayer(pcbnew.F_Cu)
        ls.AddLayer(pcbnew.F_Mask)
        pad.SetLayerSet(ls)
        pad.SetNet(net(nname))
        fp.Add(pad)
        fp.SetPosition(P(x, y))
        board.Add(fp)
        if skin:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fps[ref] = fp


def add_ics():
    pos = {p.ref: p for p in B.ALL_PARTS}
    for ref, (value, lcsc, fpname, side) in N.PARTS.items():
        fp = new_fp(fpname, ref, value, side)
        put(fp, pos[ref].x, pos[ref].y, 0)
        fps[ref] = fp
        set_native(ref, fp)
    for ref, pins in N.PINS.items():
        for number, nname in pins.items():
            p = fps[ref].FindPadByNumber(number)
            if p is None:
                raise RuntimeError(f"{ref} has no pad {number}")
            p.SetNet(net(nname))
    u5 = fps["U5"]
    for number, nname in N.U5_FIXED.items():
        u5.FindPadByNumber(number).SetNet(net(nname))
    names = symbol_pins("C5264268")
    for pad in u5.Pads():
        if names.get(pad.GetNumber()) == "VSS":
            pad.SetNet(net("GND"))
    # the TMP117 exposed pad stays floating (datasheet) and gets no paste
    ep = fps["U4"].FindPadByNumber("7")
    ls = ep.GetLayerSet()
    for l in (pcbnew.F_Paste, pcbnew.B_Paste):
        ls.RemoveLayer(l)
    ep.SetLayerSet(ls)


def add_u5_links():
    """Neighbouring pads of the connector row that belong together: OUT_ANT to OUT_MOD, VBUS to a ground pad. Made after the
    module has its final turn, because a wire made before it would stay where the pads were."""
    u5 = fps["U5"]
    for na, nb in N.U5_LINKS:
        a, m = u5.FindPadByNumber(na), u5.FindPadByNumber(nb)
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(a.GetPosition())
        t.SetEnd(m.GetPosition())
        t.SetWidth(mm(0.3))
        t.SetLayer(pcbnew.B_Cu)
        t.SetNet(net(a.GetNetname() or m.GetNetname()))
        t.SetLocked(True)
        board.Add(t)


def net_pads():
    """Every net as a list of (ref, pad), the U5 signals included once they are assigned."""
    out = {n: list(p) for n, p in N.all_nets().items()}
    for sig, padno in u5_pins.items():
        out.setdefault(sig, []).append(("U5", padno))
    return out


def net_cost(ref, nets_with_ref):
    """Half-perimeter length of the nets that touch `ref` (its pads are read at the current position and turn)."""
    total = 0.0
    for pads in nets_with_ref:
        pts = [pad_xy(fps[r], p) for r, p in pads if r in fps]
        pts = [p for p in pts if p]
        if len(pts) > 1:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return total


def assign_u5_signals():
    """Give the ten signals GPIO pads on the connector edge: cheapest matching by distance, so wires do not cross much."""
    u5 = fps["U5"]
    names = symbol_pins("C5264268")
    cand = [str(n) for n in (32, 34, 36, 38, 40, 42, 44, 46, 48)] + ["6"]
    dest = {}
    for s in N.U5_SIGNALS:
        pts = [pad_xy(fps[ref], pad) for ref, pins in N.PINS.items() if ref != "U5" for pad, nname in pins.items() if nname == s]
        if s == "VBAT_SENSE":
            pts = [pad_xy(u5, "26")]
        dest[s] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    best = {0: (0.0, [])}
    for s in N.U5_SIGNALS:
        nxt = {}
        for mask, (c0, path) in best.items():
            for j, c in enumerate(cand):
                if mask >> j & 1:
                    continue
                if s in N.U5_NEEDS_AIN and "AIN" not in names.get(c, ""):
                    continue
                px, py = pad_xy(u5, c)
                c1 = c0 + abs(px - dest[s][0]) + abs(py - dest[s][1])
                m2 = mask | 1 << j
                if m2 not in nxt or c1 < nxt[m2][0]:
                    nxt[m2] = (c1, path + [c])
        best = nxt
    _, path = min(best.values(), key=lambda v: v[0])
    u5_pins.clear()
    u5_pins.update(zip(N.U5_SIGNALS, path))


def ic_fits(ref):
    """The IC, at its current turn, lies inside the board, outside the keep-outs and clear of every other IC."""
    fp = fps[ref]
    body = body_box(ref, fp)
    pads = pad_boxes(fp)
    if not B.rect_ok(body, B.R_PART + 0.2) or any(not B.rect_ok(b, B.R_PART + 0.2) for b in pads):
        return False
    if ref != "U5" and B.overlap(body, B.KEEPOUTS["antenna"]):
        return False
    for other in N.PARTS:
        if other == ref or other not in fps:
            continue
        ob = body_box(other, fps[other], PART_GAP)
        if B.overlap(body, ob) or any(B.overlap(b, ob) for b in pads):
            return False
    return True


MOVABLE = {"U1": 1.5, "U3": 1.5, "U4": 1.5, "U6": 2.0, "U7": 2.0, "Q1": 2.0, "D1": 2.5}     # how far each IC may move from board_v01


def settle_ics():
    """Turn each IC to the quarter turn, and nudge it, so that the wires between ICs get short. U2 (optics) and U5 (module,
    antenna side to -y, the rim) keep their place."""
    u5 = fps["U5"]
    best = None
    for a in (0, 90, 180, 270):
        u5.SetOrientationDegrees(a)
        nc = [pad_xy(u5, str(n)) for n in range(65, 79)]
        cy = sum(p[1] for p in nc) / len(nc) - (-ToMM(u5.GetPosition().y))
        if best is None or cy < best[0]:
            best = (cy, a)
    u5.SetOrientationDegrees(best[1])
    assign_u5_signals()
    home = {r: (ToMM(fps[r].GetPosition().x), -ToMM(fps[r].GetPosition().y)) for r in N.PARTS}
    if "--jitter" in sys.argv:           # nudge U1 by a fraction of the search step, to get a different layout for the router
        jx, jy = (float(v) for v in sys.argv[sys.argv.index("--jitter") + 1].split(","))
        home["U1"] = (home["U1"][0] + jx, home["U1"][1] + jy)
    for r in ("U2",):
        fps[r].SetOrientationDegrees(0)
        if not ic_fits(r):
            fps[r].SetOrientationDegrees(180)
    for _ in range(3):
        nets = net_pads()
        for r in ("U1", "U3", "U4", "U6", "U7", "Q1", "D1"):
            mine = [pads for pads in nets.values() if any(x == r for x, _ in pads)]
            hx, hy = home[r]
            lim = MOVABLE[r]
            steps = [round(k * 0.25, 2) for k in range(-int(lim / 0.25), int(lim / 0.25) + 1)]
            best = None
            for a in (0, 90, 180, 270):
                fps[r].SetOrientationDegrees(a)
                for dx in steps:
                    for dy in steps:
                        if math.hypot(dx, dy) > lim:
                            continue
                        put(fps[r], hx + dx, hy + dy, a)
                        if not ic_fits(r):
                            continue
                        c = net_cost(r, mine) + 0.6 * math.hypot(dx, dy)
                        if best is None or c < best[0]:
                            best = (c, a, hx + dx, hy + dy)
            if best is None:
                raise RuntimeError(f"{r} fits nowhere within {lim} mm of its place")
            put(fps[r], best[2], best[3], best[1])
        assign_u5_signals()
    names = symbol_pins("C5264268")
    for r in ["U1", "U2", "U3", "U4", "U5", "U6", "U7", "Q1", "D1"]:
        x, y = ToMM(fps[r].GetPosition().x), -ToMM(fps[r].GetPosition().y)
        h = home.get(r, (x, y))
        print(f"  {r}: turn {fps[r].GetOrientationDegrees():.0f}, at ({x:.2f}, {y:.2f}), moved {math.hypot(x - h[0], y - h[1]):.2f} mm")
    for sig, c in sorted(u5_pins.items(), key=lambda kv: int(kv[1])):
        fps["U5"].FindPadByNumber(c).SetNet(net(sig))
        print(f"  U5 pad {c} ({names.get(c)}) <- {sig}")


# ------------------------------------------------------------------ passives
CORRIDOR = {"U1": 1.2, "U6": 1.0, "U4": 0.8, "U3": 0.8, "U7": 0.6, "U5": 0.7}     # length kept free in front of each connected pad


def corridors():
    """Boxes in front of the connected pads of the fine-pitch parts where no passive may stand, so wires can leave the pad."""
    out = []
    for ref, length in CORRIDOR.items():
        fp = fps[ref]
        ext = pad_extent(fp)
        cx, cy = (ext[0] + ext[2]) / 2, (ext[1] + ext[3]) / 2
        boxes = pad_boxes(fp)
        pads = list(fp.Pads())
        for pad, bb in zip(pads, boxes):
            if not pad.GetNetname() or ref == "U1" and pad.GetNumber() in ("B2", "B3", "B4", "C2", "C3", "C4"):
                continue
            x, y = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            dx, dy = x - cx, y - cy
            if abs(dx) >= abs(dy):
                sx = 1 if dx > 0 else -1
                box = (x, y - max(bb[3] - bb[1], 0.2) / 2, x + sx * length, y + max(bb[3] - bb[1], 0.2) / 2) if sx > 0 else \
                      (x - length, y - max(bb[3] - bb[1], 0.2) / 2, x, y + max(bb[3] - bb[1], 0.2) / 2)
            else:
                sy = 1 if dy > 0 else -1
                w = max(bb[2] - bb[0], 0.2) / 2
                box = (x - w, y, x + w, y + sy * length) if sy > 0 else (x - w, y - length, x + w, y)
            # a corridor that runs into another pad of the same part leads nowhere: the pad is an inner one
            if any(B.overlap(box, o) and o is not bb and o != bb for o in boxes if _shrink(o) and B.overlap(box, _shrink(o))):
                continue
            out.append((box, pad.GetNetname()))
    return out


def _shrink(b, d=0.02):
    return (b[0] + d, b[1] + d, b[2] - d, b[3] - d)


def place_passives():
    """Each passive goes to the free spot nearest the pad it serves, turned so that the right pad is the near one."""
    near = {ref: spec[3] for ref, spec in N.PASSIVES.items()}
    for ref in ("R8", "R9", "C16"):                 # the battery divider sits by the pad that carries the sense signal
        near[ref] = ("U5", u5_pins["VBAT_SENSE"])
    fixed = [(ref, pad_boxes(fp, PART_GAP)) for ref, fp in fps.items() if ref not in N.PASSIVES]
    bodies = {r: body_box(r, fps[r]) for r in N.PARTS}
    others = [B.KEEPOUTS["antenna"]]
    lanes = corridors()

    def clear(fp):
        pads = pad_boxes_net(fp)
        boxes = [b for b, _ in pads]
        if any(not B.rect_ok(b, B.R_PART) for b in boxes):
            return False
        if any(B.overlap(b, k) for b in boxes for k in others):
            return False
        if any(B.overlap(b, k) for b in boxes for k in bodies.values()):
            return False
        if any(B.overlap(b, lane) and n != lane_net for b, n in pads for lane, lane_net in lanes):
            return False
        return not any(B.overlap(x, y) for _, bs in fixed for x in boxes for y in bs)

    dist = {}
    order = sorted(N.PASSIVES, key=lambda r: ({"U1": 0, "U5": 1}.get(near[r][0], 2), r))     # the BGA first, then the module: both have few free sides
    for ref in order:
        value, na, nb, _, role = N.PASSIVES[ref]
        fp = new_fp("Capacitor_SMD:C_0402_1005Metric" if ref.startswith("C") else "Resistor_SMD:R_0402_1005Metric", ref, value, "B")
        fp.FindPadByNumber("1").SetNet(net(na))
        fp.FindPadByNumber("2").SetNet(net(nb))
        fps[ref] = fp
        tref, tpad = near[ref]
        tnet = fps[tref].FindPadByNumber(tpad).GetNetname()
        tgt = pad_xy(fps[tref], tpad)
        best = None
        for ring in range(115):
            d = 0.45 + 0.1 * ring
            for k in range(48):
                ang = 2 * math.pi * k / 48
                x, y = tgt[0] + d * math.cos(ang), tgt[1] + d * math.sin(ang)
                for rot in (0, 90, 180, 270):
                    put(fp, x, y, rot)
                    if not clear(fp):
                        continue
                    p1, p2 = pad_xy(fp, "1"), pad_xy(fp, "2")
                    near_pad, far_pad = (p1, p2) if tnet in (na, "") or tnet != nb else (p2, p1)
                    score = math.dist(near_pad, tgt) + 0.2 * math.dist(far_pad, tgt)
                    if best is None or score < best[0]:
                        best = (score, x, y, rot)
            if best is not None and ring > 2:
                break
        if best is None:                                  # the board is nearly full: look at every spot on a fine grid
            for gx in range(-110, 111, 2):
                for gy in range(-110, 30, 2):
                    for rot in (0, 90):
                        put(fp, gx / 10, gy / 10, rot)
                        if not clear(fp):
                            continue
                        p1, p2 = pad_xy(fp, "1"), pad_xy(fp, "2")
                        score = math.dist(((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2), tgt)
                        if best is None or score < best[0]:
                            best = (score, gx / 10, gy / 10, rot)
        if best is None:
            if "--partial" in sys.argv:                  # look at the layout when something does not fit: leave the part outside the board
                print(f"  NO ROOM for {ref} near {tref}.{tpad}")
                put(fp, 0.0, 14.0 + 1.5 * len(dist) % 9, 0)
                dist[ref] = 99.0
                continue
            raise RuntimeError(f"no room for {ref} near {tref}.{tpad}")
        put(fp, best[1], best[2], best[3])
        fixed.append((ref, pad_boxes(fp, PART_GAP)))
        dist[ref] = best[0]
    far = max(dist, key=dist.get)
    print(f"  {len(dist)} passives placed, farthest {far} at {dist[far]:.2f} mm, {len(lanes)} escape lanes kept free")


# ------------------------------------------------------------------ vias, zones, text
def via_at(x, y, nname, size=VIA):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(x, y))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetDrill(mm(size[0]))
    v.SetWidth(mm(size[1]))
    v.SetNet(net(nname))
    v.SetLocked(True)
    board.Add(v)


def add_vias_in_pads():
    """The six inner balls of the MAX86141 and the module's inner ground pads cannot be reached from the surface."""
    u1 = fps["U1"]
    for number in ("B2", "B3", "B4", "C2", "C3", "C4"):
        x, y = pad_xy(u1, number)
        via_at(x, y, u1.FindPadByNumber(number).GetNetname())
    u5 = fps["U5"]
    names = symbol_pins("C5264268")
    for pad in u5.Pads():
        if names.get(pad.GetNumber()) == "VSS" and ToMM(pad.GetSize().x) < 0.5:
            x, y = pad_xy(u5, pad.GetNumber())
            via_at(x, y, "GND")


def add_fanout_stubs(length=0.45):
    """A short locked wire out of every connected ball of the two 0.4 mm BGAs, straight away from the part, so that the
    router cannot close a ball in with the wires of its neighbours. It stops short of any other pad."""
    n = 0
    others = {r: pad_boxes_net(f) for r, f in fps.items()}
    for ref in ("U1", "U6"):
        fp = fps[ref]
        ext = pad_extent(fp)
        cx, cy = (ext[0] + ext[2]) / 2, (ext[1] + ext[3]) / 2
        boxes = pad_boxes(fp)
        for pad, bb in zip(fp.Pads(), boxes):
            if not pad.GetNetname() or ref == "U1" and pad.GetNumber() in ("B2", "B3", "B4", "C2", "C3", "C4"):
                continue
            x, y = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
            dx, dy = x - cx, y - cy
            ux, uy = (math.copysign(1, dx), 0) if abs(dx) >= abs(dy) else (0, math.copysign(1, dy))
            got = 0.0
            for k in range(1, int(length / 0.05) + 1):
                px, py = x + ux * 0.05 * k, y + uy * 0.05 * k
                tb = (px - 0.05, py - 0.05, px + 0.05, py + 0.05)
                if any(B.overlap(tb, (b[0] - ROUTE_CLEAR, b[1] - ROUTE_CLEAR, b[2] + ROUTE_CLEAR, b[3] + ROUTE_CLEAR))
                       for r, bs in others.items() for b, nn in bs if nn != pad.GetNetname()):
                    break
                got = 0.05 * k
            if got < 0.15:
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(x, y))
            t.SetEnd(P(x + ux * got, y + uy * got))
            t.SetWidth(mm(TRACK))
            t.SetLayer(pcbnew.B_Cu)
            t.SetNet(net(pad.GetNetname()))
            t.SetLocked(True)
            board.Add(t)
            n += 1
    print(f"  {n} fan-out stubs on the BGAs")


def add_ground_vias():
    """A via beside every ground pad of the passives and of the small ICs, joined by a short track, so that the ground
    plane on In1 is reached without the router having to find room for it among the BGA's wires."""
    lanes = corridors()
    pads = []                                   # (box, net) of every pad on the board
    for ref, fp in fps.items():
        pads += pad_boxes_net(fp)
    vias = [(pad_xy(fps["U1"], n)) for n in ("B2", "B3", "B4", "C2", "C3", "C4")]
    r = VIA_ROUTE[1] / 2
    made = 0
    todo = []
    for ref, fp in fps.items():
        if ref in ("U1", "U5", "U2") or ref.startswith(("CP", "BT", "SWD")):
            continue
        ext = pad_extent(fp)
        c = ((ext[0] + ext[2]) / 2, (ext[1] + ext[3]) / 2)
        for pad in fp.Pads():
            if pad.GetNetname() == "GND" and pad.GetNumber() != ("5" if ref == "U7" else "-"):
                todo.append((ref, fp, pad, c))
    for ref, fp, pad, c in todo:
        x0, y0 = pad_xy(fp, pad.GetNumber())
        out = math.atan2(y0 - c[1], x0 - c[0])
        best = None
        for d in [0.4 + 0.05 * k for k in range(0, 14)]:
            for da in (0, 0.5, -0.5, 1.0, -1.0, 1.57, -1.57, 2.2, -2.2, 3.14):
                a = out + da
                x, y = x0 + d * math.cos(a), y0 + d * math.sin(a)
                vb = (x - r, y - r, x + r, y + r)
                if not B.rect_ok(vb, B.R_PART + 0.4) or B.overlap(vb, B.KEEPOUTS["antenna"]):
                    continue
                ok = True
                for k in range(0, 11):                       # along the stub and at the via
                    px, py = x0 + (x - x0) * k / 10, y0 + (y - y0) * k / 10
                    pr = r if k == 10 else 0.05
                    tb = (px - pr, py - pr, px + pr, py + pr)
                    for bb, n in pads:
                        gap = 0.2 if n in SENSITIVE else ROUTE_CLEAR          # the photodiode inputs keep 0.2 mm
                        if n != "GND" and B.overlap(tb, (bb[0] - gap, bb[1] - gap, bb[2] + gap, bb[3] + gap)):
                            ok = False
                            break
                    if not ok:
                        break
                    for lane, ln in lanes:
                        if ln != "GND" and B.overlap(tb, lane):
                            ok = False
                            break
                    if not ok:
                        break
                if ok and any(math.dist((x, y), v) < VIA_ROUTE[1] + 0.2 for v in vias):
                    ok = False
                if ok:
                    best = (x, y)
                    break
            if best:
                break
        if best is None:
            print(f"  no ground via found for {ref}.{pad.GetNumber()}")
            continue
        via_at(best[0], best[1], "GND", VIA_ROUTE)
        vias.append(best)
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(P(x0, y0))
        t.SetEnd(P(*best))
        t.SetWidth(mm(TRACK))
        t.SetLayer(pcbnew.B_Cu)
        t.SetNet(net("GND"))
        t.SetLocked(True)
        board.Add(t)
        made += 1
    print(f"  {made} ground vias placed beside pads")


def add_zone(layer, nname):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(net(nname))
    z.SetLocalClearance(mm(0.12))
    z.SetMinThickness(mm(0.1))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if layer == pcbnew.In1_Cu else pcbnew.ZONE_CONNECTION_THERMAL)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in B.board_polygon(240):
        ol.Append(FromMM(x), FromMM(-y))
    board.Add(z)


def add_text(layer, s, x, y, size):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetPosition(P(x, y))
    t.SetTextSize(VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(0.12))
    board.Add(t)


# ------------------------------------------------------------------ rules and files
def set_rules():
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ds.m_MinClearance = mm(CLEAR)
    ds.m_TrackMinWidth = mm(TRACK)
    ds.m_MinThroughDrill = mm(VIA[0])
    ds.m_CopperEdgeClearance = mm(EDGE_CLEAR)
    ds.m_HoleToHoleMin = mm(0.25)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(mm(CLEAR))
    nc.SetTrackWidth(mm(TRACK))
    nc.SetViaDiameter(mm(VIA_ROUTE[1]))
    nc.SetViaDrill(mm(VIA_ROUTE[0]))


def netclass(name, track, priority):
    return {"name": name, "clearance": CLEAR, "track_width": track, "via_diameter": VIA_ROUTE[1], "via_drill": VIA_ROUTE[0],
            "microvia_diameter": 0.2, "microvia_drill": 0.1, "diff_pair_width": 0.1, "diff_pair_gap": 0.1, "diff_pair_via_gap": 0.25,
            "wire_width": 6, "bus_width": 12, "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": priority}


SENSITIVE = ("PD1_IN", "PD2_IN")          # photodiode inputs: kept 0.2 mm from other copper wherever the wire runs free


def write_project(path):
    power = ("VBAT", "V18", "VIN_RAW", "VIN_CHG", "LED1", "LED2", "LED3", "LED1_G1", "LED1_G2")
    pro = {
        "meta": {"filename": os.path.basename(path), "version": 3},
        "board": {"design_settings": {
            "defaults": {"copper_line_width": TRACK, "board_outline_line_width": 0.1},
            "rules": {"min_clearance": CLEAR, "min_track_width": TRACK, "min_via_diameter": VIA[1], "min_through_hole_diameter": VIA[0],
                      "min_via_annular_width": 0.05, "min_copper_edge_clearance": EDGE_CLEAR, "min_hole_to_hole": 0.25,
                      "min_hole_clearance": 0.15, "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1,
                      "min_text_height": 0.8, "min_text_thickness": 0.08, "min_resolved_spokes": 2},
            "rule_severities": {"silk_over_copper": "ignore", "silk_overlap": "ignore", "silk_edge_clearance": "ignore",
                                "courtyards_overlap": "ignore", "missing_courtyard": "ignore", "footprint_type_mismatch": "ignore",
                                "lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore", "text_height": "ignore",
                                "text_thickness": "ignore"}}},
        "erc": {"rule_severities": {"footprint_link_issues": "ignore", "lib_symbol_issues": "ignore", "lib_symbol_mismatch": "ignore"}},
        "net_settings": {
            "classes": [netclass("Default", TRACK, 2147483647), netclass("Power", 0.15, 0), dict(netclass("Sensitive", TRACK, 0), clearance=CLEAR_SENSITIVE)],
            "meta": {"version": 4},
            "netclass_assignments": None,
            "netclass_patterns": [{"netclass": "Power", "pattern": p} for p in power] + [{"netclass": "Sensitive", "pattern": p} for p in SENSITIVE],
        },
    }
    with open(path, "w") as f:
        json.dump(pro, f, indent=2)


def build():
    set_rules()
    add_outline()
    add_holes()
    add_pads_not_parts()
    add_ics()
    print("rotations and U5 pads:")
    settle_ics()
    add_u5_links()
    print("passives:")
    place_passives()
    add_vias_in_pads()
    if "--no-stubs" not in sys.argv:
        add_fanout_stubs()
    add_ground_vias()
    rule_area("antenna keep-out", rect=B.KEEPOUTS["antenna"])
    add_zone(pcbnew.In1_Cu, "GND")      # ground plane; the router treats it as a conduction area
    add_text(pcbnew.F_SilkS, "+", 9.0, -2.9, 0.9)
    add_text(pcbnew.F_SilkS, "-", -9.0, -2.9, 0.9)
    add_text(pcbnew.F_SilkS, "V0.1", 0.0, 1.0, 0.8)
    board.GetDesignSettings().SetBoardThickness(mm(0.6))      # JLCPCB 4-layer 0.6 mm (no 0.4 mm in 4 layers); KiCad's default is 1.6


if __name__ == "__main__":
    build()
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "caseback_v01.kicad_pcb")
    board.Save(path)
    write_project(os.path.join(OUT, "caseback_v01.kicad_pro"))
    print("saved", path)
