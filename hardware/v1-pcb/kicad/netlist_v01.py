"""Caseback V0.1: parts, pins and nets, in one place.

The PCB builder (build_v01_pcb.py) and the schematic builder both read this file, so the board and the schematic cannot
disagree. Pin names and numbers follow the datasheets read for this project (SFH 7072 v1.6, MAX86140/86141, BQ25100
family SLUSBV8C, BMI270, TMP117) and the LCSC symbols, which were compared with those datasheets pin by pin. The
ISP1807 pad list follows its datasheet (the user manual of the module, 21 pages).

Plain Python, no dependencies.
"""

from __future__ import annotations

# ref: (value, LCSC code, footprint name in lib/lcsc.pretty or a KiCad library ("Lib:Name"), side)
# side "B" = skin side (all ICs), "F" = watch side
PARTS = {
    "U1": ("MAX86141ENP+T", "C5328762", "BGA-20_L2.0-W1.8-R4-C5-P0.40-TL", "B"),
    "U2": ("SFH 7072", "C2655172", "DFN-12_L7.5-W3.9-P1.20-BL", "B"),
    "U3": ("BMI270", "C2836813", "LGA-14_L3.0-W2.5-P0.50-BR", "B"),
    "U4": ("TMP117MAIDRVR", "C2803242", "WSON-6_L2.0-W2.0-P0.65-BL-EP", "B"),
    "U5": ("ISP1807-LR-RS", "C5264268", "BULETM-SMD_ISP1807", "B"),
    "U6": ("BQ25101YFPR", "C478468", "DSBGA-6_L0.9-W1.6-R2-C3-P0.40-BL", "B"),
    "U7": ("TLV75518PDQNR", "C2867154", "X2SON-4_L1.0-W1.0-P0.65-TL-EP", "B"),
    "Q1": ("DMG1013T-7", "C96676", "SC-75-3_L1.6-W0.8-P1.00-LS1.6-BR", "B"),
    "D1": ("TPD1E10B06DPYR", "C48260", "X1SON-2_L1.0-W0.6-P0.65-BI-1", "B"),
}

# passives: ref: (value, LCSC code, package, net a, net b, placed near (ref, pad), role)
CAPS = {"100n": "C1525", "1u": "C52923", "2.2u": "C12530", "4.7u": "C23733", "10u": "C15525"}
RES = {"0": "C17168", "2.2": "C25101", "4.7k": "C25900", "10k": "C25744", "13k": "C25754", "47k": "C25792", "100k": "C25741", "750k": "C122545", "1M": "C26083"}

PASSIVES = {
    "C1": ("100n", "V18", "GND", ("U1", "D2"), "VDD_ANA bypass"),
    "C2": ("10u", "V18", "GND", ("U1", "D2"), "VDD_ANA bulk"),
    "C3": ("1u", "VREF", "GND", ("U1", "B5"), "VREF decoupling"),
    "C4": ("100n", "V18", "GND", ("U1", "C2"), "VDD_DIG bypass"),
    "C5": ("10u", "VBAT", "GND", ("U1", "A1"), "VLED bulk"),
    "C6": ("100n", "VBAT", "GND", ("U1", "A1"), "VLED bypass"),
    "R1": ("2.2", "LED1_G1", "LED1", ("U2", "6"), "ballast, green 1"),
    "R2": ("2.2", "LED1_G2", "LED1", ("U2", "12"), "ballast, green 2"),
    "R5": ("100k", "V18", "AFE_INT", ("U1", "B2"), "INT pull-up"),
    "C7": ("100n", "V18", "GND", ("U4", "5"), "TMP117 supply"),
    "R3": ("4.7k", "V18", "I2C_SCL", ("U4", "1"), "I2C pull-up"),
    "R4": ("4.7k", "V18", "I2C_SDA", ("U4", "6"), "I2C pull-up"),
    "C8": ("100n", "V18", "GND", ("U3", "8"), "BMI270 VDD"),
    "C9": ("100n", "V18", "GND", ("U3", "5"), "BMI270 VDDIO"),
    "C10": ("1u", "VIN_CHG", "GND", ("U6", "A2"), "charger input"),
    "C11": ("2.2u", "VBAT", "GND", ("U6", "A1"), "charger output"),
    "R6": ("13k", "ISET", "GND", ("U6", "B2"), "charge current, about 10 mA"),
    "R7": ("10k", "TS", "GND", ("U6", "B1"), "no thermistor on the cell"),
    "C12": ("1u", "VBAT", "GND", ("U7", "4"), "LDO input"),
    "C13": ("1u", "V18", "GND", ("U7", "1"), "LDO output"),
    "C14": ("4.7u", "V18", "GND", ("U5", "26"), "module supply"),
    "C15": ("100n", "V18", "GND", ("U5", "26"), "module supply"),
    # 4.2 V x 750k / 1.75M = 1.8 V at the pad: the module's analog inputs stop at VDD + 0.3 V, so a 1M / 1M divider (2.1 V) is too high
    "R8": ("1M", "VBAT", "VBAT_SENSE", ("U5", "26"), "battery divider"),
    "R9": ("750k", "VBAT_SENSE", "GND", ("U5", "26"), "battery divider"),
    "C16": ("100n", "VBAT_SENSE", "GND", ("U5", "26"), "divider filter"),
}

# pad -> net for every IC pad that is connected (None or missing = no connection)
PINS = {
    "U1": {"A1": "VBAT", "A2": "SPI_SCK", "A3": "SPI_MISO", "A4": "SPI_MOSI", "A5": "SPI_CS",
           "B1": "LED3", "B2": "AFE_INT", "B3": "GND", "B4": "GND", "B5": "VREF",
           "C1": "LED2", "C2": "V18", "C3": "GND", "C4": "GND", "C5": "GND",
           "D1": "LED1", "D2": "V18", "D3": "GND", "D4": "PD2_IN", "D5": "PD1_IN"},
    "U2": {"1": "PD1_IN", "2": "GND", "3": "PD2_IN", "4": "VBAT", "5": "VBAT", "6": "LED1_G1",
           "7": "VBAT", "8": "LED2", "9": "LED3", "10": "GND", "11": "VBAT", "12": "LED1_G2"},
    # BMI270 in I2C mode: CSB high selects I2C, SDO low gives address 0x68, aux pins to VDDIO, INT2/OCSB/OSDO open
    "U3": {"1": "GND", "2": "V18", "3": "V18", "4": "IMU_INT", "5": "V18", "6": "GND", "7": "GND", "8": "V18",
           "12": "V18", "13": "I2C_SCL", "14": "I2C_SDA"},
    # TMP117: ADD0 low gives 0x48, ALERT open, exposed pad left floating (and without paste) as the datasheet advises
    "U4": {"1": "I2C_SCL", "2": "GND", "4": "GND", "5": "V18", "6": "I2C_SDA"},
    "U6": {"A1": "VBAT", "A2": "VIN_CHG", "B1": "TS", "B2": "ISET", "C1": "CHG_STAT", "C2": "GND"},
    "U7": {"1": "V18", "2": "GND", "3": "VBAT", "4": "VBAT", "5": "GND"},
    # P-FET in series with the charge input: drain to the contact, source to the charger, gate to ground
    "Q1": {"1": "GND", "2": "VIN_CHG", "3": "VIN_RAW"},
    "D1": {"1": "VIN_RAW", "2": "GND"},
}

# ISP1807 (pad list from its datasheet, isp_ble_DS1807 user manual): VCC_nRF is pad 26 (1.7 to 3.6 V, 3.9 V absolute
# maximum), SWDIO 28, SWDCLK 30, every VSS pad is ground, the USB data and NFC pads stay open. OUT_ANT (20) has to be
# joined to OUT_MOD (22) "for normal operation": the module's own antenna hangs on that link, so it is the net ANT. USB is
# not used, so VBUS (12) goes to ground, which is what Nordic's staff recommend for the nRF52840 without USB.
# The signals below are matched to GPIO pads on the connector edge by the builder.
U5_FIXED = {"26": "V18", "28": "SWDIO", "30": "SWDCLK", "20": "ANT", "22": "ANT", "12": "GND"}
# pairs of neighbouring module pads in the connector row that are joined by one short wire on the skin side
U5_LINKS = [("20", "22"), ("12", "14")]
U5_SIGNALS = ["SPI_SCK", "SPI_MOSI", "SPI_MISO", "SPI_CS", "AFE_INT", "IMU_INT", "I2C_SCL", "I2C_SDA", "CHG_STAT", "VBAT_SENSE"]
U5_NEEDS_AIN = {"VBAT_SENSE"}
# the pad each signal ends up on (route_v01.py sets them before it routes): the row of GPIO pads on the connector edge,
# in the order the nets leave the board. VBAT_SENSE is on P0.03 / AIN1, an analog input.
U5_PADS = {"IMU_INT": "32", "I2C_SCL": "34", "I2C_SDA": "36", "VBAT_SENSE": "38", "SPI_SCK": "40", "SPI_MISO": "42",
           "SPI_MOSI": "44", "SPI_CS": "46", "AFE_INT": "48", "CHG_STAT": "6"}

# pads that are not parts: ref -> (net, footprint kind, x, y, size) in the disc frame (watch side, mm)
# CP1 and CP2 are on the skin side (B.Cu) since D52: each is the land of an SMD spring contact that presses on a steel rivet
# in the shell floor. The contact itself is not chosen yet, so it is not in the bill of materials.
SKIN_PADS = {"CP1", "CP2"}
PADS = {
    "CP1": ("GND", "rect", -9.0, -1.0, (2.0, 2.0)),
    "CP2": ("VIN_RAW", "rect", 9.0, -1.0, (2.0, 2.0)),
    "BT1": ("GND", "rect", -8.0, 2.3, (1.4, 1.0)),
    "BT2": ("VBAT", "rect", 8.0, 2.3, (1.4, 1.0)),
    "SWD1": ("V18", "round", -1.905, -3.0, 0.8),
    "SWD2": ("SWDIO", "round", -0.635, -3.0, 0.8),
    "SWD3": ("SWDCLK", "round", 0.635, -3.0, 0.8),
    "SWD4": ("GND", "round", 1.905, -3.0, 0.8),
}


def all_nets():
    nets = {}
    for ref, pins in PINS.items():
        for pad, net in pins.items():
            nets.setdefault(net, []).append((ref, pad))
    for ref, (v, a, b, near, role) in PASSIVES.items():
        nets.setdefault(a, []).append((ref, "1"))
        nets.setdefault(b, []).append((ref, "2"))
    for ref, (net, *_rest) in PADS.items():
        nets.setdefault(net, []).append((ref, "1"))
    for pad, net in U5_FIXED.items():
        nets.setdefault(net, []).append(("U5", pad))
    return nets


if __name__ == "__main__":
    for net, pins in sorted(all_nets().items()):
        print(f"{net:12s} {' '.join(f'{r}.{p}' for r, p in pins)}")
