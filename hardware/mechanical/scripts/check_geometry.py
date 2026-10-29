"""Geometry checks on the exported V0 STLs (stdlib + numpy, no Blender needed).

    python3 check_geometry.py [--dir ../stl] [--tag TXT]

Reads caseback_v0_params[TAG].json and the four STLs written by generate_enclosure.py, measures wall,
floor and roof thickness by ray casting through the meshes, and prints a table. Exit code 1 if any
row fails. Thickness tolerance is 0.01 mm (float32 STL and 180-segment cylinders).
"""

from __future__ import annotations

import json
import os
import struct
import sys
from math import cos, degrees, radians, sin, sqrt

import numpy as np

MIN_T = 0.9
TOL = 0.01
LEDGE_MIN = 0.4
SQUEEZE = (0.15, 0.35)         # accepted cord squeeze range, fraction of cord diameter
FIT_CLR_MIN = 0.2              # radial clearance disc to dish, per side
GAP = 0.1                      # smallest vertical gap counted as air between two solids
rows: list[tuple[str, str, str, bool]] = []


def check(name: str, value: str, limit: str, ok: bool) -> bool:
    rows.append((name, value, limit, bool(ok)))
    return bool(ok)


# ------------------------------------------------------------------ STL + ray casting
def load_stl(path: str) -> np.ndarray:
    data = open(path, "rb").read()
    n = struct.unpack("<I", data[80:84])[0]
    if 84 + 50 * n != len(data):
        raise SystemExit(f"{path}: not a binary STL")
    rec = np.frombuffer(data, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), offset=84, count=n)
    return rec["v"].astype(np.float64)


def open_edges(tris: np.ndarray) -> int:
    pts = np.round(tris.reshape(-1, 3), 4)
    _, idx = np.unique(pts, axis=0, return_inverse=True)
    idx = idx.reshape(-1, 3)
    e = np.sort(np.concatenate([idx[:, [0, 1]], idx[:, [1, 2]], idx[:, [2, 0]]]), axis=1)
    _, counts = np.unique(e, axis=0, return_counts=True)
    return int((counts != 2).sum())


def cast(tris: np.ndarray, orig: np.ndarray, d) -> list[np.ndarray]:
    """Sorted hit parameters t along d for every origin (Moller-Trumbore, double sided)."""
    d = np.asarray(d, dtype=float)
    v0 = tris[:, 0]
    e1, e2 = tris[:, 1] - v0, tris[:, 2] - v0
    pvec = np.cross(d, e2)
    det = np.einsum("mi,mi->m", e1, pvec)
    ok = np.abs(det) > 1e-12
    v0, e1, e2, pvec, det = v0[ok], e1[ok], e2[ok], pvec[ok], det[ok]
    out: list[np.ndarray] = []
    for s in range(0, len(orig), 150):
        o = orig[s:s + 150]
        tv = o[:, None, :] - v0[None]
        u = np.einsum("nmi,mi->nm", tv, pvec) / det
        qv = np.cross(tv, e1[None])
        v = np.einsum("i,nmi->nm", d, qv) / det
        t = np.einsum("mi,nmi->nm", e2, qv) / det
        hit = (u >= 0) & (v >= 0) & (u + v <= 1)
        for r in range(len(o)):
            out.append(np.sort(t[r][hit[r]]))
    return out


def solid_intervals(parts, orig, d, t0=0.0):
    """Merged solid intervals (a, b) along each ray over all parts; None when a part has an odd hit count."""
    per = [cast(p, orig, d) for p in parts]
    res = []
    for i in range(len(orig)):
        iv = []
        bad = False
        for h in per:
            if len(h[i]) % 2:
                bad = True
                break
            iv += [(h[i][k] - t0, h[i][k + 1] - t0) for k in range(0, len(h[i]), 2)]
        if bad:
            res.append(None)
            continue
        iv.sort()
        m: list[list[float]] = []
        for a, b in iv:
            if m and a <= m[-1][1] + 1e-4:
                m[-1][1] = max(m[-1][1], b)
            else:
                m.append([a, b])
        res.append([tuple(x) for x in m])
    return res


def columns(parts, xy):
    zoff = 10.0
    o = np.array([[x, y, -zoff] for x, y in xy])
    return solid_intervals(parts, o, (0, 0, 1), zoff)


def radial(parts, z, angles, r_out):
    """Solid intervals along inward rays starting outside the part; t is the distance from r_out."""
    res = []
    for a in angles:
        o = np.array([[r_out * cos(a), r_out * sin(a), z]])
        res.append(solid_intervals(parts, o, (-cos(a), -sin(a), 0.0))[0])
    return res


def grid(r_max, step, jitter=(0.0137, 0.0091)):
    n = int(r_max / step) + 1
    xs = np.arange(-n, n + 1) * step + jitter[0]
    ys = np.arange(-n, n + 1) * step + jitter[1]
    return [(x, y) for x in xs for y in ys if x * x + y * y <= r_max * r_max]


# ------------------------------------------------------------------ checks
def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    a = sys.argv[1:]
    d = os.path.join(here, "..", "stl")
    tag = ""
    for i, k in enumerate(a):
        if k == "--dir":
            d = a[i + 1]
        if k == "--tag":
            tag = a[i + 1]
    d = os.path.abspath(d)
    P = json.load(open(os.path.join(d, f"caseback_v0_params{tag}.json")))
    T = {k: load_stl(os.path.join(d, v)) for k, v in P["stl"].items()}
    disc = [T["bottom"], T["top"]]
    H, rin = P["disc_h"], P["cavity_r"]
    zc = P["cavity_z"][1]

    for k, t in T.items():
        check(f"mesh closed: {k}", f"{open_edges(t)} open edges", "0", open_edges(t) == 0)
    allv = np.concatenate([t.reshape(-1, 3) for t in disc])
    check("disc diameter", f"{2 * np.hypot(allv[:, 0], allv[:, 1]).max():.2f} mm", f"{P['disc_dia']}", abs(2 * np.hypot(allv[:, 0], allv[:, 1]).max() - P["disc_dia"]) < 0.02)
    check("disc height", f"{allv[:, 2].max() - allv[:, 2].min():.2f} mm", f"{H}", abs(allv[:, 2].max() - allv[:, 2].min() - H) < 0.02)

    # the two shells touch at the seam but must not interpenetrate
    sxy = grid(P["disc_dia"] / 2 - 0.05, 0.5, (0.0113, 0.0071))
    ivb, ivt = columns([T["bottom"]], sxy), columns([T["top"]], sxy)
    overlap = 0.0
    for b, t in zip(ivb, ivt):
        for a0, a1 in (b or []):
            for c0, c1 in (t or []):
                overlap = max(overlap, min(a1, c1) - max(a0, c0))
    check("bottom / top shell interpenetration", f"{max(overlap, 0):.3f} mm", "<= 0.01", overlap <= TOL)

    # floor and roof, vertical rays inside the rim
    xy = grid(rin + 1.0, 0.4)
    col = columns(disc, xy)
    ambiguous = sum(c is None for c in col)
    floor, roof, roof_rec, roof_out, hole = [], [], [], [], []
    for (x, y), iv in zip(xy, col):
        if iv is None or len(iv) < 2:
            continue
        gaps = [(iv[i + 1][0] - iv[i][1], i) for i in range(len(iv) - 1) if iv[i + 1][0] - iv[i][1] >= GAP]
        if not gaps:
            continue
        g, i = max(gaps)
        if iv[0][0] > 0.35:
            continue
        r = sqrt(x * x + y * y)
        floor.append((iv[i][1] - iv[0][0], x, y))
        rt = iv[-1][1] - iv[i + 1][0]
        roof.append((rt, x, y))
        (roof_rec if r < P["suction_dia"] / 2 - 0.1 else roof_out).append((rt, x, y))
    check("columns with ambiguous hits", str(ambiguous), "0", ambiguous == 0)
    mf = min(floor)
    check("floor thickness, min over cavity", f"{mf[0]:.3f} mm at ({mf[1]:.1f},{mf[2]:.1f})", f">= {MIN_T}", mf[0] >= MIN_T - TOL)
    mr = min(roof_rec)
    check("roof under Ø22 pad recess, min", f"{mr[0]:.3f} mm at ({mr[1]:.1f},{mr[2]:.1f})", f">= {MIN_T}", mr[0] >= MIN_T - TOL)
    mo = min(roof_out)
    check("roof outside recess, min", f"{mo[0]:.3f} mm", f">= {MIN_T}", mo[0] >= MIN_T - TOL)
    breach = sum(1 for r in roof_rec if r[0] <= 0.05)
    check("pad recess breaches roof", f"{breach} columns", "0", breach == 0)

    # rim wall, horizontal rays from outside at several heights
    angles = [radians(k * 3.0) + 0.0031 for k in range(120)]
    wall_min = (9.9, 0.0, 0.0)
    for z in (1.05, 1.5, 1.7, 2.25, 2.6):
        for ang, iv in zip(angles, radial(disc, z, angles, P["disc_dia"] / 2 + 3.0)):
            if iv is None:
                continue
            for a0, b0 in iv:
                r0, r1 = P["disc_dia"] / 2 + 3.0 - b0, P["disc_dia"] / 2 + 3.0 - a0
                if (r0 + r1) / 2 >= rin + 0.2 and r1 - r0 < wall_min[0]:
                    wall_min = (r1 - r0, z, degrees(ang))
    check("rim wall / web thickness, min", f"{wall_min[0]:.3f} mm at z={wall_min[1]}", f">= {MIN_T}", wall_min[0] >= MIN_T - TOL)

    # gasket groove: depth from a vertical ray, width from a horizontal one
    gr = P["groove"]
    xg = gr["r0"] + gr["w"] / 2
    iv = columns(disc, [(xg + 0.0137, 0.0091)])[0]
    depth = P["seam_z"] - iv[0][1]
    squeeze = (gr["cord_dia"] - depth) / gr["cord_dia"]
    check("gasket groove depth", f"{depth:.2f} mm (cord {gr['cord_dia']} mm)", "0.4-0.7", 0.4 <= depth <= 0.7)
    check("gasket squeeze", f"{squeeze * 100:.0f} %", f"{SQUEEZE[0] * 100:.0f}-{SQUEEZE[1] * 100:.0f} %", SQUEEZE[0] <= squeeze <= SQUEEZE[1])

    # PPG window seat: ledge = (seat - aperture) / 2, measured along x through the window centre
    wx, wy = P["window"]["xy"]
    w = P["window"]
    def hole_width(z):
        o = np.array([[-20.0, wy + 0.0043, z]])
        iv = solid_intervals(disc, o, (1.0, 0.0, 0.0))[0]
        gaps = [(iv[i][1] - 20.0, iv[i + 1][0] - 20.0) for i in range(len(iv) - 1)]
        c = [g for g in gaps if g[0] < wx < g[1]]
        return (c[0][1] - c[0][0]) if c else 0.0
    ap = hole_width(0.5)
    seat = hole_width(P["floor"] + w["seat_depth"] * 0.5)
    check("PPG aperture", f"{ap:.2f} mm", f"{w['aperture_dia']}", abs(ap - w["aperture_dia"]) < 0.05)
    check("window seat ledge", f"{(seat - ap) / 2:.2f} mm radial", f">= {LEDGE_MIN}", (seat - ap) / 2 >= LEDGE_MIN - TOL)
    ivw = columns(disc, [(wx + (w["aperture_dia"] + w["seat_dia"]) / 4 + 0.0137, wy + 0.0091)])[0]
    check("floor under seat ledge", f"{ivw[0][1]:.2f} mm", f">= {MIN_T}", ivw[0][1] >= MIN_T - TOL)

    # screws: counterbore floor below the caseback plane, through hole open
    sx, sy = P["screws"]["xy"][0]
    ivs = columns(disc, [(sx + P["screws"]["hole_r"] + 0.3, sy + 0.0091)])[0]
    check("screw head counterbore floor", f"z={ivs[-1][1]:.2f} mm", f"< {H - 0.6:.1f} (head below caseback plane)", ivs[-1][1] < H - 0.6 + TOL)
    ivc = columns(disc, [(sx + 0.0021, sy + 0.0043)])[0]
    check("screw through hole open at top", f"top solid z={ivc[-1][1]:.2f}", f"< {H - 1.0:.1f}", ivc[-1][1] < H - 1.0)

    # battery pocket must be free air, inside the cavity
    pk = P["pocket"]
    cx, cy = pk["center"]
    lx, ly, lz = pk["size"]
    pxy = [(cx + (i + 0.5) * 0.5 - lx / 2 + 0.0037, cy + (j + 0.5) * 0.5 - ly / 2 + 0.0019)
           for i in range(int(lx / 0.5)) for j in range(int(ly / 0.5))]
    pcol = columns(disc, pxy)
    zs = [pk["z0"] + 0.02, pk["z0"] + lz - 0.02]
    solid_pts = 0
    far = 0.0
    for (x, y), iv in zip(pxy, pcol):
        far = max(far, sqrt(x * x + y * y))
        if iv is None:
            solid_pts += 1
            continue
        for a0, b0 in iv:
            if a0 < zs[1] and b0 > zs[0]:
                solid_pts += 1
                break
    corner = sqrt((abs(cx) + lx / 2) ** 2 + (abs(cy) + ly / 2) ** 2)
    check("pocket free of material", f"{solid_pts} blocked columns", "0", solid_pts == 0)
    check("pocket inside cavity radius", f"corner r={corner:.2f}, margin {rin - corner:.2f} mm", f"< {rin}", corner < rin)
    check("pocket top below roof", f"pocket top z={pk['z0'] + lz:.2f}, ceiling z={zc:.2f}", f"<= {zc:.2f}",pk["z0"] + lz <= zc + TOL)

    # disc in puck
    pk_r = np.hypot(allv[:, 0], allv[:, 1]).max()
    zf = P["puck"]["h"] - P["puck"]["dish_depth"]
    ang = [radians(k * 5.0) + 0.0031 for k in range(72) if abs(((k * 5) % 360) - 270) > 12]
    rr = []
    for a0, iv in zip(ang, radial([T["puck"]], zf + 1.3, ang, P["puck"]["dia"] / 2 + 3)):
        if iv:
            rr.append(P["puck"]["dia"] / 2 + 3 - iv[0][1])
    dish_r = min(rr)
    check("dish radius vs disc radius", f"dish {dish_r:.2f} vs disc {pk_r:.2f}: {dish_r - pk_r:.2f} mm/side", f">= {FIT_CLR_MIN}", dish_r - pk_r >= FIT_CLR_MIN - TOL)
    puck_wall = min(P["puck"]["dia"] / 2 - r for r in rr)
    check("puck wall around dish", f"{puck_wall:.2f} mm", f">= {MIN_T}", puck_wall >= MIN_T - TOL)
    check("dish depth vs disc key height", f"dish {P['puck']['dish_depth']} mm, notch {P['notch']['height']} mm", "dish > notch", P["puck"]["dish_depth"] > P["notch"]["height"])

    # keying: sample the puck key tab, rotate the disc, test overlap with disc material
    kx = [(x, y) for x, y in grid(P["puck"]["dish_dia"] / 2 - 0.05, 0.25, (0.0071, 0.0033)) if y < -14.0 and abs(x) < 3.0]
    kcol = columns([T["puck"]], kx)
    tab = [(x, y, iv[-1][1]) for (x, y), iv in zip(kx, kcol) if iv and iv[-1][1] > zf + 0.1]
    check("puck key tab found", f"{len(tab)} samples, height {max(t[2] for t in tab) - zf:.2f} mm", "> 0", len(tab) > 0)

    def collides(theta: float) -> bool:
        c, s = cos(-theta), sin(-theta)
        pts = [(c * x - s * y, s * x + c * y, zt - zf) for x, y, zt in tab]
        ivs = columns(disc, [(px + 0.0003, py + 0.0002) for px, py, _ in pts])
        for (px, py, hz), iv in zip(pts, ivs):
            if iv and any(a0 < hz - 0.05 and b0 > 0.05 for a0, b0 in iv):
                return True
        return False
    fit0 = collides(0.0)
    check("disc seats in puck at 0 deg (tab clears notch)", "collision" if fit0 else "free", "free", not fit0)
    first = next((k * 0.5 for k in range(1, 61) if collides(radians(k * 0.5)) and collides(radians(-k * 0.5))), None)
    check("rotation play before the tab hits the rim", f"about +/-{first:.1f} deg" if first else ">15 deg", "<= 5 deg", first is not None and first <= 5.0)
    bad = [t for t in (90, 180, 270) if not collides(radians(t))]
    check("disc rotated 90/180/270 deg cannot seat", "blocked" if not bad else f"seats at {bad}", "blocked", not bad)

    # cell fit table (analytic, from the parameters)
    avail = zc - P["floor"]
    fs = P["foam"] + P["slack"]
    print(f"\nCell fit (in-plane: half diagonal of the pocket inside the Ø{2 * rin:.1f} cavity, window and screws ignored)")
    print(f"Cavity height {avail:.2f} mm (z {P['floor']} to {zc:.2f}), foam + slack {fs:.2f} mm, pocket {lx:.1f} x {ly:.1f} mm")
    print(f"{'cell':<10}{'T x W x L (mm)':<20}{'needs':>9}{'has':>7}{'fits':>7}{'min disc H':>12}{'in-plane':>10}{'vol mm3':>9}{'mAh@250Wh/L':>14}")
    for n, (t, wd, ln) in P["cells"].items():
        need = t + fs
        h_min = P["floor"] + need + 0.9 + 0.4
        mah = t * wd * ln / 1000 * 250 / 3.7
        diag = sqrt((ln + P["pocket_clr"]) ** 2 + (wd + P["pocket_clr"]) ** 2) / 2
        plan = "yes" if diag <= rin else "NO"
        print(f"{n:<10}{t:>4} x {wd:>4} x {ln:>4}{'':<4}{need:>8.2f}{avail:>7.2f}{'yes' if need <= avail + 1e-9 else 'NO':>7}{h_min:>12.2f}{plan:>10}{t * wd * ln:>9.0f}{mah:>14.0f}")

    w0 = max(len(r[0]) for r in rows)
    w1 = max(len(r[1]) for r in rows)
    print(f"\n{'check':<{w0}}  {'measured':<{w1}}  {'limit':<28} result")
    for n, v, lim, ok in rows:
        print(f"{n:<{w0}}  {v:<{w1}}  {lim:<28} {'PASS' if ok else 'FAIL'}")
    failed = [r for r in rows if not r[3]]
    print(f"\n{len(rows) - len(failed)}/{len(rows)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
