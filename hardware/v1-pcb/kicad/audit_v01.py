"""Audit of the routed board: how long and how roundabout every net is.

    $KICAD/.../python3 audit_v01.py [BOARD.kicad_pcb]

For each net: pins, wire length on each layer, number of vias, and the ratio between the wire and the shortest tree that
could join the pins (half-perimeter of the pin box as a floor). A DRC with no errors says the board can be made; this
says how well it is drawn. The nets that matter most for the measurement are marked.
"""

import math
import os
import sys

import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "caseback_v01.kicad_pcb")
SENSITIVE = {"PD1_IN": "photodiode input", "PD2_IN": "photodiode input", "VREF": "reference", "LED1": "LED current", "LED2": "LED current",
             "LED3": "LED current", "SPI_SCK": "SPI clock", "I2C_SCL": "I2C", "I2C_SDA": "I2C", "VBAT": "supply", "V18": "supply"}
LAYER = {pcbnew.F_Cu: "F", pcbnew.In1_Cu: "1", pcbnew.In2_Cu: "2", pcbnew.B_Cu: "B"}

board = pcbnew.LoadBoard(BOARD)
rows = []
pins = {}
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname():
            pins.setdefault(p.GetNetname(), []).append((ToMM(p.GetPosition().x), -ToMM(p.GetPosition().y)))
wire = {}
vias = {}
layers = {}
widths = {}
for t in board.GetTracks():
    n = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        vias[n] = vias.get(n, 0) + 1
    else:
        a, b = t.GetStart(), t.GetEnd()
        L = math.hypot(ToMM(a.x - b.x), ToMM(a.y - b.y))
        wire[n] = wire.get(n, 0.0) + L
        layers.setdefault(n, {})
        layers[n][LAYER[t.GetLayer()]] = layers[n].get(LAYER[t.GetLayer()], 0.0) + L
        widths.setdefault(n, set()).add(round(ToMM(t.GetWidth()), 3))

def floor_of(n):
    xs = [p[0] for p in pins[n]]
    ys = [p[1] for p in pins[n]]
    return (max(xs) - min(xs)) + (max(ys) - min(ys))        # half-perimeter, rectilinear floor for the wire


def ratio_of(n):
    f = floor_of(n)
    return wire.get(n, 0.0) / f if f > 0.3 else 0.0


print(f"{'net':12s} {'pins':>4s} {'wire mm':>8s} {'floor mm':>8s} {'ratio':>6s} {'vias':>4s}  layers (mm)           note")
for n in sorted((k for k in pins if k != "GND"), key=lambda k: -ratio_of(k)):
    w = wire.get(n, 0.0)
    lay = " ".join(f"{k}:{v:.1f}" for k, v in sorted(layers.get(n, {}).items()))
    warn = " <-- detour" if ratio_of(n) > 1.8 and w > 4 else ""
    print(f"{n:12s} {len(pins[n]):4d} {w:8.1f} {floor_of(n):8.1f} {ratio_of(n):6.2f} {vias.get(n, 0):4d}  {lay:22s} {SENSITIVE.get(n, '')}{warn}")
print(f"\nGND: {len(pins.get('GND', []))} pins, {vias.get('GND', 0)} vias to the plane, {wire.get('GND', 0):.1f} mm of wire")
print("total vias", sum(vias.values()), "| total wire", f"{sum(wire.values()):.0f} mm")
print("widths used (mm):", sorted({w for s in widths.values() for w in s}))
