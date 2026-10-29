# Caseback Firmware (Zephyr)

V0 bring-up application for nRF52840 (nRF52840 DK, PCA10056; custom `caseback_v0` board later).

## What it does

- BMI270 probe on I2C (`0x68`): reads `CHIP_ID` and logs it (no assertion).
- MAX86140/41 probe on SPI: reads `PART_ID` (register `0xFF`; `0x24` = MAX86140 and `0x25` = MAX86141 per the
  datasheet's Part ID table) and logs it. The AFE has no I2C interface and no `0x57` address; the I2C scan was removed.
- BLE peripheral. Advertisement = flags + 128-bit Caseback service UUID; scan response = name
  `Caseback-XXXX` (last two bytes of the hardware id). Advertising restarts after every disconnect.
- GATT (`caseback-protocol/spec/gatt.md`, UUIDs and limits from `include/protocol.h`), one frame per ATT value:
  - **INFO** (read): an `INFO_RESPONSE` frame. `device_id` comes from `hwinfo_get_device_id()` (FICR);
    `capabilities` = only what is implemented (none yet) plus `ENCRYPTED_ONLY` when encryption is required.
  - **CONTROL** (write without response): phone-to-device frames. `INFO_REQUEST` is answered with an
    `INFO_RESPONSE` notified on **DATA**; an undecodable frame, an unknown `msg_type`, an unsupported
    request or a device-to-phone type is answered with an `ERROR` frame. The decision logic is
    `caseback_handle_control()` in `src/device.c` (host-tested); `main.c` only queues the write and lets the
    system workqueue notify, so the BT callback never blocks. A reply longer than `ATT_MTU - 3` is dropped, never truncated.
  - **DATA** (notify, with CCC).
  - INFO, CONTROL and the CCC require an encrypted link when `CONFIG_CASEBACK_REQUIRE_ENCRYPTION=y` (production).
- After connecting: ATT MTU exchange (247 requested), data length update (251) and a connection
  parameter update (1000 to 1500 ms, latency 0, timeout 6 s), all from a work item.
- Hardware watchdog (10 s) fed from the main loop, which also gives a 20 ms LED pulse every 2 s.
  A failed `bt_enable` or advertising start is logged and retried; `main` never returns.

## Configurations

| File | Use |
|------|-----|
| `prj.conf` | Bring-up on the DK: serial console and logs on, INFO readable before bonding (`CASEBACK_REQUIRE_ENCRYPTION=n`) so nRF Connect can read it. |
| `prj_production.conf` | Added with `-DEXTRA_CONF_FILE=prj_production.conf`: encrypted INFO, `SERIAL=n`, console and logs off. |

Both share: MTU 247 / 251-byte ACL buffers / data length update, SMP + bonding + settings + privacy
(RPA), preferred connection parameters 1.0 to 1.5 s, latency 0, timeout 6 s (`CASEBACK_CONN_*` in `protocol.h`, iOS limits;
the 2 s of the power design is not reachable with the iOS rules), GATT cache support, HWINFO, watchdog. The DC/DC converter is enabled in the overlay
(`&reg1`); a custom board needs the inductors.

```bash
# from a west workspace that has zephyr + nrf
west build -b nrf52840dk/nrf52840 firmware/caseback-fw --pristine
west build -b nrf52840dk/nrf52840 firmware/caseback-fw --pristine -- -DEXTRA_CONF_FILE=prj_production.conf
west flash
```

## Wiring (nRF52840 DK, Arduino header)

The overlay uses the Zephyr `arduino_i2c`, `arduino_spi` and `arduino_header` labels. The pin
numbers below are what those labels are expected to resolve to; **verify against the DK user guide**.

| Signal | Arduino | nRF pin | Note |
|--------|---------|---------|------|
| BMI270 SDA / SCL | SDA / SCL | P0.26 / P0.27 | I2C, address `0x68` (SDO low) |
| AFE SCLK | D13 | P1.15 | SPI, mode 0 assumed, 1 MHz |
| AFE SDI (MOSI) | D11 | P1.13 | |
| AFE SDO (MISO) | D12 | P1.14 | 1.8 V output, needs level shifting on a 3.3 V DK |
| AFE CSB | D10 | P1.12 | active low |
| AFE INT | D9 | P1.11 | open drain, active low; replaces P0.08, which is the DK UART RXD |

The MAX86140/41 core runs at 1.8 V (VDD 1.7 to 2.0 V) and its LED supply at 3.1 to 5.5 V, so it
cannot share the 3.3 V bus directly. The `PART_ID` command byte (`0x80` for a read) is the usual
Maxim convention and was not confirmed from the datasheet text; if the log shows `0x00`/`0xFF`,
check wiring, level shifting, SPI mode and that byte first.

## Console

115200 8N1 on the DK **J-Link VCOM UART** (`uart0`, P0.06 TX / P0.08 RX), not USB CDC. Expect:

```text
<inf> caseback: Caseback bring-up
<inf> caseback: BMI270 @0x68 CHIP_ID=0x24
<inf> caseback: AFE PART_ID=0x24 (MAX86140)
<inf> caseback: advertising as Caseback-A1B2
```

(Illustrative; the format depends on the Zephyr logging config.)

## Flash budget

nRF52840 has 1 MB of flash. With MCUboot (not yet enabled) subtract about 48 KB for the bootloader,
split the rest into two equal image slots, and keep a settings partition for bonds. Roughly
450 KB per slot before the log/history storage of decision D3 is planned. Measure the real image
size on the first build.

## Host tests

`src/protocol.c` and `src/device.c` build without Zephyr:

```bash
cc -Wall -Wextra -Werror -std=c99 -pedantic -Iinclude -o /tmp/test_protocol tests/test_protocol.c src/protocol.c
/tmp/test_protocol ../../caseback-protocol/fixtures/golden
cc -Wall -Wextra -Werror -std=c99 -pedantic -fsanitize=address,undefined -Iinclude -o /tmp/test_device tests/test_device.c src/device.c src/protocol.c
/tmp/test_device
```

## Protocol

Application payloads follow `caseback-protocol/spec/`. Reference implementations:
`caseback-protocol/python` and `apps/ios/CasebackProtocol`; the firmware implements the
same wire format in `src/protocol.c`.
