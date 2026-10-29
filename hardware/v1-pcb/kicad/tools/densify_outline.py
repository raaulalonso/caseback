"""Copy a board with its Edge.Cuts arcs replaced by many short lines, so the 3D export has a round outline.

    $KICAD/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 -I densify_outline.py IN.kicad_pcb OUT.kicad_pcb

KiCad's GLB export draws an arc with segments of about 1.5 mm, which shows as a polygon on a render. The copy is only for
the renders; the board in the repository is not touched.
"""

import math
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

b = pcbnew.LoadBoard(sys.argv[1])
arcs = [d for d in b.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_ARC]
made = 0
for a in arcs:
    c, r = a.GetCenter(), ToMM(a.GetRadius())
    a0 = a.GetArcAngleStart().AsDegrees()
    sweep = a.GetArcAngle().AsDegrees()
    n = max(8, int(abs(sweep) / 0.25))
    pts = [VECTOR2I(int(c.x + FromMM(r) * math.cos(math.radians(a0 + sweep * i / n))),
                    int(c.y + FromMM(r) * math.sin(math.radians(a0 + sweep * i / n)))) for i in range(n + 1)]
    for p, q in zip(pts, pts[1:]):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(p)
        s.SetEnd(q)
        s.SetWidth(FromMM(0.05))
        b.Add(s)
        made += 1
for a in arcs:           # removals last: KiCad's Python wrappers lose their types after one
    b.Remove(a)
b.Save(sys.argv[2])
print(len(arcs), "arcs ->", made, "lines")
