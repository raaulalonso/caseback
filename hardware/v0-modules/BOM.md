# Caseback V0 Hardware Prototype — BOM

> Bring-up path: **devkit + breakouts on a jig**, then shrink to modules in a 3D-printed disc.
> Target envelope (V0): Ø34 mm (jig 32–36). The 4.0 mm printed shell is a fit dummy (it holds a 1.5 mm cell, ~20 mAh, and no carrier PCB); the functional wearable needs ~5.5–6.5 mm. ≤12 g with battery.

## 0. Phase 1 bracelet

The first prototype does not use the nRF52840 DK, the MAX86140EVSYS or the MCP73831 below. It is a printed TPU bracelet with these parts:

| Part | Replaces | Note |
|---|---|---|
| Seeed XIAO nRF52840 | U1 (DK) | USB UF2 bootloader, built-in LiPo charger; no SWD debugger, no PPK2 yet |
| MAX30101 breakout (clone of SparkFun SEN-16474, 25 mm square) | U2 / U2c | Green, red and IR LED; its green LED may need more than 3.3 V; I2C 0x57 |
| BMI270 module with soldered pins | U3 | I2C 0x68, CS to 3V3 |
| NTC 10k (MF52 type) with a 10 kOhm resistor from an assortment | U4 | Divider on D0 |
| 2 x LiPo 401230 110 mAh | BT1 | Check for a protection board on arrival; polarity with a multimeter |
| 80 W iron kit with multimeter, resistors, breadboard, Dupont, TPU, velcro | tools | |

Firmware for this route: `firmware/prototype-recorder/recorder.ino` (Arduino, not built yet). The Zephyr firmware in `firmware/caseback-fw` still targets the DK.

Final disc, from the 2026-10-19 research: thin 12 to 30 mAh cell (1.4 to 1.7 mm, VTC or LiPol, ordered without protection), protection on the board, a thin rigid or flex board, a sealed but serviceable enclosure (D48).

## 1. Core electronics

| Ref | Part | Why | Source | Qty | Est. |
|-----|------|-----|--------|----:|-----:|
| U1 | **Nordic nRF52840 DK** (PCA10056) | Bring-up, debugger, BLE sniffer | Nordic / DigiKey / Mouser | 1 | ~$40 |
| U1b | **Raytac MDBT50Q-1MV2** (nRF52840 module, chip ant.) | Final V0 module soldered to carrier | DigiKey `MDBT50Q-1MV2` | 2 | ~$8 ea |
| U2 | **MAX86140EVSYS** (Analog Devices PPG AFE eval) | Green/IR/Red PPG AFE + LEDs. USB evaluation system for a PC GUI; check it can be read over SPI from the DK before buying (D1). | DigiKey / ADI | 1 | ~$75 |
| U2c | **MAX30101 breakout** (green + red + IR LED, I²C 0x57) | Cheapest way to validate green-LED wrist PPG; the MAX30102 has no green LED (D1) | SparkFun / Pimoroni / AliExpress | 1 | TBD |
| U2b | **MAX86140** + LED pack (V0 carrier) | Same AFE on custom FPC later. WLP 2.05 × 1.85 mm at 0.4 mm pitch, **SPI only**, 1.8 V core: not hand-solderable, needs reflow and a fine-pitch or HDI board | DigiKey | 2 | ~$6 ea |
| U3 | **SparkFun BMI270 Qwiic** (SEN-22397) | 6DoF IMU, ultralow power; run accelerometer-only, gyro off (10 µA vs 420 µA) | SparkFun | 1 | ~$15 |
| U3b | **BMI270** LGA-14 (V0 carrier) | Production IMU | Mouser | 5 | ~$3 ea |
| U4 | **NTC 10k 0402** (MF52-type or NCP15XH103) | Skin temp | DigiKey | 5 | ~$0.2 |
| BT1 | **LiPo 3.7 V 50–100 mAh** + PCM. Part-number digits are thickness × width × length (from memory): 301020 = 3.0 × 10 × 20 mm, 401230 = 4.0 × 12 × 30 mm. Confirm on the cell's datasheet; a 4.0 mm cell does not fit a 4.0 mm disc | ≥ 3 d target; the 4.0 mm shell fits only a 1.5 mm cell (~20 mAh): 301020 needs a 5.45 mm disc, 401230 6.45 mm | Adafruit / EEMB / Amazon | 2 | ~$6 |
| U5 | **MCP73831** (SOT-23-5, 4.2 V variant) | LiPo charge; set R_PROG for ≤ 1C of the cell (see `wiring.md`); needs a 4.4 V+ part for LiHV cells | DigiKey | 5 | ~$1 |
| U6 | **AP2112K-3.3** (bring-up jig only: 55 µA Iq) | 3V3 rail; not for the wearable, see below | DigiKey | 5 | ~$0.5 |
| J1 | **2-pin pogo pads** (non-magnetic; magnet stays on the puck) | Charge puck interface | AliExpress / Adafruit | 5 | ~$2 |
| J2 | **JST-PH 2.0 2-pin** | Battery connector | Adafruit | 5 | ~$0.5 |

## 2. Mechanical / wearables

| Ref | Part | Why | Source | Qty | Est. |
|-----|------|-----|--------|----:|-----:|
| M1 | **Microsuction pad** (or “nano tape” sheets). 3M 300LSE is an adhesive transfer tape (from memory): it contradicts “no glue”, so confirm what it is before ordering | Attach under caseback; needs a shear/pull-out test (D12) | Amazon / 3M | 1 roll | ~$15 |
| M2 | **TPU 95A filament** (or Resin-like PETG) | 3D-printed disc + softband | Prusa / Bambu | 1 spool | ~$25 |
| M3 | **Soft TPU strap blank** 20/22 mm + slider | Workout/night band with sensor pocket | AliExpress | 2 | ~$5 |
| M4 | **Watch caseback dummy** (steel disc Ø28–34) | Fit test jig | eBay / spare | 1 | ~$5 |

## 3. Tools (have or buy once)

| Item | Notes |
|------|-------|
| nRF52840 DK USB cable | Already with DK |
| Qwiic / STEMMA QT cable 10 cm | BMI270 |
| Hot air / fine tip iron | Module carrier |
| Caliper | Fit check vs caseback |
| 3D printer (FDM OK for V0) | Or JLCPCB 3D print |
| Multimeter + USB power meter | Battery current |
| Nordic nRF Connect + mobile app | BLE smoke test |

## 3b. Power parts for the V0.1 carrier (prices TBD)

From [battery-autonomy.md](../../docs/research/battery-autonomy.md); the jig above keeps the AP2112K because the DK powers the nRF.

- nRF52840 module fed from **VDDH** (2.5–5.5 V) with the sensors on the internal regulator, or an **nPM1100**-class PMIC
  (0.8 µA Iq). Check that the MDBT50Q-1MV2 exposes VDDH before committing.
- **Load switch** on the AFE rail (about 0.5 µA Iq, nA off) so the MAX86140 and its LEDs can be fully cut.
- **Protection IC** with ≤ 3 µA leakage instead of a generic PCM.
- No fuel-gauge IC: read VBAT through a switched divider on the ADC.
- LED rail: MAX86140 needs VLED ≥ 3.1 V; confirm a green LED reaches 20–40 mA at 3.3–3.5 V battery, otherwise budget a boost.

## 4. V0 architecture (breadboard → jig)

```
[nRF52840 DK]──SWD──► debug
     │
     ├─ SPI ── PPG AFE (SCLK/SDI/SDO/CSB + INT), 1.8 V core
     ├─ I2C ── BMI270 Qwiic
     ├─ ADC ── NTC divider (GPIO-powered)
     ├─ GPIO─ charge status (MCP73831 STAT)
     └─ BLE ── advertising "Caseback-XXXX" + GATT (caseback-protocol)
```

**Carrier board (V0.1):** 20×20 mm to 28×28 mm with MDBT50Q + BMI270 + NTC + charge IC + pogo pads (2-layer is fine without the WLP AFE). PPG sits on an eval FPC or a breakout until V1.

## 5. Budget (one jig + one wearable pilot)

| Block | Est. |
|-------|-----:|
| Devkits + evals (U1, U2, U3) | ~$130 |
| Modules + passives (U1b, U2b, U3b, U4, U5, U6) | ~$52 |
| Battery + connector + pogo (BT1, J1, J2) | ~$25 |
| Mechanical + filament (M1–M4) | ~$55 |
| **Total V0** (sum of `bom.csv`; U2c breakout not included) | **~$261** |

## 6. Do-not-buy-yet (V1)

- Custom 4-layer flex PCB
- Custom LED/optical stack
- Medical-grade ECG AFE
- Production tooling / injection mold
