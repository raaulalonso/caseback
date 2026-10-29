"""Write the files JLCPCB asks for from caseback_v01.kicad_pcb: Gerbers and drills (one zip), BOM and placement (CPL).

    $KICAD/Contents/MacOS is searched for kicad-cli; give another with KICAD_CLI.
    $KICAD/.../python3 export_jlcpcb_v01.py [BOARD.kicad_pcb] [OUT_DIR]

Every part is on the skin side (B.Cu), so the assembly is single-sided, bottom. The placement file gives positions in the
frame of the Gerbers (y up) and the angle as seen from the bottom. KiCad stores the angle of a bottom part as seen
from the top, so it is negated; JLCPCB shows every part over the board before it asks for payment, and the angle of each
part type has to be looked at there once (EasyEDA footprints and JLCPCB's own library do not always agree).
"""

import csv
import glob
import os
import shutil
import subprocess
import sys
import zipfile

import pcbnew
from pcbnew import ToMM

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import netlist_v01 as N  # noqa: E402

BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "caseback_v01.kicad_pcb")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "fab")
KICAD_CLI = os.environ.get("KICAD_CLI", os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"))
LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"


def part_table():
    """ref -> (value, LCSC code, package) for every part that is placed."""
    out = {}
    for ref, (value, lcsc, fp, side) in N.PARTS.items():
        out[ref] = (value, lcsc, fp.split("_")[0] if not ":" in fp else fp.split("_")[1])
    for ref, (value, na, nb, near, role) in N.PASSIVES.items():
        table = N.CAPS if ref.startswith("C") else N.RES
        unit = "F" if ref.startswith("C") else "ohm"
        out[ref] = (f"{value} {unit}", table[value], "0402")
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    gerber_dir = os.path.join(OUT, "gerber")
    shutil.rmtree(gerber_dir, ignore_errors=True)
    os.makedirs(gerber_dir)
    subprocess.run([KICAD_CLI, "pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "--no-x2", "-o", gerber_dir, BOARD], check=True)
    subprocess.run([KICAD_CLI, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--drill-origin", "absolute",
                    "--excellon-zeros-format", "decimal", "--generate-map", "--map-format", "gerberx2", "-o", gerber_dir + os.sep, BOARD], check=True)
    zpath = os.path.join(OUT, "caseback_v01_gerber.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(glob.glob(os.path.join(gerber_dir, "*"))):
            if not f.endswith((".pdf", ".json", ".gbrjob")):
                z.write(f, os.path.basename(f))

    board = pcbnew.LoadBoard(BOARD)
    table = part_table()
    groups = {}
    cpl = []
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        ref = fp.GetReference()
        if ref not in table:
            continue
        value, lcsc, package = table[ref]
        groups.setdefault((value, package, lcsc), []).append(ref)
        bottom = fp.GetLayer() == pcbnew.B_Cu
        rot = fp.GetOrientationDegrees()
        rot = (-rot if bottom else rot) % 360
        cpl.append((ref, ToMM(fp.GetPosition().x), -ToMM(fp.GetPosition().y), "Bottom" if bottom else "Top", rot))

    with open(os.path.join(OUT, "caseback_v01_bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (value, package, lcsc), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([value, ",".join(sorted(refs, key=lambda r: (r.rstrip("0123456789"), int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))))), package, lcsc])
    with open(os.path.join(OUT, "caseback_v01_cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for ref, x, y, layer, rot in cpl:
            w.writerow([ref, f"{x:.4f}mm", f"{y:.4f}mm", layer, f"{rot:.0f}"])
    print(f"{len(cpl)} placed parts, {len(groups)} BOM lines, {os.path.basename(zpath)}")


if __name__ == "__main__":
    main()
