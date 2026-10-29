#!/bin/zsh
# usage: pcbcheck.sh DIR [FILE]
# Runs KiCad's DRC (every severity, zones refilled) on DIR/FILE (default caseback_v01.kicad_pcb), prints the count per
# violation type and renders the skin and watch faces as PNG (needs PyMuPDF for svgpng.py).
# KICAD_CLI overrides the path of kicad-cli.
D=$1; F=${2:-caseback_v01.kicad_pcb}; B=${F%.kicad_pcb}
K=${KICAD_CLI:-$HOME/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}
HERE=${0:A:h}
cd $D || exit 1
$K pcb drc --severity-all --format json -o drc.json --units mm --refill-zones --save-board $F >/dev/null 2>&1
python3 -I - <<'PY'
import json, collections
d = json.load(open("drc.json"))
c = collections.Counter(v["type"] for v in d["violations"])
print("DRC:", dict(c), "| unconnected", len(d.get("unconnected_items", [])))
seen = set()
for v in d["violations"]:
    if v["type"] in ("unconnected_items",):
        continue
    key = (v["type"], tuple(sorted(i["description"][:40] for i in v["items"])))
    if key in seen:
        continue
    seen.add(key)
    if len(seen) > 14:
        break
    print(" ", v["type"], "|", v["description"][:70], "|", " / ".join(i["description"][:45] for i in v["items"][:2]), v["items"][0]["pos"])
PY
$K pcb export svg --layers "B.Cu,B.Mask,Edge.Cuts" --mirror --exclude-drawing-sheet --page-size-mode 2 -o $B-skin.svg $F >/dev/null 2>&1
$K pcb export svg --layers "F.Cu,F.Mask,F.SilkS,Edge.Cuts" --exclude-drawing-sheet --page-size-mode 2 -o $B-watch.svg $F >/dev/null 2>&1
python3 -I $HERE/svgpng.py $B-skin.svg $B-skin.png 1500 2>/dev/null
python3 -I $HERE/svgpng.py $B-watch.svg $B-watch.png 1500 2>/dev/null
