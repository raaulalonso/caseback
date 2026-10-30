"""Caseback band, first generation: the numbers of the holder, the strap and the buckle, and the checks that tie them to the disc and
to its charger.

    python3 band_v01.py              prints the checks

Standard library only. generate_band.py (Blender) imports this file, so the model, the renders and the checks use the same numbers.
The disc comes from hardware/v1-pcb/board_v01.py; the charger is the one of generate_disc.py, whose numbers are repeated in PUCK below
and compared with it when generate_band.py runs.

The band has no electronics. The disc sits in a silicone holder on the top of the wrist with its skin face out of the holder. The charger
is a round base with a dish: a fixed hook and a sprung latch go into two pockets in the rim of the disc and hold it down on the two
spring pins until a button is pressed. The pockets are in the part of the rim that stands out of the holder, so the disc clicks into the
charger on a watch, alone or in the band.

Frames: millimetres. The holder: the centre of the disc at (0, 0), x along the strap, Z = 0 the skin face of the disc, +Z away from
the wrist.
"""

from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "v1-pcb")))
import board_v01 as B  # noqa: E402

# ------------------------------------------------------------------ the disc, as the band sees it
R_DISC = B.R_DISC                                  # 12.5
DISC_TOP = B.H + B.PAD_PROUD                       # 3.1, the top of the microsuction pad
SIDE_Z0, SIDE_Z1 = B.EDGE_SKIN, B.H - B.EDGE_LID   # the outer wall of the disc is straight from z = 1.2 to 2.4
CONTACTS = B.CONTACTS                              # two steel contacts on the skin face, (-9, -1) and (9, -1)
CONTACT_D = B.CONTACT_SLUG_D
DISC_G = 3.0                                       # estimate

# ------------------------------------------------------------------ the charger of the disc (generate_disc.py)
PUCK = dict(r=17.0, h=7.0, dish_r=12.8, dish_depth=1.2, pogo_free=0.35, hook_reach=0.33, hook_w=2.6, latch_w=4.0, latch_travel=0.8)
LOOP_INNER = (63.0, 53.0)                          # inside of the closed band in the model (a wrist of about 197 mm round), across and top to bottom
POCKET_Z, POCKET_DEPTH, POCKET_W = B.POCKET_Z, B.POCKET_DEPTH, B.POCKET_W

# ------------------------------------------------------------------ the holder: one moulding of silicone round the disc
HOLDER = dict(
    L=38.0,              # along the strap; across it the holder is as wide as the strap
    corner=7.0,          # plan radius of the four corners
    proud=1.3,           # the skin face of the disc stands this far out of the holder
    roof=0.6,            # the back of the holder over the pad of the disc
    bore_r=12.4,         # 0.1 mm smaller than the disc: the silicone grips its straight wall
    push_r=4.0,          # a hole in the back: a finger pushes the disc out through it
    edge_skin=0.8,       # radius of the edge on the skin side
    edge_back=1.0,       # radius of the edge on the back
    strap_in=5.0,        # length of strap moulded into the right end of the holder
    strap_holes=(2, 1.6),  # two holes punched in the end of the strap: the silicone flows through them
    strap_sink=0.15,     # the strap end lies this much nearer the skin inside the holder
    shore_a=60,
)
STRAP_W, STRAP_T = 27.4, 1.4                       # woven polyester, twill, with a bound edge
HOOK_W, HOOK_T = 25.0, 0.35                        # hook tape on the inside of the free end; the outside of the strap is the loop face
BUCKLE = dict(depth=2.6, wall=0.85, slot=STRAP_T + 0.9, tab=4.0, tab_t=0.6)   # 316L; the tab is moulded into the left end of the holder
EXTRA = 44.0                                       # the free end runs this far past the start of the strap, over it
STRAP_LEN = 245.0                                  # from the holder to the tip of the free end


def holder_t() -> float:
    return DISC_TOP + HOLDER["roof"] - HOLDER["proud"]


def band_mass() -> dict:
    """Rough masses in grams: woven strap at 0.6 g/cm3, silicone at 1.15, steel at 8.0."""
    h = HOLDER
    plan = h["L"] * STRAP_W - (4 - math.pi) * h["corner"] ** 2
    holder = (plan * holder_t() - math.pi * h["bore_r"] ** 2 * (DISC_TOP - h["proud"]) - math.pi * h["push_r"] ** 2 * h["roof"]) * 1.15e-3
    strap = STRAP_LEN * STRAP_W * STRAP_T * 0.6e-3
    hook = (EXTRA - 10.0) * HOOK_W * HOOK_T * 0.5e-3
    k = BUCKLE
    w = STRAP_W + 0.6 + 2 * k["wall"]
    buckle = (2 * (w + k["slot"]) * k["wall"] * k["depth"] + k["tab"] * w * k["tab_t"] * 0.5) * 8.0e-3
    return dict(holder=holder, strap=strap, hook=hook, buckle=buckle, total=holder + strap + hook + buckle)


# ------------------------------------------------------------------ checks
def checks():
    rows = []

    def add(name, ok, detail):
        rows.append((name, bool(ok), detail))

    h = HOLDER
    z0 = h["proud"]
    t = holder_t()
    # the disc in the holder
    add("holder grips the straight wall of the disc", z0 <= SIDE_Z1 - 0.8 and 0.05 <= R_DISC - h["bore_r"] <= 0.15,
        f"the bore covers the wall from z = {z0} to {SIDE_Z1:.1f} ({SIDE_Z1 - z0:.1f} mm) and the rounded edge above it, {R_DISC - h['bore_r']:.2f} mm of interference")
    add("holder wall beside the disc", STRAP_W / 2 - h["bore_r"] >= 1.0, f"{STRAP_W / 2 - h['bore_r']:.2f} mm at the sides")
    add("back of the holder", h["roof"] >= 0.5, f"{h['roof']} mm over the pad")
    add("push-out hole inside the pad", h["push_r"] <= B.R_RECESS - 3.0, f"hole r {h['push_r']}, pad r {B.R_RECESS}: the finger presses the pad, not its edge")
    add("holder thickness", t <= 2.6, f"{t:.1f} mm; from the skin face of the disc to the outside of the free end {DISC_TOP + h['roof'] + STRAP_T + HOOK_T:.2f} mm")
    add("skin face of the disc out of the holder", 1.0 <= z0 <= 1.6, f"{z0} mm")
    add("contacts uncovered", all(math.hypot(x, y) + CONTACT_D / 2 < h["bore_r"] for x, y in CONTACTS),
        f"contacts end at r {max(math.hypot(x, y) for x, y in CONTACTS) + CONTACT_D / 2:.2f}, inside the bore, {z0} mm out of the holder")
    # the strap moulded into the holder
    inner = t - (STRAP_T + HOOK_T)                               # the inner line of the strap, from the skin side of the holder
    under = inner - h["strap_sink"]
    over = t - (inner - h["strap_sink"] + STRAP_T)
    add("silicone round the strap end", min(under, over) >= 0.45, f"{under:.2f} mm under it, {over:.2f} mm over it")
    add("strap end clear of the bore", h["L"] / 2 - h["strap_in"] - h["bore_r"] >= 1.0, f"{h['L'] / 2 - h['strap_in'] - h['bore_r']:.1f} mm")
    add("strap end long enough to anchor", h["strap_in"] >= 4.5 and h["strap_holes"][0] >= 2, f"{h['strap_in']} mm with {h['strap_holes'][0]} holes of {h['strap_holes'][1]} mm")
    # the buckle
    k = BUCKLE
    add("buckle slot takes the strap", k["slot"] >= STRAP_T + 0.8, f"slot {k['slot']:.1f} mm for a strap of {STRAP_T}")
    add("buckle tab in the silicone", k["tab"] >= 3.5 and k["tab_t"] + 0.8 <= t, f"tab {k['tab']} x {k['tab_t']} mm in an end {t:.1f} mm thick")
    # the closure
    add("hook tape narrower than the strap", HOOK_W <= STRAP_W - 2.0, f"{HOOK_W} mm on {STRAP_W}")
    hook_len = EXTRA - (h["L"] / 2 - (h["L"] / 2 - h["strap_in"])) - 5.0
    add("hook tape on the strap", hook_len >= 30.0, f"about {hook_len:.0f} mm past the end of the holder")
    # the charger
    add("disc reaches the floor of the charger dish", h["proud"] >= PUCK["dish_depth"] + 0.1,
        f"disc {h['proud']} mm out of the holder, dish {PUCK['dish_depth']} mm deep: the holder stays {h['proud'] - PUCK['dish_depth']:.1f} mm above the charger")
    add("pockets of the disc stand out of the holder", POCKET_Z[1] <= h["proud"] - 0.05, f"pockets from z = {POCKET_Z[0]} to {POCKET_Z[1]}, holder from {h['proud']}")
    add("hook and latch stay under the holder", PUCK["dish_depth"] <= h["proud"] - 0.1, f"the rim of the charger is {PUCK['dish_depth']} mm over the dish floor, the holder {h['proud']}")
    add("latch clears the disc when pressed", PUCK["latch_travel"] >= PUCK["hook_reach"] + (PUCK["dish_r"] - R_DISC) + 0.1,
        f"travel {PUCK['latch_travel']} mm for a tooth {PUCK['hook_reach']} mm into the pocket and {PUCK['dish_r'] - R_DISC:.1f} mm of gap")
    add("one way in", PUCK["hook_w"] <= POCKET_W[1] - 0.3 and POCKET_W[1] < PUCK["latch_w"] <= POCKET_W[0] - 0.4,
        f"hook {PUCK['hook_w']} mm fits both pockets ({POCKET_W[1]}, {POCKET_W[0]}), latch {PUCK['latch_w']} mm only the wide one")
    add("charger fits inside the closed band", 2 * PUCK["r"] <= LOOP_INNER[0] - 10.0 and PUCK["h"] + 3.0 <= LOOP_INNER[1] - 10.0,
        f"charger {2 * PUCK['r']:.0f} x {PUCK['h']} mm inside a loop of {LOOP_INNER[0]:.0f} x {LOOP_INNER[1]:.0f}; the plug points across the band, out of its side")
    return rows


def main():
    rows = checks()
    width = max(len(r[0]) for r in rows)
    for name, ok, detail in rows:
        print(f"{'ok  ' if ok else 'FAIL'} {name:<{width}}  {detail}")
    m = band_mass()
    print("\nmass, g: " + ", ".join(f"{k} {v:.1f}" for k, v in m.items()))
    print(f"holder {HOLDER['L']} x {STRAP_W} x {holder_t():.1f} mm, strap {STRAP_W} x {STRAP_T} mm")
    return 0 if all(ok for _, ok, _ in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
