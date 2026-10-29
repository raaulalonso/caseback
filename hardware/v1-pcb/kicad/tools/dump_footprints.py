"""Write the placed footprints of a KiCad board as JSON, for the 3D model of the disc.

    $KICAD/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -I dump_footprints.py BOARD.kicad_pcb OUT.json

Positions are in the disc frame of board_v01.py (millimetres, y up, seen from the watch side): the y of KiCad is negated.
`side` is "skin" for B.Cu and "watch" for F.Cu. `rot` is the orientation as KiCad stores it (degrees, counter-clockwise,
for a part on B.Cu as seen from the top of the board). Pads carry their absolute position, size and angle.
"""

import json
import sys

import pcbnew
from pcbnew import ToMM

SHAPES = {
    pcbnew.PAD_SHAPE_CIRCLE: "circle",
    pcbnew.PAD_SHAPE_RECTANGLE: "rect",
    pcbnew.PAD_SHAPE_OVAL: "oval",
    pcbnew.PAD_SHAPE_ROUNDRECT: "roundrect",
}

b = pcbnew.LoadBoard(sys.argv[1])
out = []
for fp in b.GetFootprints():
    pads = []
    for p in fp.Pads():
        pos, size = p.GetPosition(), p.GetSize()
        pads.append({
            "n": p.GetNumber(), "net": p.GetNetname(), "x": ToMM(pos.x), "y": -ToMM(pos.y),
            "w": ToMM(size.x), "h": ToMM(size.y), "angle": p.GetOrientationDegrees(),
            "shape": SHAPES.get(p.GetShape(), "other"), "skin": p.IsOnLayer(pcbnew.B_Cu),
        })
    pos = fp.GetPosition()
    out.append({
        "ref": fp.GetReference(), "name": str(fp.GetFPID().GetLibItemName()), "side": "skin" if fp.GetLayer() == pcbnew.B_Cu else "watch",
        "x": ToMM(pos.x), "y": -ToMM(pos.y), "rot": fp.GetOrientationDegrees(), "pads": pads,
    })
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(len(out), "footprints")
