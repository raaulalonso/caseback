"""Draw all the copper of caseback_v01.kicad_pcb again, with the grid router of manhattan.py.

    $KICAD/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -I route_v01.py IN.kicad_pcb OUT.kicad_pcb

The parts, the pads, the outline and the vias in pads stay where they are: the board is the source of the placement. Every
other wire and via is taken off and drawn again, in this order:

1. the ten GPIO signals get their pads on the module (netlist_v01.U5_PADS);
2. the four lanes of the optics (the photodiode inputs and the two LED returns) are laid by hand, below, as straight runs on
   F.Cu with a via in each end pad. The router does not see them as something to find, only as copper to keep away from;
3. each ground pad gets a short stub to the nearest via, or to a new one: In1.Cu is the ground plane. A ground pad with no
   room round it gets its via in the pad;
4. the other nets, one after the other in ORDER, each from the pad nearest its centre outwards. A via is either in a pad or
   clear of it, never across its edge.
If a net cannot be joined, the whole board is routed again with that net first (up to six times).

Wires are 0.10 mm (0.15 mm for the supply and the LED nets), clearance 0.10 mm (0.15 mm at the photodiode inputs), vias
0.30 / 0.15 mm. Wires that end in nothing are dropped at the end. The project file next to OUT gets the same clearances.
"""

import json
import math
import os
import sys
import time

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import manhattan as M  # noqa: E402
import netlist_v01 as N  # noqa: E402

CLEAR, CLEAR_SENSITIVE = 0.10, 0.15
WIDTH, WIDTH_POWER = 0.10, 0.15
VIA_IN_PAD = 0.25                  # diameter of the vias that sit in pads (drill 0.15)
LINK_WIDTH = 0.30                  # the wires between neighbouring module pads (U5_LINKS), kept as they are
KEEPOUTS = [(-5.5, -11.5, 5.5, -6.05)]          # antenna of the module: x0, y0, x1, y1 in the disc frame (y up)
SENSITIVE = {"PD1_IN", "PD2_IN"}
POWER = {"VBAT", "V18", "VIN_RAW", "VIN_CHG", "LED1", "LED2", "LED3", "LED1_G1", "LED1_G2"}
ORDER = ["PD1_IN", "PD2_IN", "LED1_G1", "LED1_G2", "LED1", "LED2", "LED3", "SPI_SCK", "SPI_MISO", "SPI_MOSI", "SPI_CS",
         "AFE_INT", "I2C_SCL", "I2C_SDA", "IMU_INT", "CHG_STAT", "SWDIO", "SWDCLK", "VBAT_SENSE", "VIN_RAW", "VIN_CHG",
         "ISET", "TS", "VREF", "VBAT", "V18"]

# the prices of the search: a via costs as much as 10 mm of wire (15 mm when it lands in a pad), and F.Cu runs along x, In2.Cu along y
COST = {"via": 10.0, "in_pad": 5.0, "turn90": 2.5, "turn45": 1.0, "diagonal": 1.2, "off_direction": 1.2, "halo": 0.35,
        "layer": {M.F: 1.0, M.I2: 1.05, M.B: 2.2}, "prefer": {M.F: "h", M.I2: "v", M.B: None}}
COST_GND = {"via": 30.0, "in_pad": 0.0, "turn90": 3.0, "turn45": 1.0, "diagonal": 0.0, "off_direction": 0.25, "halo": 0.0,
            "layer": {M.F: 1.12, M.I2: 1.12, M.B: 1.0}, "prefer": {M.F: "h", M.I2: "v", M.B: None}}

# lanes drawn by hand: net, wire width, F.Cu points (x, y in mm, y up). The first and last point get a via of 0.25 mm.
# PD1_IN and PD2_IN run from the two photodiode balls of the AFE (D5, D4) round the south side of the optics to the pads of
# the photodiodes; LED2 and LED3 are the returns of the two outer LEDs.
LANES = [
    ("PD2_IN", 0.10, [(5.35, 0.1), (5.35, 2.4), (-0.6, 2.4), (-0.6, 1.85)]),
    ("PD1_IN", 0.10, [(5.75, 0.1), (5.75, 2.75), (-3.0, 2.75), (-3.0, 1.85)]),
    ("LED2", 0.15, [(4.15, -0.3), (1.8, -0.3)]),
    ("LED3", 0.15, [(4.15, -0.7), (0.6, -0.7)]),
]

LAYER_OF = {pcbnew.F_Cu: M.F, pcbnew.In2_Cu: M.I2, pcbnew.B_Cu: M.B}
KICAD_LAYER = {M.F: pcbnew.F_Cu, M.I2: pcbnew.In2_Cu, M.B: pcbnew.B_Cu}
ALL = (M.F, M.I2, M.B)
LANE_NETS = {net for net, _, _ in LANES}


class Router:
    def __init__(self, board):
        self.board = board
        self.grid = M.Grid()
        self.names = sorted({p.GetNetname() for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname()})
        self.nid = {n: i + 1 for i, n in enumerate(self.names)}
        self.pads = {n: [] for n in self.names}
        self.vias = []                                  # (net, x, y) of every via on the board, placed or new
        self.placed = {n: [] for n in self.names}       # the vias that were already on the board: net -> [(x, y, via)]
        self.items = {n: [] for n in self.names}        # ("seg", layer, [(x, y)], width) and ("via", x, y, diameter, locked)
        self.gone = []                                  # vias taken off the board; kept so that SWIG does not free them twice

    # ------------------------------------------------------------------ the board as it is
    def load(self):
        board, grid = self.board, self.grid
        free = 1000
        for fp in board.GetFootprints():
            for p in fp.Pads():
                net = p.GetNetname()
                if net:
                    nid = self.nid[net]
                else:
                    free += 1
                    nid = free
                layers = [LAYER_OF[l] for l in LAYER_OF if p.IsOnLayer(l)]
                if not layers:
                    continue
                pos = p.GetPosition()
                if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE:
                    r = ToMM(p.GetSize().x) / 2
                    kind, geom = "circle", (ToMM(pos.x), -ToMM(pos.y), r)
                    ext = (geom[0] - r, geom[1] - r, geom[0] + r, geom[1] + r)
                else:
                    bb = p.GetBoundingBox()
                    kind, geom = "rect", (ToMM(bb.GetLeft()), -ToMM(bb.GetBottom()), ToMM(bb.GetRight()), -ToMM(bb.GetTop()))
                    ext = geom
                grid.mark(kind, geom, layers, nid, net in SENSITIVE)
                grid.keep_vias_off(kind, geom)
                if net:
                    self.pads[net].append({"ref": fp.GetReference(), "num": p.GetNumber(), "kind": kind, "geom": geom, "layers": layers, "ext": ext})
        for t in board.GetTracks():
            net = t.GetNetname()
            if t.Type() == pcbnew.PCB_VIA_T:
                x, y = ToMM(t.GetPosition().x), -ToMM(t.GetPosition().y)
                grid.mark("circle", (x, y, ToMM(t.GetWidth(pcbnew.F_Cu)) / 2), ALL, self.nid.get(net, 0), net in SENSITIVE)
                grid.add_hole(x, y)
                self.vias.append((net, x, y))
                self.placed.setdefault(net, []).append((x, y, t))
            else:
                a, b = t.GetStart(), t.GetEnd()
                grid.mark("seg", (ToMM(a.x), -ToMM(a.y), ToMM(b.x), -ToMM(b.y), ToMM(t.GetWidth()) / 2),
                          (LAYER_OF.get(t.GetLayer(), M.B),), self.nid.get(net, 0))
        grid.mark_outline(KEEPOUTS)

    # ------------------------------------------------------------------ what is added
    def add_seg(self, net, layer, pts, width):
        self.items[net].append(("seg", layer, pts, width))
        for a, b in zip(pts, pts[1:]):
            self.grid.mark("seg", (a[0], a[1], b[0], b[1], width / 2), (layer,), self.nid[net], net in SENSITIVE)

    def add_via(self, net, x, y, diameter=M.VIA_D, locked=False):
        if any(abs(v[1] - x) < 0.01 and abs(v[2] - y) < 0.01 for v in self.vias):
            return
        self.items[net].append(("via", x, y, diameter, locked))
        self.vias.append((net, x, y))
        self.grid.mark("circle", (x, y, diameter / 2), ALL, self.nid[net], net in SENSITIVE)
        self.grid.add_hole(x, y)

    def add_path(self, net, path, width):
        for it in M.to_polylines(path):
            if it[0] == "seg":
                self.add_seg(net, it[1], [(M.cx(i), M.cy(j)) for i, j in it[2]], width)
            else:
                self.add_via(net, M.cx(it[1]), M.cy(it[2]))

    # ------------------------------------------------------------------ search helpers
    @staticmethod
    def centre(pad):
        e = pad["ext"]
        return (e[0] + e[2]) / 2, (e[1] + e[3]) / 2

    @staticmethod
    def cells(pad):
        """Grid cells inside a pad, on each of its layers (the cell nearest the middle when the pad is smaller than a cell)."""
        out = []
        g, e = pad["geom"], pad["ext"]
        for l in pad["layers"]:
            found = []
            for iy in range(M.iy_of(e[1]) - 1, M.iy_of(e[3]) + 2):
                for ix in range(M.ix_of(e[0]) - 1, M.ix_of(e[2]) + 2):
                    x, y = M.cx(ix), M.cy(iy)
                    inside = (math.hypot(x - g[0], y - g[1]) <= g[2] + 1e-9) if pad["kind"] == "circle" else \
                             (g[0] - 1e-9 <= x <= g[2] + 1e-9 and g[1] - 1e-9 <= y <= g[3] + 1e-9)
                    if inside:
                        found.append((l, ix, iy))
            if not found:
                cx_, cy_ = Router.centre(pad)
                found.append((l, M.ix_of(cx_), M.iy_of(cy_)))
            out += found
        return out

    def add_tree(self, tree, path):
        for k in path:
            tree.add((k[0], k[1], k[2]))
        for it in M.to_polylines(path):
            if it[0] == "via":
                tree.update((l, it[1], it[2]) for l in ALL)

    # ------------------------------------------------------------------ the three stages
    def lanes(self):
        for net, width, pts in LANES:
            for x, y in (pts[0], pts[-1]):
                self.add_via(net, x, y, VIA_IN_PAD, locked=True)
            self.add_seg(net, M.F, [tuple(p) for p in pts], width)

    def ground(self):
        """Every ground pad: a stub on its own layer to a ground via within 1.4 mm, or to a new one at the nearest free spot;
        with no room for that, a via in the pad."""
        nid = self.nid["GND"]
        new = in_pad = 0
        for p in sorted(self.pads["GND"], key=lambda p: (p["ref"], p["num"])):
            px, py = self.centre(p)
            if any(v[0] == "GND" and abs(px - v[1]) < 0.12 and abs(py - v[2]) < 0.12 for v in self.vias):
                continue                                    # a via already sits in the pad
            layer = p["layers"][0]
            targets = {}
            for dy in range(-30, 31):
                for dx in range(-30, 31):
                    ix, iy = M.ix_of(px) + dx, M.iy_of(py) + dy
                    if math.hypot(dx, dy) * M.G > 1.4 or not self.grid.via_ok(ix, iy, nid) or self.grid.in_pad[iy * M.NX + ix]:
                        continue
                    if self.grid.free("n", layer, iy * M.NX + ix, nid):
                        targets[(layer, ix, iy)] = None
            for v in self.vias:
                if v[0] == "GND" and math.hypot(v[1] - px, v[2] - py) < 1.6:
                    targets.update({(l, M.ix_of(v[1]), M.iy_of(v[2])): "via" for l in ALL})
            window = (max(0, M.ix_of(px) - 40), min(M.NX - 1, M.ix_of(px) + 40), max(0, M.iy_of(py) - 40), min(M.NY - 1, M.iy_of(py) + 40))
            path, tag = M.search(self.grid, nid, "n", set(self.cells(p)), targets, [(px, py)], COST_GND, window, vias=False) if targets else (None, None)
            if path:
                self.add_path("GND", path, WIDTH)
                if tag is None:
                    self.add_via("GND", M.cx(path[-1][1]), M.cy(path[-1][2]))
                    new += 1
                continue
            spots = sorted((c for c in self.cells(p) if self.grid.via_ok(c[1], c[2], nid)), key=lambda c: math.hypot(M.cx(c[1]) - px, M.cy(c[2]) - py))
            if not spots:
                print(f"   no ground via for {p['ref']}.{p['num']}")
                continue
            self.add_via("GND", M.cx(spots[0][1]), M.cy(spots[0][2]))
            in_pad += 1
        print(f"   GND: {new} new vias, {in_pad} in pads")

    def net(self, net):
        """Join all the pads of a net: grow a tree from the pad nearest the centre, and each time take the shortest way to the next pad."""
        nid = self.nid[net]
        variant = "w" if net in POWER else "s" if net in SENSITIVE else "n"
        width = WIDTH_POWER if net in POWER else WIDTH
        pads = self.pads[net]
        if not pads:
            return True
        tree = {(l, M.ix_of(v[1]), M.iy_of(v[2])) for v in self.vias if v[0] == net for l in ALL}
        remaining = list(pads)
        if not tree:
            cen = [self.centre(p) for p in pads]
            mx, my = sum(c[0] for c in cen) / len(cen), sum(c[1] for c in cen) / len(cen)
            first = min(pads, key=lambda p: math.hypot(self.centre(p)[0] - mx, self.centre(p)[1] - my))
            tree.update(self.cells(first))
            remaining.remove(first)
        while True:
            remaining = [p for p in remaining if not any(c in tree for c in self.cells(p))]
            if not remaining:
                return True
            targets = {c: p for p in remaining for c in self.cells(p)}
            centres = [self.centre(p) for p in remaining]
            xs = [M.cx(c[1]) for c in tree] + [c[0] for c in centres]
            ys = [M.cy(c[2]) for c in tree] + [c[1] for c in centres]
            path = tag = None
            used = variant
            for margin in (4.0, 8.0, 99.0):
                window = (max(0, M.ix_of(min(xs) - margin)), min(M.NX - 1, M.ix_of(max(xs) + margin)),
                          max(0, M.iy_of(min(ys) - margin)), min(M.NY - 1, M.iy_of(max(ys) + margin)))
                path, tag = M.search(self.grid, nid, variant, tree, targets, centres, COST, window)
                if not path and variant == "w":             # no room for the wider wire: 0.10 mm
                    path, tag = M.search(self.grid, nid, "n", tree, targets, centres, COST, window)
                    used = "n"
                if path:
                    break
            if not path:                                    # the tree may be walled in: grow from a pad towards it instead
                used = variant
                back = {c: None for c in tree}
                centres_t = [(M.cx(c[1]), M.cy(c[2])) for c in list(tree)[:60]]
                for p in remaining:
                    path, _ = M.search(self.grid, nid, variant, set(self.cells(p)), back, centres_t, COST)
                    if path:
                        path.reverse()
                        tag = p
                        break
            if not path:
                print(f"   {net}: no path to {[(p['ref'], p['num']) for p in remaining]}")
                return False
            self.add_path(net, path, WIDTH_POWER if used == "w" else WIDTH)
            self.add_tree(tree, path)
            tree.update(self.cells(tag))
            remaining.remove(tag)

    # ------------------------------------------------------------------ clean-up
    def covered(self, net, layer, x, y):
        for p in self.pads[net]:
            if layer not in p["layers"]:
                continue
            g = p["geom"]
            if p["kind"] == "circle":
                if math.hypot(x - g[0], y - g[1]) <= g[2] + 1e-6:
                    return True
            elif g[0] - 1e-6 <= x <= g[2] + 1e-6 and g[1] - 1e-6 <= y <= g[3] + 1e-6:
                return True
        return False

    def prune(self):
        """Drop vias that join copper on fewer than two layers (the ground plane counts for ground) and wires that end in
        nothing, until nothing changes. A via in a pad that no wire uses goes too."""
        dropped = 0
        for net, items in self.items.items():
            segs = [[it[1], a, b, it[3]] for it in items if it[0] == "seg" for a, b in zip(it[2], it[2][1:])]
            # every via of the net as [x, y, item or board via, kept]; the lane vias are drawn by hand and stay
            vias = [[it[1], it[2], it, it[4]] for it in items if it[0] == "via"] + [[x, y, v, False] for x, y, v in self.placed.get(net, [])]

            def on_wire(layer, p, skip):
                return any(j != skip and s[0] == layer and M.dist_seg(p[0], p[1], s[1][0], s[1][1], s[2][0], s[2][1]) < 1e-6 for j, s in enumerate(segs))

            def layers_at(x, y):
                return sum(1 for l in ALL if self.covered(net, l, x, y) or any(s[0] == l and M.dist_seg(x, y, s[1][0], s[1][1], s[2][0], s[2][1]) < 1e-6 for s in segs))

            def via_at(p):
                return any(v[0] == net and math.hypot(v[1] - p[0], v[2] - p[1]) < 1e-6 for v in self.vias)

            changed = True
            while changed:
                changed = False
                for v in vias:
                    if not v[3] and layers_at(v[0], v[1]) + (net == "GND") < 2:
                        vias.remove(v)
                        self.vias.remove((net, v[0], v[1]))
                        if not isinstance(v[2], tuple):
                            self.board.Remove(v[2])
                            self.gone.append(v[2])
                        dropped += 1
                        changed = True
                        break
                for j, s in enumerate(segs):
                    if any(not (self.covered(net, s[0], *e) or via_at(e) or on_wire(s[0], e, j)) for e in (s[1], s[2])):
                        segs.pop(j)
                        dropped += 1
                        changed = True
                        break
            self.items[net] = [("seg", l, [s[1], s[2]], s[3]) for l in ALL for s in segs if s[0] == l] + [v[2] for v in vias if isinstance(v[2], tuple)]
        print(f"   {dropped} vias and wires that led nowhere dropped")

    # ------------------------------------------------------------------ out
    def write(self):
        board = self.board
        for net, items in self.items.items():
            nobj = board.FindNet(net)
            for it in items:
                if it[0] == "seg":
                    _, l, pts, w = it
                    for a, b in zip(pts, pts[1:]):
                        t = pcbnew.PCB_TRACK(board)
                        t.SetStart(VECTOR2I(FromMM(a[0]), FromMM(-a[1])))
                        t.SetEnd(VECTOR2I(FromMM(b[0]), FromMM(-b[1])))
                        t.SetWidth(FromMM(w))
                        t.SetLayer(KICAD_LAYER[l])
                        t.SetNet(nobj)
                        board.Add(t)
                else:
                    _, x, y, d, locked = it
                    v = pcbnew.PCB_VIA(board)
                    v.SetPosition(VECTOR2I(FromMM(x), FromMM(-y)))
                    v.SetViaType(pcbnew.VIATYPE_THROUGH)
                    v.SetDrill(FromMM(M.VIA_DRILL))
                    v.SetWidth(FromMM(d))
                    v.SetNet(nobj)
                    v.SetLocked(locked)
                    board.Add(v)


def strip(board):
    """Take off every wire and via except the locked vias in pads (0.25 mm) and the locked links between module pads (0.3 mm)."""
    gone = []
    for t in list(board.GetTracks()):
        via = t.Type() == pcbnew.PCB_VIA_T
        w = ToMM(t.GetWidth(pcbnew.F_Cu) if via else t.GetWidth())
        if t.IsLocked() and abs(w - (VIA_IN_PAD if via else LINK_WIDTH)) < 1e-3:
            continue
        board.Remove(t)
        gone.append(t)              # the wrappers are kept so that SWIG does not free them twice
    return gone


def set_clearances(board):
    nets = board.GetDesignSettings().m_NetSettings
    nets.GetDefaultNetclass().SetClearance(FromMM(CLEAR))
    for name, nc in nets.GetNetclasses().items():
        nc.SetClearance(FromMM(CLEAR_SENSITIVE if name == "Sensitive" else CLEAR))


def write_project(src, dst):
    pro = json.load(open(src))
    for cls in pro["net_settings"]["classes"]:
        cls["clearance"] = CLEAR_SENSITIVE if cls["name"] == "Sensitive" else CLEAR
    pro["meta"]["filename"] = os.path.basename(dst)
    json.dump(pro, open(dst, "w"), indent=2)


ATTEMPTS = 6
KEEP = []                           # boards and removed items of earlier attempts, kept alive so that SWIG does not free them twice


def attempt(src, order):
    """Strip the board and route everything once, in this order. Returns the router, the board and the nets left open."""
    board = pcbnew.LoadBoard(src)
    KEEP.append(board)
    set_clearances(board)
    KEEP.append(strip(board))
    u5 = board.FindFootprintByReference("U5")
    for p in u5.Pads():
        if p.GetNumber() not in N.U5_FIXED and p.GetNetname() != "GND":
            p.SetNetCode(0)
    for sig, num in N.U5_PADS.items():
        u5.FindPadByNumber(num).SetNet(board.FindNet(sig))

    r = Router(board)
    r.load()
    t0 = time.time()
    r.lanes()
    r.ground()
    failed = []
    for net in order:
        if net in r.pads and net not in LANE_NETS:
            t1 = time.time()
            ok = r.net(net)
            print(f"{net:12s} {'ok' if ok else 'OPEN'} {time.time() - t1:.1f}s")
            if not ok:
                failed.append(net)
    print(f"routed in {time.time() - t0:.0f} s")
    return r, board, failed


def main(src, dst):
    order = list(ORDER)
    for k in range(1, ATTEMPTS + 1):
        print(f"attempt {k}")
        r, board, failed = attempt(src, order)
        if not failed:
            break
        print(f"   open: {', '.join(failed)}; they go first next time")
        order = failed + [n for n in order if n not in failed]
    r.prune()
    r.write()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(dst, board)
    write_project(os.path.splitext(src)[0] + ".kicad_pro", os.path.splitext(dst)[0] + ".kicad_pro")
    print("saved", dst + (" - open nets: " + ", ".join(failed) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
