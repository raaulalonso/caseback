"""Last clean-up of the routed board: drop vias that connect only one layer, move the silkscreen, refill the zones.

    $KICAD/.../python3 finalize_v01.py IN.kicad_pcb OUT.kicad_pcb DRC.json

DRC.json is the report of kicad-cli for IN (it names the dangling vias). Vias that are locked (the ones in pads) stay.
"""

import json
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I, ToMM

src, dst, drc = sys.argv[1:4]
board = pcbnew.LoadBoard(src)
report = json.load(open(drc))
dangling = [v["items"][0]["pos"] for v in report["violations"] if v["type"] == "via_dangling"]

kept = []
removed = 0
for t in list(board.GetTracks()):
    if t.Type() != pcbnew.PCB_VIA_T or t.IsLocked():
        continue
    x, y = ToMM(t.GetPosition().x), ToMM(t.GetPosition().y)
    if any(abs(x - p["x"]) < 0.01 and abs(y - p["y"]) < 0.01 for p in dangling):
        board.Remove(t)
        kept.append(t)          # keep the wrapper alive so SWIG does not free it twice
        removed += 1

for d in list(board.GetDrawings()):
    if d.Type() == pcbnew.PCB_TEXT_T and d.GetText() == "CASEBACK V0.1":
        board.Remove(d)
        kept.append(d)

filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
pcbnew.SaveBoard(dst, board)
print(f"{removed} dangling vias removed")
