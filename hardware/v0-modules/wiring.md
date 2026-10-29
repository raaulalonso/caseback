# Caseback V0 Wiring (nRF52840 DK → sensors)

> **Correction (2026-09-30 review).** The MAX86140/41 has an **SPI-only** interface (SCLK, SDO, SDI, CSB, plus `INT`),
> a 1.8 V core supply and a 3.1–5.5 V LED supply. Earlier revisions of this page put it on the I²C bus at 0x57 (that is
> the MAX30101/30102 address). Only the BMI270 is on I²C. Pin numbers for the SPI lines and the interrupt come from the
> firmware overlay (`firmware/caseback-fw/boards/nrf52840dk_nrf52840.overlay`) and must be checked against the nRF52840 DK
> user guide before wiring.

## Power

| Net | Source | Notes |
|-----|--------|-------|
| `VBAT` | LiPo+ (through PCM) | 3.0–4.2 V |
| `3V3` | AP2112K-3.3 from `VBAT` | Rail for the IMU and NTC on the jig only; the wearable drops this LDO (55 µA Iq), see BOM 3b |
| `1V8` | Regulator or the breakout's own | MAX86140 `VDD_ANA`/`VDD_DIG` (core supply) |
| `VLED` | `VBAT` | MAX86140 LED supply, 3.1–5.5 V; a green LED plus driver headroom may not reach 40–62 mA below ~3.6 V |
| `GND` | Common | |
| DK `VDD` | USB from PC | **Leave DK rail separate** during first power-up; common GND only |

After rails are validated, power the DK `VDD OUT` from `3V3` for portable jig.

## SPI bus (PPG AFE)

| Signal | DK Arduino-header name | MAX86140 | Notes |
|--------|------------------------|----------|-------|
| `SCK` | `D13` | `SCLK` | Zephyr `arduino_spi` |
| `MOSI` | `D11` | `SDI` | |
| `MISO` | `D12` | `SDO` | |
| `CS` | `D10` | `CSB` | active low |
| `PPG_INT` | `D9` | `INT` | open-drain, active low; needs a pull-up. Not P0.08: that pin is the DK's UART RXD |

- Logic levels: the AFE I/O follows its 1.8 V supply; use a level shifter or an AFE breakout that has one when the DK
  runs at 3.3 V.
- Bench path for the AFE is decision D1. The MAX86140EVSYS is a USB evaluation system
  for a PC GUI; do not assume it plugs into the DK's SPI pins. A MAX30101 breakout (green + red + IR LED, I²C 0x57)
  is the cheap way to validate green-LED wrist PPG in the meantime.

## I²C bus (BMI270, 3.3 V)

| Signal | nRF52840 DK pin | BMI270 Qwiic | NTC |
|--------|-----------------|--------------|-----|
| `SDA` | **P0.26** (Arduino header `SDA`) | SDA (Qwiic) | — |
| `SCL` | **P0.27** (Arduino header `SCL`) | SCL (Qwiic) | — |
| `3V3` | VDD | VCC | top of divider |
| `GND` | GND | GND | bottom of divider |

- Pull-ups: 2.2–4.7 kΩ to `3V3` (Qwiic boards often have them).
- BMI270 address `0x68` (SDO low).

## IMU configuration (power)

Enable the BMI270 accelerometer only (`PWR_CTRL.acc_en=1`, `gyr_en=0`, low-power mode, 25 Hz): 10 µA. With the gyro on it is
420 µA, more than the whole rest of the system. The advanced features (step counter, wrist wear, any/no-motion) add ~3 µA.

## ADC / temp

| Signal | Pin | Circuit |
|--------|-----|---------|
| `NTC` | **P0.03** (AIN1 / `A0`) | `NTC_PWR` (a GPIO, high only while measuring) — 10k NTC — `NTC_NODE` — 10k fixed — `GND` |

Do **not** tie the divider to the always-on `3V3` rail: 3.3 V / 20 kΩ is ~165 µA continuously, four times the whole
system floor. Drive it from a GPIO, wait for it to settle, sample `NTC_NODE` with SAADC, then release the pin. Use the
SAADC's supply-referenced (ratiometric) setting where the firmware allows it, so the rail's tolerance does not become
temperature error. Convert with beta-parameter or Steinhart-Hart.

## Charge status (optional in V0 jig)

| Signal | Pin | Circuit |
|--------|-----|---------|
| `CHG_STAT` | **P0.11** (shared with DK Button 1; move to a free pin if it interferes) | MCP73831 `STAT` is tri-state (low while charging, high toward the USB-side supply when done, high-impedance in shutdown; from memory, check the datasheet). Do not connect it straight to the nRF pin: use a divider (e.g. 100 k + 47 k to GND) or a small transistor so it can never exceed the nRF's 3.3 V. |

## Battery / charge

```
USB 5V ── MCP73831 ── VBAT ── AP2112K-3.3 ── 3V3   (jig only)
              │              │
             PROG            10uF + 100nF
```

`R_PROG` sets the charge current, I ≈ 1000 V / R_PROG. Choose it for the cell, at 1C or less (0.5C is the usual standard
rate for micro cells); the part's minimum programmable current is about 15 mA (from memory):

| Cell | R_PROG | Current |
|------|--------|---------|
| ~16 mAh (V1 concept) | 62 kΩ | ~16 mA (1C) |
| ~45 mAh | 47 kΩ / 22 kΩ | ~21 mA (0.5C) / ~45 mA (1C) |
| 50–100 mAh V0 | 20 kΩ – 10 kΩ | 50–100 mA |

Pogo pads: `VBAT+` / `GND` on the disc (non-magnetic); series 0 Ω on the device for the first smoke test. The disc holds no
magnet and no ferromagnetic part, so the puck cannot hold or align it: give the puck mechanical keying (decision D11).
Two contacts at battery voltage on the skin face are a known risk (sweat, corrosion, nickel in ENIG): connect the battery
only after charger detection and prefer contacts away from the skin.

## Nordic DK pin map (quick)

| Function | Pin | Arduino-style |
|----------|-----|---------------|
| I2C SDA | P0.26 | SDA |
| I2C SCL | P0.27 | SCL |
| SPI SCK / MOSI / MISO | P1.15 / P1.13 / P1.14 (overlay; verify) | D13 / D11 / D12 |
| PPG CS | P1.12 (overlay; verify) | D10 |
| PPG_INT | P1.11 (overlay; verify) | D9 |
| NTC ADC | P0.03 | A0 |
| CHG_STAT | P0.11 | Button 1 (shared) |
| Status LED | P0.13 | LED1 |

## Bring-up order

1. Power **DK from USB only**, sensors unpowered → blink LED.
2. Common GND, power BMI270 Qwiic from DK `3V3` → I²C scan expect `0x68`.
3. Add the AFE on SPI (breakout or eval, per D1) with its 1.8 V and LED rails → read the PART_ID register over SPI
   (value and transaction format in the MAX86140/41 datasheet; the firmware probe logs it).
4. Add NTC divider (GPIO-powered) → print mV vs room temp.
5. Power from LiPo + MCP73831 (USB power meter) → verify 3V3 and charge LED.
6. Enable BLE advertising `Caseback-XXXX` and GATT INFO.
