# Caseback messages (proto_ver 0x01, spec v0.2)

All multi-byte integers are little-endian; all layouts are fixed unless stated. Frames are described in
[framing.md](framing.md), the transport in [gatt.md](gatt.md). `P->D` is phone to device (written to CONTROL), `D->P` is
device to phone (notified on DATA, or read from INFO). A type used in both directions has a payload layout per
direction. Anything marked *reserved* MUST be sent as zero / not sent, and receivers ignore reserved bits and reject
reserved values with `INVALID_FIELD`.

## Implementation status

| Message | Python / Swift / C codec | Notes |
|---------|:------------------------:|-------|
| INFO_REQUEST, INFO_RESPONSE | implemented | golden fixtures |
| ERROR, TIME_ANCHOR | implemented | golden fixtures |
| CONFIG_SET, CONFIG_STATE, BATTERY | implemented | golden fixtures |
| STREAM_DATA, STREAM_CONTROL | specified only | codecs in a later milestone |
| HISTORY_QUERY, HISTORY_ACK | specified only | codecs in a later milestone |

## Message types

| Range | Use |
|-------|-----|
| `0x00` | reserved (never valid) |
| `0x01`..`0x04` | session: INFO_REQUEST, INFO_RESPONSE, ERROR, TIME_ANCHOR |
| `0x05`..`0x0F` | reserved |
| `0x10`..`0x13` | data plane: STREAM_DATA, STREAM_CONTROL, HISTORY_QUERY, HISTORY_ACK |
| `0x14`..`0x1F` | reserved |
| `0x20`..`0x22` | device control: CONFIG_SET, CONFIG_STATE, BATTERY |
| `0x23`..`0x2F` | reserved |
| `0x30`..`0x3F` | reserved for standard SMP DFU (see below) |
| `0x40`..`0xFF` | reserved |

Firmware update (decision D4) uses the standard SMP/mcumgr GATT service handled by MCUboot, not Caseback frames. There is no
custom OTA message family; `0x30`..`0x3F` is reserved so that no other message claims it. `msg_type` values that are
reserved or unassigned are valid frames at the framing level; the receiver answers with `ERROR(UNKNOWN_MSG_TYPE)`.

## ErrorCode

Numeric taxonomy shared by framing errors, message-decoding errors and the ERROR message. Python (`ErrorCode`), Swift
(`ErrorCode`) and C (`enum caseback_error`) use the same names and values.

| Code | Name | Meaning |
|-----:|------|---------|
| 0x0000 | `NONE` | no error; never sent |
| 0x0001 | `TRUNCATED` | input ends before the frame does |
| 0x0002 | `BAD_MAGIC` | first byte is not `0xA5` |
| 0x0003 | `UNSUPPORTED_VERSION` | `proto_ver` is not 1 |
| 0x0004 | `PAYLOAD_TOO_LONG` | `payload_len` above 175 |
| 0x0005 | `LENGTH_MISMATCH` | bytes present differ from the declared length (trailing bytes) |
| 0x0006 | `BAD_CRC` | CRC mismatch |
| 0x0007..0x00FF | | reserved (framing) |
| 0x0100 | `UNKNOWN_MSG_TYPE` | type unassigned, or not the type this decoder handles |
| 0x0101 | `BAD_PAYLOAD_LENGTH` | payload length differs from the layout |
| 0x0102 | `INVALID_FIELD` | value out of range or reserved |
| 0x0103 | `UNSUPPORTED` | valid request for a capability the device lacks |
| 0x0104 | `WRONG_DIRECTION` | message sent in a direction where it is undefined |
| 0x0105..0x01FF | | reserved (messages) |
| 0x0200 | `LINK_NOT_ENCRYPTED` | request needs an encrypted link |
| 0x0201 | `BUSY` | try again later |
| 0x0202 | `BAD_STATE` | not valid in the current device state |
| 0x0203 | `NO_SUCH_STREAM` | unknown `stream_id` |
| 0x0204 | `CURSOR_OUT_OF_RANGE` | history cursor beyond `next_cursor` |
| 0x0205..0x02FF | | reserved (state) |
| 0x0300 | `INTERNAL` | firmware fault |
| 0x0301..0xEFFF | | reserved |
| 0xF001 | `BUFFER_TOO_SMALL` | local only, never on the wire: output buffer too small |
| 0xF002 | `NULL_ARGUMENT` | local only, never on the wire: NULL pointer with a nonzero length |
| 0xF000..0xFFFF (others) | | reserved for local errors |

Receivers preserve an unknown code from a peer as a number and do not reject the ERROR message.

## 0x01 INFO_REQUEST (P->D)

Empty payload. Answered with INFO_RESPONSE on DATA.

## 0x02 INFO_RESPONSE (D->P)

Also returned by reading the INFO characteristic. `proto_ver` is in the frame header, not in this payload.

| Offset | Type | Field |
|-------:|------|-------|
| 0..7 | u8[8] | `device_id` (from the nRF52840 FICR; only exposed on an encrypted link) |
| 8..9 | u16 | `hw_rev` (major in the high byte, minor in the low byte) |
| 10..11 | u16 | `fw_rev` (same packing; the full image version is available through SMP) |
| 12..15 | u32 | `capabilities` |

Total payload size: **16 bytes**.

### capabilities bits

Bits 0..5 keep the v0.1 positions. Bits 8..31 are reserved: senders set them to 0, receivers ignore them.

| Bit | Name | Meaning |
|----:|------|---------|
| 0 | `PPG_RAW` | raw PPG stream (STREAM_DATA stream 0x01) |
| 1 | `PPG_SUMMARY` | PPG summary and IBI stream (stream 0x03) |
| 2 | `ACCEL` | accelerometer stream (stream 0x02); named "IMU" in v0.1, no gyro is streamed |
| 3 | `SPO2` | SpO2 measurement (needs red and IR LEDs) |
| 4 | `TEMPERATURE` | skin temperature |
| 5 | `DFU_SMP` | firmware update through the standard SMP service |
| 6 | `IBI_LOG` | offline IBI/epoch log with history backfill |
| 7 | `ENCRYPTED_ONLY` | every Caseback characteristic requires an encrypted, bonded link |
| 8..31 | | reserved |

## 0x03 ERROR (D->P)

The device sends it in place of a reply when a frame or message is rejected. The phone MUST NOT send it.

| Offset | Type | Field |
|-------:|------|-------|
| 0..1 | u16 | `code` (ErrorCode) |
| 2 | u8 | `msg_type` of the offending frame (0 when it could not be read) |
| 3 | u8 | `detail`: for `INVALID_FIELD` the payload offset of the first invalid field; for `BAD_PAYLOAD_LENGTH` the expected length (saturating at 255); otherwise 0 |

Total payload size: **4 bytes**. For framing errors the device MAY drop the frame silently instead (a corrupt frame
cannot be trusted to have come from a peer that wants an answer).

## 0x04 TIME_ANCHOR (P->D and D->P)

The phone sends it right after connecting (and at least hourly); the device answers immediately. The device has no wall
clock (decision D7): every record carries `boot_id` and uptime, and the phone rebuilds UTC from the anchors. Gaps are
marked, not interpolated.

P->D request, **8 bytes**:

| Offset | Type | Field |
|-------:|------|-------|
| 0..7 | u64 | `utc_ms`: milliseconds since the Unix epoch, UTC, at the moment of sending |

D->P reply, **12 bytes**:

| Offset | Type | Field |
|-------:|------|-------|
| 0..3 | u32 | `boot_id`: random value drawn from the hardware RNG at every boot |
| 4..11 | u64 | `uptime_ms`: milliseconds since boot when the request was received |

The phone pairs the reply with its own send and receive times (midpoint of the round trip) to derive
`utc = anchor_utc + (uptime - anchor_uptime)` for a given `boot_id`. The device keeps the last `utc_ms` in RAM only.
The request and the reply are told apart by direction and by length.

## 0x10 STREAM_DATA (D->P) - specified only

Live samples, or replayed history when flag bit 0 is set. Header of **20 bytes**, then samples; at most 155 bytes of
samples so the frame stays within 182 bytes.

| Offset | Type | Field |
|-------:|------|-------|
| 0..1 | u16 | `seq`: one counter shared by all STREAM_DATA frames of a connection, 0 at connect, +1 per frame, wraps. A jump means loss, duplication or reordering |
| 2..5 | u32 | `boot_id` |
| 6..13 | u64 | `uptime_ms` of the first sample |
| 14 | u8 | `stream_id` |
| 15 | u8 | `format` (per stream, below) |
| 16 | u8 | `flags`: bit 0 `HISTORY` (replay of stored data), bit 1 `GAP_BEFORE` (samples were lost just before this frame); bits 2..7 reserved |
| 17..18 | u16 | `rate_dhz`: sample rate in 0.1 Hz for uniform streams, 0 for event streams. Sample `i` is at `uptime_ms + round(i * 10000 / rate_dhz)` ms |
| 19 | u8 | `count`: number of samples |
| 20.. | | `count` samples |

| `stream_id` | Name | `format` | Sample |
|------------:|------|---------:|--------|
| 0x01 | PPG_RAW | 1, 2 or 3 (channels) | that many u24 ADC counts, in the order green, red, IR, only for LEDs in the mask; 3, 6 or 9 bytes |
| 0x02 | ACCEL | 0x01 | s16 x, s16 y, s16 z; fixed range +-4 g, 8192 LSB/g; 6 bytes |
| 0x03 | PPG_SUMMARY | 0x01 IBI | u16 `t_off_ms` (beat time after `uptime_ms`), u16 `ibi_ms`, u8 `quality` (0..255, 255 best); 5 bytes |
| 0x03 | PPG_SUMMARY | 0x02 EPOCH | u8 `beats`, u16 `mean_ibi_ms`, u8 `quality`, u16 `activity` (accelerometer activity count); one 30 s epoch, 6 bytes, epoch `i` starts at `uptime_ms + i * 30000`; `rate_dhz` 0 |
| 0x00, 0x04..0xFF | | | reserved |

Only IBI/EPOCH records (stream 0x03) are stored offline (decision D3); raw is streamed live only.

## 0x11 STREAM_CONTROL (P->D and D->P) - specified only

Starts or stops a stream. Payload **3 bytes**, same layout both ways; the device answers with the resulting state.

| Offset | Type | Field |
|-------:|------|-------|
| 0 | u8 | `stream_id` |
| 1 | u8 | `action`: 0 stop, 1 start; others reserved |
| 2 | u8 | `format`: requested format, 0 for the mode default |

Errors: `NO_SUCH_STREAM`, `UNSUPPORTED`, `BAD_STATE`, `LINK_NOT_ENCRYPTED`.

## 0x12 HISTORY_QUERY (P->D and D->P) - specified only

The device keeps a ring log of stored STREAM_DATA frames. Each stored frame has a cursor: a u32 that increases by one
per frame and is never reused. Ack-then-erase: the device never erases a frame before it is acknowledged, but a full
log overwrites the oldest frames regardless, and says so.

P->D, **6 bytes**:

| Offset | Type | Field |
|-------:|------|-------|
| 0..3 | u32 | `cursor`: first cursor the phone still needs |
| 4..5 | u16 | `max_frames`: 0 for everything up to `next_cursor` |

D->P reply, **9 bytes**, followed by the replayed frames:

| Offset | Type | Field |
|-------:|------|-------|
| 0..3 | u32 | `first_cursor`: cursor of the first replayed frame, `max(cursor, oldest stored)` |
| 4..7 | u32 | `next_cursor`: cursor the next stored frame will get |
| 8 | u8 | `flags`: bit 0 `GAP` (frames in `[cursor, first_cursor)` were overwritten before they were acknowledged); bits 1..7 reserved |

The replayed STREAM_DATA frames (flag `HISTORY`) follow in cursor order, frame `k` has cursor `first_cursor + k`. If the
phone sees a `seq` jump it queries again from its last contiguous cursor. `cursor > next_cursor` is answered with
`ERROR(CURSOR_OUT_OF_RANGE)`. Wall time is rebuilt with the anchor stored for each frame's `boot_id`.

## 0x13 HISTORY_ACK (P->D) - specified only

Payload **4 bytes**: u32 `cursor`. Every stored frame with a cursor below it is durably saved on the phone and may be
erased. No reply (`ERROR(CURSOR_OUT_OF_RANGE)` if `cursor` is above `next_cursor`). Acknowledgements are idempotent.

## 0x20 CONFIG_SET (P->D) and 0x21 CONFIG_STATE (D->P, and P->D as a query)

CONFIG_SET and CONFIG_STATE share one **26-byte** layout. The device validates the whole payload, applies it
atomically (clamping rates and currents to what the hardware supports) and answers with CONFIG_STATE carrying the
values actually applied. An invalid payload changes nothing and is answered with `ERROR(INVALID_FIELD)` whose
`detail` is the offset of the first bad field. CONFIG_STATE with an empty payload from the phone asks for the current
state. The device SHOULD persist the last accepted configuration.

| Offset | Type | Field | Range |
|-------:|------|-------|-------|
| 0 | u8 | `mode` | 0 night, 1 day, 2 workout, 3 raw |
| 1 | u8 | `payload_format` | 0 `summary`, 1 `stream_raw` |
| 2..3 | u16 | `ppg_rate_hz[night]` | 0..400 (0 = PPG off) |
| 4..5 | u16 | `ppg_rate_hz[day]` | 0..400 |
| 6..7 | u16 | `ppg_rate_hz[workout]` | 0..400 |
| 8..9 | u16 | `ppg_rate_hz[raw]` | 0..400 |
| 10..11 | u16 | `burst_period_s` | day mode: seconds between bursts; 0 = continuous |
| 12..13 | u16 | `burst_len_s` | day mode: burst length in seconds; MUST be 0 when the period is 0, else `<= burst_period_s` |
| 14 | u8 | `led_mask` | bit 0 green, bit 1 red, bit 2 IR; bits 3..7 reserved |
| 15 | u8 | `led_green_ma` | LED current in mA, 1 mA steps |
| 16 | u8 | `led_red_ma` | mA |
| 17 | u8 | `led_ir_ma` | mA |
| 18..21 | u32 | `wear_ppg_dc` | wear detection: raw PPG DC counts above which the disc is on skin |
| 22..23 | u16 | `wear_motion_thr` | wear detection: raw accelerometer no-motion threshold, LSB |
| 24..25 | u16 | `wear_probe_period_ms` | proximity probe period; 0 disables the probe |

The thresholds are raw sensor values on purpose: they come from bench data (decision D10) and are not converted to
physical units. `payload_format` is the payload of the stream, not the mode (decision D8).

### Mode vocabulary (decision D8)

| `mode` | Meaning | Power-model profile | Typical settings |
|-------:|---------|---------------------|------------------|
| 0 night | continuous, low rate | A and B night part, C with `led_mask` red+IR | 25 Hz, `summary` |
| 1 day | bursts | A day part; `burst_period_s` = 0 gives profile B (continuous) | >= 32 Hz, 30 s every 300 s, `summary` |
| 2 workout | continuous, high rate | D workout hour | 100 Hz |
| 3 raw | raw stream | E | 100 Hz, `stream_raw` |

## 0x22 BATTERY (D->P, and P->D as a query)

Sent by the device after the link is encrypted, on a charging-state change and at most once per 60 s; the phone asks for
it with an empty payload. Payload **12 bytes**.

| Offset | Type | Field | Range |
|-------:|------|-------|-------|
| 0..1 | u16 | `voltage_mv` | battery voltage, mV |
| 2 | u8 | `charging` | 0 not charging, 1 charging, 2 charge complete, 3 fault, 0xFF unknown; others reserved |
| 3 | u8 | `percent` | 0..100 estimated state of charge, 0xFF unknown |
| 4..5 | u16 | `avg_current_ua[night]` | running average current in this mode, uA; 0xFFFF unknown |
| 6..7 | u16 | `avg_current_ua[day]` | |
| 8..9 | u16 | `avg_current_ua[workout]` | |
| 10..11 | u16 | `avg_current_ua[raw]` | |

`percent` is a voltage-based estimate and is labelled approximate in the app.

## Reference vectors

Independently derived from the layouts above (field bytes written out by hand, CRC-16/CCITT-FALSE computed with a
separate implementation, not the Caseback package). `python/tests/test_spec_vectors.py` asserts that the golden files in
`fixtures/golden/` are byte-identical to these lines. Every field value in these frames is distinct and most bytes are
above `0x7F`.

```
info_request.bin: A5 01 01 00 00 BB 59
info_response.bin: A5 01 02 10 00 8B 9C AD BE CF D0 E1 F2 02 81 04 93 C3 00 00 00 82 BB
error.bin: A5 01 03 04 00 02 01 20 0C 32 F3
time_anchor_request.bin: A5 01 04 08 00 E6 D5 C4 B3 A2 01 00 00 1B 68
time_anchor_reply.bin: A5 01 04 0C 00 CE FA DE C0 A0 B1 C2 D3 E4 00 00 00 26 9F
config_query.bin: A5 01 21 00 00 7D DF
config_set.bin: A5 01 20 1A 00 02 01 19 00 C8 00 64 00 90 01 2C 01 1E 00 05 2A 1B 21 C9 B7 05 00 F4 01 E8 03 5A FF
config_state.bin: A5 01 21 1A 00 01 00 30 00 20 00 80 00 90 01 58 02 2D 00 07 3C 34 29 FF FF 07 00 B8 0B 88 13 73 79
battery_query.bin: A5 01 22 00 00 2D 86
battery.bin: A5 01 22 0C 00 AD 0F 01 57 D2 00 56 03 2B 1A 8E 3D 27 66
```

Field values behind them:

- `info_response.bin`: `device_id` 8B 9C AD BE CF D0 E1 F2, `hw_rev` 0x8102, `fw_rev` 0x9304, `capabilities` 0xC3
  (PPG_RAW, PPG_SUMMARY, IBI_LOG, ENCRYPTED_ONLY).
- `error.bin`: `code` 0x0102 (`INVALID_FIELD`), offending `msg_type` 0x20, `detail` 0x0C.
- `time_anchor_request.bin`: `utc_ms` 0x000001A2B3C4D5E6. `time_anchor_reply.bin`: `boot_id` 0xC0DEFACE,
  `uptime_ms` 0x000000E4D3C2B1A0.
- `config_set.bin`: `mode` 2, `payload_format` 1, rates 25/200/100/400 Hz, burst 300 s / 30 s, `led_mask` 5,
  42/27/33 mA, `wear_ppg_dc` 0x0005B7C9, `wear_motion_thr` 500, probe 1000 ms.
- `config_state.bin`: `mode` 1, `payload_format` 0, rates 48/32/128/400 Hz, burst 600 s / 45 s, `led_mask` 7, 60/52/41 mA,
  `wear_ppg_dc` 0x0007FFFF, `wear_motion_thr` 3000, probe 5000 ms.
- `battery.bin`: 4013 mV, charging, 87 %, 210/854/6699/15758 uA.

The other files in `fixtures/golden/` (negative frames, maximum and 0xA5-heavy frames) are listed in
`fixtures/golden/manifest.txt` with the error each decoder must report.
