# V0.1 board in KiCad

`caseback_v01.kicad_pcb` is the board, `caseback_v01.kicad_sch` its schematic, `fab/` the files for JLCPCB. The stack
of the disc is in `../board_v01.py`.

The board is made by scripts, so a change to a part or a net starts in `netlist_v01.py` and not in KiCad.

## Tools

- KiCad 10 (its `kicad-cli` and the Python that comes with it, which has `pcbnew`). The scripts look for it in
  `~/Applications/KiCad/KiCad.app`; `KICAD_CLI` overrides the path of `kicad-cli`.

### Setting the tools up again

Versions used for the board in this folder (28 October 2026):

| Tool | Version | Where it came from |
|------|---------|--------------------|
| KiCad | 10.0.7 | the macOS app, copied to `~/Applications/KiCad/` |
| KiCad MCP server | 2.8.3 (mixelpixx/KiCAD-MCP-Server, `stable`, MIT) | Cloned to `Caseback-pcb-archive/tools/kicad-mcp-server`, built with `npm ci --ignore-scripts`, with its Python requirements in a venv made from KiCad's own Python (`KICAD_PYTHON`, and `KICAD_CLI` for the DRC). Registered in Claude Code with `claude mcp add kicad`. It opens and checks the board through `pcbnew` and `kicad-cli`; the layout is still made by the scripts here |
| PyMuPDF | any recent | `pip install pymupdf`, for the PNG renders of the SVG files |
| easyeda2kicad | 1.0.1 | `pip install easyeda2kicad`, which made `lib/` from the LCSC part numbers |

`tools/pcbcheck.sh DIR [FILE]` runs the DRC and renders the two faces. The older routing runs, the tools used for them and
the second-opinion checker (KiCadRoutingTools 0.23.7, github.com/drandyhaas/KiCadRoutingTools: clearance, connectivity,
pads, odd copper) are kept outside the repository in a folder called `Caseback-pcb-archive`.

## Order

Run each script with KiCad's Python (`python3 -I script.py ...`).

1. `build_v01_pcb.py`: outline, parts, vias in pads, rules, ground plane, antenna keep-out. It made the first placement; the
   board in this folder is the source of the placement now, and the builder is not run again for a routing change.
2. `route_v01.py IN OUT`: takes off every wire and via except the vias in pads and the two links of the module, and draws
   them again (see below). It takes about 40 s.
3. `finalize_v01.py IN OUT DRC.json`: removes vias that join one layer only (the DRC report names them) and refills the zones.
4. `polish_v01.py`: the antenna link, the keep-out, the SFH 7072 pads, via filling marks, zero-length wires.
5. `build_v01_sch.py` then `compare_netlists_v01.py`: schematic from the netlist and the check against the board.
6. `audit_v01.py`: wire length and vias per net.
7. `export_jlcpcb_v01.py`: Gerber and drill zip, BOM, placement file.

### The routing

`manhattan.py` is a router that draws at 0, 45 and 90 degrees on a 0.05 mm grid and nothing else, with one width per net
class: 0.10 mm for signals, 0.15 mm for the supply and the LED nets, clearance 0.10 mm (0.15 mm at the photodiode inputs),
vias 0.30 / 0.15 mm. It searches F.Cu, In2.Cu and B.Cu; In1.Cu is the ground plane. The prices in `route_v01.py` make F.Cu
run along x and In2.Cu along y, keep turns to 45 degrees, and keep the skin side to short stubs. `route_v01.py` is the
driver that knows the board:

- the four lanes of the optics (the two photodiode inputs and the returns of two LEDs) are drawn by hand in the script as
  straight runs on F.Cu with a via in each end pad; the router only keeps away from them;
- ground pads get a short stub to a via, or a via of their own: the plane does the rest;
- then every other net, in the order of `ORDER`. A net it cannot join goes first in the next try, up to six tries;
- a via is either inside a pad or clear of it, never across its edge, and costs more inside a pad;
- vias that join one layer and wires that end in nothing are dropped at the end.

The module's signals go to the pads listed in `netlist_v01.U5_PADS` (the script sets them before routing).

It is a router written for this board with some lanes drawn by hand, not a fully hand-drawn board. The result was checked by
looking at each layer, and by the KiCad DRC, the KiCad MCP server and the second-opinion checker.

Edits to the reference board that are not a new route:

- `charge_pads_to_skin_v01.py IN.kicad_pcb OUT.kicad_pcb` moves the two charge pads from F.Cu to B.Cu (D52). It was run on
  the board of the 32 mm disc; the builder now draws the pads on B.Cu from the start, so the 25 mm board did not need it. After any edit of this kind run
  `tools/pcbcheck.sh` (it refills the zones and saves the board), then steps 5 to 7.
- `tools/dump_footprints.py BOARD OUT.json` writes the position, side and pads of every part. `placement_v01.json` is its
  output for the reference board: the 3D model of the disc and `board_v01.py` read it, so run it again after the board
  changes.
- `tools/dump_copper.py BOARD OUT.json` writes the pads, wires, vias and zones of the copper in the disc frame. 
- `tools/densify_outline.py` writes a copy of the board with the round outline made of short segments, which is the form
  KiCad's glTF export needs to give a round board.

## Data from other sources

`lib/lcsc.pretty` and `lib/lcsc_symbols` are footprints and symbols from EasyEDA/LCSC for the parts in the BOM. Their
licence is not stated; treat them as the parts' manufacturer data and check them against the datasheets before ordering.
