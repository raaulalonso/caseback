"""Compare the netlist of the schematic with the nets of the board.

    $KICAD/.../python3 compare_netlists_v01.py [BOARD.kicad_pcb] [SCHEMATIC.kicad_sch]

The schematic's netlist is exported with kicad-cli (kicadsexpr); the board is read with pcbnew. Every connected pad of
the board must appear on the same net in the schematic, and the other way round. Prints the differences, or "match".
"""

import os
import re
import subprocess
import sys
import tempfile

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "caseback_v01.kicad_pcb")
SCH = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "caseback_v01.kicad_sch")
KICAD_CLI = os.environ.get("KICAD_CLI", os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"))

out = os.path.join(tempfile.mkdtemp(), "sch.net")
subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out, SCH], check=True, capture_output=True)
text = open(out).read()
sch = {}
nets = text[text.index("(nets"):]
for m in re.finditer(r'\(net\s+\(code "\d+"\)\s+\(name "([^"]*)"\)(.*?)\n\t\t\)', nets, re.S):
    name = m.group(1)
    for n in re.finditer(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', m.group(2)):
        if not name.startswith("unconnected-"):          # KiCad names the single-pin nets of no-connect flags like this
            sch[(n.group(1), n.group(2))] = name.lstrip("/")

board = pcbnew.LoadBoard(BOARD)
pcb = {}
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname():
            pcb[(fp.GetReference(), p.GetNumber())] = p.GetNetname()

diff = 0
for k in sorted(set(pcb) | set(sch)):
    a, b = pcb.get(k), sch.get(k)
    if a != b:
        diff += 1
        print(f"  {k[0]}.{k[1]}: board {a}, schematic {b}")
print(f"{len(pcb)} connected pads on the board, {len(sch)} nodes in the schematic:", "match" if not diff else f"{diff} differences")
