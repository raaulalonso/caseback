"""Grid router for the V0.1 board: wires run at 0, 45 and 90 degrees, on a 0.05 mm grid, and nothing else.

Plain Python, no dependencies (it runs under KiCad's Python). This file is the engine; route_v01.py is the driver that
knows the board. Three copper layers are searched: F.Cu, In2.Cu and B.Cu (In1.Cu is the ground plane). A search is A* over
(layer, x, y, heading) with a price for turns, for 45 degree steps, for leaving a layer's preferred direction (F.Cu
horizontal, In2.Cu vertical) and for a via, so that long runs come out straight and parallel and the skin side keeps only
short stubs.

Every copper item is first written into an occupancy grid, grown by its clearance and by half the width of the wire that
will be searched. A cell holds the net that owns it, or -1 when two nets claim it: a wire of net n may use a cell that is
free or owned by n. The grid is kept in four variants, one per kind of wire (0.10 mm, 0.15 mm, the photodiode inputs
with their wider clearance, and the centre of a via).
"""

from __future__ import annotations

import heapq
import math
from array import array

G = 0.05                                    # grid pitch, mm
X0, Y0, X1, Y1 = -11.65, -11.65, 11.65, 3.45
NX = int(round((X1 - X0) / G)) + 1
NY = int(round((Y1 - Y0) / G)) + 1
F, I2, B = 0, 1, 2                          # the layers that are searched
R_BOARD, CHORD_Y, EDGE_CLEAR = 11.2, 3.2, 0.25
VIA_D, VIA_DRILL = 0.30, 0.15
HOLE_REACH = 0.40                           # centre to centre of two vias: the drills stay 0.25 mm apart
PAD_INSET = 0.04                            # a via counts as in a pad when its centre is this far inside the edge (the corners of a pad are rounded)
PAD_MARGIN = 0.02                           # a via's copper is called "in a pad" when it comes this close to it

# variant: (half width of the wire, clearance). n: 0.10 mm wire, w: 0.15 mm wire, s: photodiode input, v: centre of a via
VARIANTS = {"n": (0.05, 0.10), "w": (0.075, 0.10), "s": (0.05, 0.15), "v": (VIA_D / 2, 0.10)}
SENSITIVE_CLEARANCE = 0.15
DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
STEP = [1.0, math.sqrt(2)] * 4


def cx(ix):
    return X0 + ix * G


def cy(iy):
    return Y0 + iy * G


def ix_of(x):
    return int(round((x - X0) / G))


def iy_of(y):
    return int(round((y - Y0) / G))


def dist_rect(px, py, r):
    dx = max(r[0] - px, 0.0, px - r[2])
    dy = max(r[1] - py, 0.0, py - r[3])
    return math.hypot(dx, dy)


def dist_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / L2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def _bbox(kind, geom, grow):
    if kind == "rect":
        return geom[0] - grow, geom[1] - grow, geom[2] + grow, geom[3] + grow
    if kind == "circle":
        r = geom[2] + grow
        return geom[0] - r, geom[1] - r, geom[0] + r, geom[1] + r
    w = geom[4] + grow
    return min(geom[0], geom[2]) - w, min(geom[1], geom[3]) - w, max(geom[0], geom[2]) + w, max(geom[1], geom[3]) + w


def _dist(kind, geom, px, py):
    if kind == "rect":
        return dist_rect(px, py, geom)
    if kind == "circle":
        return math.hypot(px - geom[0], py - geom[1]) - geom[2]
    return dist_seg(px, py, geom[0], geom[1], geom[2], geom[3]) - geom[4]


class Grid:
    def __init__(self):
        n = NX * NY
        self.occ = {(v, l): array("h", [0]) * n for v in VARIANTS for l in (F, I2, B)}
        self.halo = {l: bytearray(n) for l in (F, I2, B)}     # cells near foreign copper, so that wires keep to the middle of a gap
        self.hole = bytearray(n)                              # cells too close to the drill of a via
        self.in_pad = bytearray(n)                            # cells inside a pad, where a via costs more

    def _claim(self, v, l, i, net):
        a = self.occ[(v, l)]
        if a[i] == 0:
            a[i] = net
        elif a[i] != net:
            a[i] = -1

    def mark(self, kind, geom, layers, net, sensitive=False):
        """Write a pad ('rect' x0 y0 x1 y1, 'circle' x y r), a wire ('seg' x0 y0 x1 y1 half-width) or a via into the grid."""
        for v, (hw, clr) in VARIANTS.items():
            grow = max(clr, SENSITIVE_CLEARANCE if sensitive else 0.0) + hw
            bb = _bbox(kind, geom, grow)
            for iy in range(max(0, iy_of(bb[1]) - 1), min(NY - 1, iy_of(bb[3]) + 1) + 1):
                py = cy(iy)
                for ix in range(max(0, ix_of(bb[0]) - 1), min(NX - 1, ix_of(bb[2]) + 1) + 1):
                    if _dist(kind, geom, cx(ix), py) < grow - 1e-9:
                        for l in layers:
                            self._claim(v, l, iy * NX + ix, net)
        bb = _bbox(kind, geom, 0.37)
        for iy in range(max(0, iy_of(bb[1])), min(NY - 1, iy_of(bb[3])) + 1):
            py = cy(iy)
            for ix in range(max(0, ix_of(bb[0])), min(NX - 1, ix_of(bb[2])) + 1):
                if _dist(kind, geom, cx(ix), py) < 0.37:
                    for l in layers:
                        self.halo[l][iy * NX + ix] = 1

    def mark_outline(self, keepouts):
        """The board edge (0.25 mm of margin) and the keep-outs are closed to every net."""
        for v, (hw, clr) in VARIANTS.items():
            lim = EDGE_CLEAR + hw
            for iy in range(NY):
                py = cy(iy)
                for ix in range(NX):
                    px = cx(ix)
                    blocked = math.hypot(px, py) > R_BOARD - lim or py > CHORD_Y - lim
                    if not blocked:
                        blocked = any(dist_rect(px, py, k) < hw + 0.05 for k in keepouts)
                    if blocked:
                        for l in (F, I2, B):
                            self.occ[(v, l)][iy * NX + ix] = -1

    def keep_vias_off(self, kind, geom):
        """A via's copper that reaches a pad has its centre inside the pad: the cells just outside it are closed to vias, so no
        via straddles an edge. The cells inside cost `in_pad` more, so the search puts a via in a pad only where that saves a detour."""
        reach = VIA_D / 2 + PAD_MARGIN
        bb = _bbox(kind, geom, reach)
        for iy in range(max(0, iy_of(bb[1]) - 1), min(NY - 1, iy_of(bb[3]) + 1) + 1):
            for ix in range(max(0, ix_of(bb[0]) - 1), min(NX - 1, ix_of(bb[2]) + 1) + 1):
                x, y = cx(ix), cy(iy)
                if _dist(kind, geom, x, y) >= reach - 1e-9:
                    continue
                if kind == "circle":
                    inside = _dist(kind, geom, x, y) < -PAD_INSET
                else:
                    inside = geom[0] + PAD_INSET < x < geom[2] - PAD_INSET and geom[1] + PAD_INSET < y < geom[3] - PAD_INSET
                (self.in_pad if inside else self.hole)[iy * NX + ix] = 1

    def add_hole(self, x, y):
        for iy in range(max(0, iy_of(y - HOLE_REACH) - 1), min(NY - 1, iy_of(y + HOLE_REACH) + 1) + 1):
            for ix in range(max(0, ix_of(x - HOLE_REACH) - 1), min(NX - 1, ix_of(x + HOLE_REACH) + 1) + 1):
                if math.hypot(cx(ix) - x, cy(iy) - y) < HOLE_REACH - 1e-9:
                    self.hole[iy * NX + ix] = 1

    def free(self, v, l, i, net):
        o = self.occ[(v, l)][i]
        return o == 0 or o == net

    def via_ok(self, ix, iy, net):
        if not (0 <= ix < NX and 0 <= iy < NY):
            return False
        i = iy * NX + ix
        return not self.hole[i] and all(self.free("v", l, i, net) for l in (F, I2, B))


def octile(dx, dy):
    dx, dy = abs(dx), abs(dy)
    return max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)


def search(grid, net, variant, sources, targets, centers, cost, window=None, vias=True):
    """A* from the cells `sources` {(layer, ix, iy)} to the first cell of `targets` {(layer, ix, iy): tag}.
    Returns (path, tag), the path being a list of (layer, ix, iy, heading), or (None, None). `cost` holds the prices;
    `vias=False` keeps the wire on its layer."""
    occ = {l: grid.occ[(variant, l)] for l in (F, I2, B)}
    occ_via = {l: grid.occ[("v", l)] for l in (F, I2, B)}
    halo = grid.halo
    lo_x, hi_x, lo_y, hi_y = window if window else (0, NX - 1, 0, NY - 1)

    def h(ix, iy):
        x, y = cx(ix), cy(iy)
        return min(octile(x - a, y - b) for a, b in centers) / G

    heap, g, parent = [], {}, {}
    for (l, ix, iy) in sources:
        k = (l, ix, iy, 8)
        g[k] = 0.0
        heapq.heappush(heap, (h(ix, iy), 0.0, k))
    while heap:
        _, gc, k = heapq.heappop(heap)
        if g.get(k, 1e18) < gc - 1e-9:
            continue
        l, ix, iy, d = k
        if (l, ix, iy) in targets:
            path = [k]
            while path[-1] in parent:
                path.append(parent[path[-1]])
            path.reverse()
            return path, targets[(l, ix, iy)]
        i0 = iy * NX + ix
        for nd in range(8):
            turn = 0.0
            if d < 8:
                diff = min((nd - d) % 8, (d - nd) % 8)
                if diff >= 3:
                    continue
                turn = 0.0 if diff == 0 else (cost["turn45"] if diff == 1 else cost["turn90"])
            jx, jy = ix + DIRS[nd][0], iy + DIRS[nd][1]
            if not (lo_x <= jx <= hi_x and lo_y <= jy <= hi_y):
                continue
            j = jy * NX + jx
            o = occ[l][j]
            if o != 0 and o != net:
                continue
            if nd % 2 == 1:                              # a 45 degree step may not squeeze between two blocked corners
                a1, a2 = occ[l][iy * NX + jx], occ[l][jy * NX + ix]
                if a1 not in (0, net) and a2 not in (0, net):
                    continue
            c = STEP[nd] * cost["layer"][l] + turn
            if nd % 2 == 1:
                c += cost["diagonal"]
            if halo[l][j]:
                c += cost["halo"]
            pref = cost["prefer"][l]
            if pref and nd % 2 == 0 and ((pref == "h") != (nd % 4 == 0)):
                c += cost["off_direction"]
            ng = gc + c
            nk = (l, jx, jy, nd)
            if ng < g.get(nk, 1e18) - 1e-9:
                g[nk] = ng
                parent[nk] = k
                heapq.heappush(heap, (ng + h(jx, jy) * 0.999, ng, nk))
        if vias and not grid.hole[i0] and all(occ_via[ll][i0] in (0, net) for ll in (F, I2, B)):
            for nl in (F, I2, B):
                if nl != l and occ[nl][i0] in (0, net):
                    nk = (nl, ix, iy, 8)
                    ng = gc + cost["via"] + (cost["in_pad"] if grid.in_pad[i0] else 0.0)
                    if ng < g.get(nk, 1e18) - 1e-9:
                        g[nk] = ng
                        parent[nk] = k
                        heapq.heappush(heap, (ng + h(ix, iy) * 0.999, ng, nk))
    return None, None


def to_polylines(path):
    """Search path -> [('seg', layer, [(ix, iy), ...]), ('via', ix, iy)] with collinear steps merged."""
    out, cur = [], None
    for a, b in zip(path, path[1:]):
        la, xa, ya, _ = a
        lb, xb, yb, _ = b
        if la != lb:
            if cur:
                out.append(cur)
                cur = None
            out.append(("via", xa, ya))
            continue
        if cur is None:
            cur = ("seg", la, [(xa, ya)])
        pts = cur[2]
        if len(pts) >= 2:
            ux, uy = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
            vx, vy = xb - xa, yb - ya
            if ux * vy - uy * vx == 0 and ux * vx + uy * vy > 0:
                pts[-1] = (xb, yb)
                continue
        pts.append((xb, yb))
    if cur:
        out.append(cur)
    return out
