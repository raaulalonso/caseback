"""Write caseback_v01.kicad_sch from netlist_v01.py and the pad assignment of the module in the board.

    $KICAD/.../python3 build_v01_sch.py [BOARD.kicad_pcb] [OUT.kicad_sch]

The schematic is a netlist drawing: every IC is a box with all its connected pins, and a net label sits on every pin
end, so a reviewer can check each pin against its datasheet. Passives sit in a column under the IC they serve, with
a label on each end. All pins are typed passive, so the electrical rules check says little; what it is for is the
netlist, which kicad-cli exports and compares with the board (compare_netlists_v01.py).
"""

import os
import re
import sys
import uuid

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import netlist_v01 as N  # noqa: E402

BOARD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "caseback_v01.kicad_pcb")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "caseback_v01.kicad_sch")
SYMBOLS = os.path.join(HERE, "lib", "lcsc_symbols")
DEVICE = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/Device.kicad_sym")
ROOT = str(uuid.uuid5(uuid.NAMESPACE_URL, "caseback-v01-root"))


def snap(v):
    """Everything sits on the 1.27 mm connection grid."""
    return round(v / 1.27) * 1.27


def uid(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "caseback-v01/" + "/".join(parts)))


def symbol_uuid(ref):
    """The id of the symbol of a reference; the board builder gives each footprint the same one as its path."""
    return uid("symbol", ref)


def lcsc_pins(code):
    s = open(os.path.join(SYMBOLS, code + ".kicad_sym")).read()
    return {m.group(2): m.group(1) for m in re.finditer(
        r'\(pin \w+ \w+\s+\(at [-\d.]+ [-\d.]+ [-\d.]+\)\s+\(length [-\d.]+\)\s+\(name "([^"]*)".*?\(number "([^"]*)"', s, re.S)}


def device_block(name):
    s = open(DEVICE).read()
    i = s.index(f'(symbol "{name}"')
    depth = 0
    for j in range(i, len(s)):
        depth += (s[j] == "(") - (s[j] == ")")
        if depth == 0:
            return s[i:j + 1].replace(f'(symbol "{name}"', f'(symbol "Device:{name}"', 1)


FONT = "(effects (font (size 1.27 1.27)))"


def ic_symbol(lib_name, pins, ref_prefix="U"):
    """Box symbol: pins is a list of (number, name). Left half and right half, 2.54 mm apart, all passive."""
    n = len(pins)
    left = pins[:(n + 1) // 2]
    right = pins[(n + 1) // 2:]
    rows = max(len(left), len(right))
    h = rows * 2.54 + 2.54
    w = 30.48
    body = [f'\t\t(symbol "{lib_name.split(":")[1]}_0_1"\n\t\t\t(rectangle (start {-w / 2:.2f} {h / 2:.2f}) (end {w / 2:.2f} {-h / 2:.2f})'
            f' (stroke (width 0.254) (type default)) (fill (type background))))']
    pin_txt = []
    for side, group in ((0, left), (1, right)):
        for i, (num, name) in enumerate(group):
            y = (len(group) - 1) / 2 * 2.54 - i * 2.54 if len(group) > 1 else 0
            x, ang = (-(w / 2 + 5.08), 0) if side == 0 else ((w / 2 + 5.08), 180)
            pin_txt.append(f'\t\t\t(pin passive line (at {x:.2f} {y:.2f} {ang}) (length 5.08) (name "{name}" {FONT}) (number "{num}" {FONT}))')
    body.append(f'\t\t(symbol "{lib_name.split(":")[1]}_1_1"\n' + "\n".join(pin_txt) + "\n\t\t)")
    text = (f'\t(symbol "{lib_name}"\n\t\t(exclude_from_sim no) (in_bom yes) (on_board yes)\n'
            f'\t\t(property "Reference" "{ref_prefix}" (at 0 {h / 2 + 2.54:.2f} 0) {FONT})\n'
            f'\t\t(property "Value" "" (at 0 {-h / 2 - 2.54:.2f} 0) {FONT})\n'
            f'\t\t(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'\t\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            + "\n".join(body) + "\n\t)")
    positions = {}
    for side, group in ((0, left), (1, right)):
        for i, (num, name) in enumerate(group):
            y = (len(group) - 1) / 2 * 2.54 - i * 2.54 if len(group) > 1 else 0
            positions[num] = ((-(w / 2 + 5.08) if side == 0 else (w / 2 + 5.08)), y, side)
    return text, positions, h


class Sheet:
    def __init__(self):
        self.lib_symbols = []
        self.items = []
        self.counter = 0

    def add(self, text):
        self.items.append(text)

    def label(self, net, x, y, side):
        """Net label whose anchor is the pin end; the text runs away from the part."""
        ang, just = (180, "right") if side == 0 else (0, "left")
        self.add(f'\t(label "{net}" (at {x:.2f} {y:.2f} {ang}) (effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid "{uid("label", str(self.counter))}"))')
        self.counter += 1

    def no_connect(self, x, y):
        self.add(f'\t(no_connect (at {x:.2f} {y:.2f}) (uuid "{uid("nc", str(self.counter))}"))')
        self.counter += 1

    def text(self, s, x, y, size=1.27):
        self.add(f'\t(text "{s}" (exclude_from_sim no) (at {x:.2f} {y:.2f} 0) (effects (font (size {size} {size})) (justify left top)) (uuid "{uid("text", str(self.counter))}"))')
        self.counter += 1

    def instance(self, lib_id, ref, value, x, y, rot, footprint, extra, pins):
        x, y = snap(x), snap(y)
        props = [("Reference", ref, x, y - 6), ("Value", value, x, y + 6), ("Footprint", footprint, x, y), ("Datasheet", "", x, y)]
        props += [(k, v, x, y) for k, v in extra.items()]
        ptxt = []
        for k, v, px, py in props:
            hide = " (hide yes)" if k not in ("Reference", "Value") else ""
            ptxt.append(f'\t\t(property "{k}" "{v}" (at {px:.2f} {py:.2f} 0) (effects (font (size 1.27 1.27)){hide}))')
        pin_ids = "\n".join(f'\t\t(pin "{p}" (uuid "{uid("pin", ref, p)}"))' for p in pins)
        self.add(f'\t(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} {rot}) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)\n'
                 f'\t\t(uuid "{symbol_uuid(ref)}")\n' + "\n".join(ptxt) + "\n" + pin_ids + "\n"
                 f'\t\t(instances (project "caseback_v01" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n\t)')


def module_pads():
    """Pad -> (net, name) of the module as routed: the signals were given to GPIO pads by the board builder."""
    board = pcbnew.LoadBoard(BOARD)
    u5 = next(f for f in board.GetFootprints() if f.GetReference() == "U5")
    names = lcsc_pins("C5264268")
    return {p.GetNumber(): (p.GetNetname(), names.get(p.GetNumber(), "")) for p in u5.Pads() if p.GetNetname()}


def build():
    sh = Sheet()
    nets_by_pin = {ref: dict(pins) for ref, pins in N.PINS.items()}
    u5 = module_pads()
    nets_by_pin["U5"] = {pad: net for pad, (net, _) in u5.items()}

    sheet = []
    lib_blocks = [device_block("R"), device_block("C")]
    pad_lib = ('\t(symbol "Caseback:Pad"\n\t\t(exclude_from_sim no) (in_bom no) (on_board yes)\n'
               f'\t\t(property "Reference" "J" (at 0 3.81 0) {FONT})\n\t\t(property "Value" "" (at 0 -3.81 0) {FONT})\n'
               '\t\t(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
               '\t\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
               '\t\t(symbol "Pad_0_1" (rectangle (start -1.27 1.27) (end 1.27 -1.27) (stroke (width 0.254) (type default)) (fill (type background))))\n'
               f'\t\t(symbol "Pad_1_1" (pin passive line (at -3.81 0 0) (length 2.54) (name "1" {FONT}) (number "1" {FONT})))\n\t)')
    lib_blocks.append(pad_lib)

    # layout: ICs in two rows, passives in a column under the IC they serve
    cells = {"U1": (55, 50), "U2": (150, 50), "U3": (235, 50), "U4": (310, 50),
             "U5": (60, 160), "U6": (160, 150), "U7": (235, 150), "Q1": (305, 150), "D1": (365, 150)}
    served = {}
    for ref, (value, na, nb, near, role) in N.PASSIVES.items():
        host = near[0]
        if ref in ("R8", "R9", "C16"):
            host = "U5"
        served.setdefault(host, []).append(ref)

    for ref, (value, lcsc, fp, side) in N.PARTS.items():
        names = lcsc_pins(lcsc)
        if ref == "U5":
            pins = sorted(((p, u5[p][1] or names.get(p, p)) for p in u5), key=lambda t: (t[1] != "VCC_nRF", t[1].startswith("VSS"), int(t[0])))
        else:
            allpads = sorted(names, key=lambda p: (len(p), p))
            pins = [(p, names[p]) for p in allpads if p in nets_by_pin[ref] or ref in ("U1", "U2", "U3", "U4", "U6", "U7", "Q1", "D1")]
        lib_name = f"Caseback:{ref}_{re.sub(r'[^A-Za-z0-9]', '', value)}"
        text, positions, h = ic_symbol(lib_name, pins)
        lib_blocks.append(text)
        x, y = snap(cells[ref][0]), snap(cells[ref][1])
        sh.instance(lib_name, ref, value, x, y, 0, f"caseback:{fp}", {"LCSC": lcsc}, [p for p, _ in pins])
        for num, (px, py, side_) in positions.items():
            net = nets_by_pin[ref].get(num)
            sx, sy = x + px, y - py
            if net:
                sh.label(net, sx, sy, side_)
            else:
                sh.no_connect(sx, sy)
        # passives under the IC
        for k, pref in enumerate(sorted(served.get(ref, []), key=lambda r: (r[0], int(r[1:])))):
            pv, na, nb, near, role = N.PASSIVES[pref]
            col = k // 8
            row = k % 8
            px, py = snap(x + col * 55), snap(y + h / 2 + 18 + row * 7.62)
            lib = "Device:C" if pref.startswith("C") else "Device:R"
            code = (N.CAPS if pref.startswith("C") else N.RES)[pv]
            sh.instance(lib, pref, pv, px, py, 90, "caseback:0402", {"LCSC": code}, ["1", "2"])
            sh.label(na, px - 3.81, py, 0)
            sh.label(nb, px + 3.81, py, 1)
            sh.text(role, px - 3, py + 1.8, 1.0)

    # board pads: contacts, cell, programming
    for k, (ref, (net, shape, x, y, size)) in enumerate(sorted(N.PADS.items())):
        px, py = snap(365 + (k // 6) * 30), snap(40 + (k % 6) * 12)
        sh.instance("Caseback:Pad", ref, net, px, py, 0, "caseback:pad", {}, ["1"])
        sh.label(net, px - 3.81, py, 0)
    sh.text("Pads: CP1/CP2 charge lands on the skin side, under the SMD spring contacts, BT1/BT2 cell tabs (polarity to confirm on the cell), SWD1..4 programming", 330, 28, 1.0)

    sh.text("Caseback V0.1 - netlist drawing generated from netlist_v01.py. Unused pads of the module are left out of its symbol.", 15, 15, 1.5)
    sh.text("U5 pin names and the supply range are from the LCSC symbol: check them against the ISP1807 datasheet before ordering.", 15, 20, 1.2)

    out = ['(kicad_sch\n\t(version 20250114)\n\t(generator "caseback_v01")\n\t(generator_version "1.0")\n'
           f'\t(uuid "{ROOT}")\n\t(paper "A3")\n\t(title_block (title "Caseback V0.1") (date "2026-10-28") (rev "0.1"))\n\t(lib_symbols']
    out += lib_blocks
    out.append("\t)")
    out += sh.items
    out.append('\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)')
    open(OUT, "w").write("\n".join(out) + "\n")
    print("written", OUT, f"({len(N.PARTS)} ICs, {len(N.PASSIVES)} passives)")


if __name__ == "__main__":
    build()
