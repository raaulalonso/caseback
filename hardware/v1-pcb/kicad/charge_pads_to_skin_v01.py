"""Move the two charge pads of the reference board from the watch side (F.Cu) to the skin side (B.Cu), D52.

Run it with the Python that ships with KiCad:

    $KICAD/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 charge_pads_to_skin_v01.py IN.kicad_pcb OUT.kicad_pcb

The disc now charges through its skin face: each pad is the land of a small SMD spring contact that presses on a steel
rivet in the shell floor (the design notes). Re-routing the whole board would give a different layout and every check
would have to be repeated, so this edits the reference board where it touches the two nets:

  * the F.Cu pads CP1 (GND) and CP2 (VIN_RAW) and the F.Cu copper that belonged to them are removed,
  * two 2.0 x 2.0 mm pads on B.Cu are placed at the same (x, y) with the same names,
  * CP2 lands on the VIN_RAW track that already runs under it on B.Cu; CP1 gets a short B.Cu track to the ground via
    that the old F.Cu track went to.

`netlist_v01.py` and `build_v01_pcb.py` describe the same change, so a rebuild from scratch gives the same pads.
"""

from __future__ import annotations

import sys

import pcbnew
from pcbnew import FromMM, ToMM, VECTOR2I

SRC, DST = sys.argv[1], sys.argv[2]
PAD_SIZE = 2.0
PADS = {"CP1": (-3.0, -12.0, "GND"), "CP2": (3.0, -12.0, "VIN_RAW")}
GND_VIA = (-0.5, -11.95)          # the via the old F.Cu ground track ended on; it joins the inner ground plane

b = pcbnew.LoadBoard(SRC)


def P(x, y):
    return VECTOR2I(FromMM(x), FromMM(-y))


def mmx(p):
    return ToMM(p.x), -ToMM(p.y)


tracks = list(b.GetTracks())      # read before anything is removed: KiCad's track list is not valid after a removal

# 2. remove the F.Cu copper that served them: the tracks of the two nets next to the pads, and the via beside CP2 that
#    only joined that track to the B.Cu one (the skin-side pad takes over)
doomed = []
for t in tracks:
    if t.GetClass() == "PCB_VIA":
        x, y = mmx(t.GetPosition())
        if abs(x - 3.815) < 0.01 and abs(y + 11.293) < 0.01:
            doomed.append(t)
        continue
    ends = [mmx(t.GetStart()), mmx(t.GetEnd())]
    if t.GetLayer() == pcbnew.F_Cu and t.GetNetname() in ("GND", "VIN_RAW") \
            and all(-3.1 <= x <= 3.9 and -12.1 <= y <= -11.2 for x, y in ends):
        doomed.append(t)

old_pads = [fp for fp in b.GetFootprints() if fp.GetReference() in PADS]   # the F.Cu pads, found before the new ones exist

# 3. new pads on B.Cu
for ref, (x, y, nname) in PADS.items():
    fp = pcbnew.FOOTPRINT(b)
    fp.SetLayer(pcbnew.B_Cu)          # a one-pad footprint: the layer of the footprint and of its pad agree
    fp.SetReference(ref)
    fp.SetValue("charge land for SMD spring contact")
    fp.Reference().SetVisible(False)
    fp.Value().SetVisible(False)
    pad = pcbnew.PAD(fp)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    pad.SetNumber("1")
    pad.SetShape(pcbnew.PAD_SHAPE_ROUNDRECT)
    pad.SetRoundRectRadiusRatio(0.12)
    pad.SetSize(VECTOR2I(FromMM(PAD_SIZE), FromMM(PAD_SIZE)))
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.B_Cu)
    ls.AddLayer(pcbnew.B_Mask)
    pad.SetLayerSet(ls)
    pad.SetNet(b.FindNet(nname))
    fp.Add(pad)
    fp.SetPosition(P(x, y))
    b.Add(fp)

# 4. B.Cu track from the ground via to the CP1 pad
t = pcbnew.PCB_TRACK(b)
t.SetLayer(pcbnew.B_Cu)
t.SetStart(P(*GND_VIA))
t.SetEnd(P(-3.0, -11.95))
t.SetWidth(FromMM(0.2))
t.SetNet(b.FindNet("GND"))
b.Add(t)

# the removals come last: after a removal KiCad's Python wrappers lose their types. The zones are refilled by the DRC run
# (kicad-cli pcb drc --refill-zones --save-board), which is how the check script saves the board.
removed = len(doomed)
for t in doomed:
    b.Remove(t)

for fp in old_pads:
    b.Remove(fp)
print("removed", removed, "tracks and vias and", len(old_pads), "pads on F.Cu")
b.Save(DST)
print("saved", DST)
