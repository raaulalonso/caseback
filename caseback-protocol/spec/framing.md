# Caseback framing (proto_ver 0x01, spec v0.2)

Every application PDU is a single frame. A frame is carried whole in one ATT value (one write or one notification); it
is never split across ATT PDUs and never concatenated with another. Multi-byte integers are little-endian.

| Offset | Type | Field | Description |
|-------:|------|-------|-------------|
| 0 | u8 | `magic` | Always `0xA5` |
| 1 | u8 | `proto_ver` | Protocol version, `0x01` |
| 2 | u8 | `msg_type` | Message type, see [messages.md](messages.md) |
| 3..4 | u16 | `payload_len` | Payload length in bytes |
| 5.. | u8 | `payload` | Message payload |
| last 2 | u16 | `crc16` | CRC-16/CCITT-FALSE over all bytes before the CRC |

## Limits

| Constant | Value | Derivation |
|----------|------:|------------|
| `HEADER_LEN` | 5 | magic, proto_ver, msg_type, payload_len |
| `CRC_LEN` | 2 | |
| `MAX_PAYLOAD` | **175** | `MAX_FRAME` - 7 |
| `MAX_FRAME` | **182** | ATT MTU 185 - 3 |

A notification or write-without-response value carries at most `ATT_MTU - 3` bytes (1 byte opcode + 2 bytes handle).
CoreBluetooth on iOS negotiates ATT MTU 185 and reports 182 as the maximum value length; Zephyr asks for 247 but the
connection uses the smaller of the two sides. The frame limit is fixed at the iOS figure so that one number works with
every central: `MAX_FRAME = 185 - 3 = 182`, so `MAX_PAYLOAD = 182 - 5 - 2 = 175` (decision D6).

Rules:

- `payload_len` MUST NOT exceed 175. Senders MUST NOT emit larger frames; receivers reject them with `PAYLOAD_TOO_LONG`.
- A sender MUST also keep every frame within `ATT_MTU - 3` of the current connection when that is below 182 (for
  example before the MTU exchange completes). Messages with a variable count (STREAM_DATA) are sized to fit.
- There is no fragmentation layer. Every defined message fits in one frame.
- `proto_ver` stays `0x01` in spec v0.2: the frame layout is unchanged. The v0.1 limit of 512 bytes was never
  transmittable (a 519-byte frame cannot travel in one notification) and no released firmware emitted it, so no
  deployed peer is affected by lowering it.

## Compatibility rule

A receiver accepts a frame only if `proto_ver` equals the one it implements (`0x01`); any other value is rejected with
`UNSUPPORTED_VERSION` after the magic check and before anything else is interpreted, because the length and CRC rules
of another version are unknown. A future incompatible layout increments `proto_ver`; additive messages inside a
version do not. A frame with an unassigned `msg_type` is a valid frame (framing is type-agnostic); the dispatcher
answers it with `ERROR(UNKNOWN_MSG_TYPE)`.

## Decoding order

All three implementations (Python, Swift, C) apply the checks in this order and report the first that fails. Each
check uses only bytes that are already present; if a check needs a byte that is missing the result is `TRUNCATED`.

| # | Check | Error | Code |
|--:|-------|-------|-----:|
| 1 | `data[0] == 0xA5` | `BAD_MAGIC` | 0x0002 |
| 2 | `data[1] == 0x01` | `UNSUPPORTED_VERSION` | 0x0003 |
| 3 | `payload_len <= 175` | `PAYLOAD_TOO_LONG` | 0x0004 |
| 4 | `len(data) >= 7 + payload_len` | `TRUNCATED` | 0x0001 |
| 5 | `len(data) == 7 + payload_len` | `LENGTH_MISMATCH` | 0x0005 |
| 6 | CRC matches | `BAD_CRC` | 0x0006 |

Consequences: an empty input, or one that ends before a checked byte, is `TRUNCATED`; a declared length above 175 is
`PAYLOAD_TOO_LONG` even when the input is also short; bytes after the CRC (trailing bytes) are `LENGTH_MISMATCH`. The
numeric codes are the `ErrorCode` values of [messages.md](messages.md).

## CRC

CRC parameters: poly `0x1021`, init `0xFFFF`, refin=false, refout=false, xorout=`0x0000`, transmitted little-endian.
Check value for ASCII `123456789` is `0x29B1`. The CRC is an integrity check only, not authentication; confidentiality
and replay protection come from the encrypted link (see [gatt.md](gatt.md)).
