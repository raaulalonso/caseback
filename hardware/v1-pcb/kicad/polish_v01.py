"""Last edits on the routed board, none of which move routed copper: segments of zero length are dropped, the SFH 7072 pads
are cut back to the datasheet's land pattern, the antenna link
(OUT_ANT to OUT_MOD of the module) and the antenna keep-out are made to match board_v01.py (they do nothing if the build
already has them), and every via whose copper reaches into a paste opening is marked as filled and capped (IPC-4761 type
VII), so the solder does not run down the hole. The keep-out has to be empty of tracks, vias and parts: the script stops
if it is not.

    $KICAD/.../python3 polish_v01.py IN.kicad_pcb OUT.kicad_pcb

The via marking is what JLCPCB's "via-in-pad, epoxy filled and capped" option has to cover; the Gerber files do not carry it.
"""

import math
import os
import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import board_v01 as B  # noqa: E402

src, dst = sys.argv[1:3]
board = pcbnew.LoadBoard(src)
kept = []

# the pad pairs of the module that are joined by one wire (netlist_v01.U5_LINKS): the antenna link and VBUS to ground
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netlist_v01 as N  # noqa: E402

u5 = board.FindFootprintByReference("U5")
added = []
for number, nname in N.U5_FIXED.items():
    net = board.FindNet(nname)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, nname)
        board.Add(net)
    u5.FindPadByNumber(number).SetNet(net)
for na, nb in N.U5_LINKS:
    pa, pm = u5.FindPadByNumber(na), u5.FindPadByNumber(nb)
    ends = {(pa.GetPosition().x, pa.GetPosition().y), (pm.GetPosition().x, pm.GetPosition().y)}
    if any(t.Type() == pcbnew.PCB_TRACE_T and {(t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y)} == ends
           for t in board.GetTracks()):
        continue
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pa.GetPosition())
    t.SetEnd(pm.GetPosition())
    t.SetWidth(FromMM(0.3))
    t.SetLayer(pcbnew.B_Cu)
    t.SetNet(pa.GetNet())
    t.SetLocked(True)
    board.Add(t)
    added.append(f"{na}-{nb}")

# SFH 7072 land pattern as in its datasheet (v1.6): pads 0.9 x 1.0 mm, stencil openings 0.8 x 0.9 mm (EasyEDA draws 1.0 x 1.1)
for p in board.FindFootprintByReference("U2").Pads():
    p.SetSize(VECTOR2I(FromMM(0.9), FromMM(1.0)))
    p.SetLocalSolderPasteMargin(FromMM(-0.05))

# finished thickness 0.6 mm (KiCad's default is 1.6; the Gerber files do not carry it, the order form does)
board.GetDesignSettings().SetBoardThickness(FromMM(0.6))

# antenna keep-out: same rectangle as board_v01.KEEPOUTS
x0, y0, x1, y1 = B.KEEPOUTS["antenna"]
for z in board.Zones():
    if z.GetZoneName() == "antenna keep-out":
        ol = z.Outline()
        ol.RemoveAllContours()
        ol.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(FromMM(x), FromMM(-y))
inside = []
for t in board.GetTracks():
    pts = [(ToMM(t.GetPosition().x), -ToMM(t.GetPosition().y))] if t.Type() == pcbnew.PCB_VIA_T else \
          [(ToMM(t.GetStart().x), -ToMM(t.GetStart().y)), (ToMM(t.GetEnd().x), -ToMM(t.GetEnd().y))]
    if any(x0 - 0.05 <= x <= x1 + 0.05 and y0 - 0.05 <= y <= y1 + 0.05 for x, y in pts):
        inside.append((t.GetNetname(), t.GetLayerName(), pts[0]))
for fp in board.GetFootprints():
    if fp.GetReference() == "U5":
        continue
    for pad in fp.Pads():                       # the pads are the copper; the courtyard of a part may touch the keep-out
        bb = pad.GetBoundingBox()
        if not (ToMM(bb.GetRight()) < x0 or ToMM(bb.GetLeft()) > x1 or -ToMM(bb.GetTop()) < y0 or -ToMM(bb.GetBottom()) > y1):
            inside.append((fp.GetReference(), "pad " + pad.GetNumber(), None))
if inside:
    sys.exit(f"copper or parts inside the antenna keep-out: {inside}")

zero = 0
for t in list(board.GetTracks()):
    if t.Type() == pcbnew.PCB_TRACE_T and t.GetStart() == t.GetEnd():
        board.Remove(t)
        kept.append(t)
        zero += 1

# a via counts as in a paste opening when its copper disc reaches the box of a pad that has paste
marked = 0
for t in board.GetTracks():
    if t.Type() != pcbnew.PCB_VIA_T:
        continue
    reach = ToMM(t.GetWidth(pcbnew.F_Cu)) / 2
    vx, vy = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
    hit = False
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if not p.IsOnLayer(pcbnew.B_Paste):
                continue
            box = p.GetBoundingBox()
            x0, x1 = ToMM(box.GetLeft()), ToMM(box.GetRight())
            y0, y1 = ToMM(box.GetTop()), ToMM(box.GetBottom())
            dx = max(x0 - vx, 0, vx - x1)
            dy = max(y0 - vy, 0, vy - y1)
            if math.hypot(dx, dy) < reach:
                hit = True
    if hit:
        t.SetFillingMode(pcbnew.FILLING_MODE_FILLED)
        t.SetCappingMode(pcbnew.CAPPING_MODE_CAPPED)
        marked += 1

pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcbnew.SaveBoard(dst, board)
print(f"module pad links added: {added or 'none'}; keep-out set")
print(f"{zero} zero-length segments removed, {marked} vias marked filled and capped")
