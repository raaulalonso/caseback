"""Write the copper of a KiCad board to JSON: pads, wires, vias, zones, in the disc frame (mm, y up).

    $KICAD/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -I dump_copper.py BOARD.kicad_pcb OUT.json

The project PDF (tools/build_project_pdf.py) draws its figures of the layers and its table of nets from this file, so it is
kept as tools/pdf_data/board_copper.json; run this again after the board is routed again.
"""

import json
import sys

import pcbnew
from pcbnew import ToMM

LAYERS = {pcbnew.F_Cu: "F", pcbnew.In1_Cu: "I1", pcbnew.In2_Cu: "I2", pcbnew.B_Cu: "B"}

board = pcbnew.LoadBoard(sys.argv[1])
out = {"pads": [], "tracks": [], "vias": [], "zones": []}
for fp in board.GetFootprints():
    for p in fp.Pads():
        box = p.GetBoundingBox()
        out["pads"].append({
            "ref": fp.GetReference(), "n": p.GetNumber(), "net": p.GetNetname(),
            "shape": "circle" if p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE else "rect",
            "x0": ToMM(box.GetLeft()), "x1": ToMM(box.GetRight()), "y0": -ToMM(box.GetBottom()), "y1": -ToMM(box.GetTop()),
            "layers": [name for layer, name in LAYERS.items() if p.IsOnLayer(layer)],
        })
for t in board.GetTracks():
    if t.Type() == pcbnew.PCB_VIA_T:
        out["vias"].append({"net": t.GetNetname(), "x": ToMM(t.GetPosition().x), "y": -ToMM(t.GetPosition().y),
                            "d": ToMM(t.GetWidth(pcbnew.F_Cu)), "drill": ToMM(t.GetDrill())})
    else:
        a, b = t.GetStart(), t.GetEnd()
        out["tracks"].append({"net": t.GetNetname(), "layer": LAYERS.get(t.GetLayer(), "?"), "w": ToMM(t.GetWidth()),
                              "a": [ToMM(a.x), -ToMM(a.y)], "b": [ToMM(b.x), -ToMM(b.y)]})
for z in board.Zones():
    box = z.GetBoundingBox()
    out["zones"].append({"name": z.GetZoneName(), "net": z.GetNetname(), "rule_area": z.GetIsRuleArea(),
                         "layers": [name for layer, name in LAYERS.items() if z.IsOnLayer(layer)],
                         "x0": ToMM(box.GetLeft()), "x1": ToMM(box.GetRight()), "y0": -ToMM(box.GetBottom()), "y1": -ToMM(box.GetTop())})
json.dump(out, open(sys.argv[2], "w"), separators=(",", ":"))
print(f"{len(out['pads'])} pads, {len(out['tracks'])} wires, {len(out['vias'])} vias, {len(out['zones'])} zones")
