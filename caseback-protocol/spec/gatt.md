# Caseback GATT (spec v0.2)

Frames (see [framing.md](framing.md)) are carried whole in GATT characteristic values. Standard 16-bit UUIDs are not
reused for Caseback data (a standard Battery Service is deliberately not exposed; battery state is the BATTERY message);
Caseback defines its own 128-bit UUIDs. Firmware update is the standard SMP service, left to MCUboot (decision D4).

## Service and characteristics

INFO is read-only, so a request can never be written to it. v0.1 defined INFO_REQUEST but no way to send it. v0.2 adds a
write characteristic for phone-to-device frames and a notify characteristic for device-to-phone frames:

| Item | UUID | Properties | Security | Carries |
|------|------|------------|----------|---------|
| Caseback service | `decdc7df-2ecb-4d75-b44c-992dccdfca5b` | primary | | |
| INFO | `decdc7e0-2ecb-4d75-b44c-992dccdfca5b` | read | encrypted (LE Secure Connections) | one INFO_RESPONSE frame |
| CONTROL | `decdc7e1-2ecb-4d75-b44c-992dccdfca5b` | write without response | encrypted | P->D frames |
| DATA | `decdc7e2-2ecb-4d75-b44c-992dccdfca5b` | notify | encrypted (also the CCC descriptor write) | D->P frames |
| SMP DFU service | `8d53dc1d-1db7-4cd3-868b-8a527460aa84` | standard mcumgr | encrypted, bonded | not Caseback frames |
| SMP characteristic | `da2e7828-fbce-4e01-ae9e-261174997c48` | write without response, notify | encrypted, bonded | SMP |

The SMP UUIDs are the ones used by the Zephyr/mcumgr BLE transport; they are listed for the phone side only and are not
implemented by Caseback code.

The new UUIDs follow the base pattern of the existing ones: `decdc7dfX` increments in the first 32-bit group. Existing
UUIDs do not change. New characteristics may only be appended after the existing ones (see the GATT cache note).

Rules:

- One ATT value is exactly one frame. Frames are at most 182 bytes.
- Every request goes to CONTROL and every reply arrives on DATA, in the order the device produced them. Replies are
  matched by `msg_type` (INFO_RESPONSE, the TIME_ANCHOR reply, CONFIG_STATE, BATTERY, ERROR carrying the offending
  `msg_type`); the protocol has no request id, so a phone keeps at most one request of each type outstanding.
- Reading INFO returns the same bytes as an INFO_REQUEST/INFO_RESPONSE exchange. It works at any ATT MTU (long read),
  which is how a phone learns `device_id` and capabilities before enabling notifications.
- DATA is not reliable (see the STREAM_DATA `seq` field). A notification larger than `ATT_MTU - 3` is never sent.
- iOS: use `writeType: .withoutResponse` and check `canSendWriteWithoutResponse` before every write.

## Security (decision D5, provisional)

- LE Secure Connections with bonding. The disc has no display and no button, so pairing is Just Works (encrypted but not
  MITM-protected); it is only possible while a pairing window is open (charging puck or 3 taps) and every Caseback
  characteristic requires an encrypted link (`capabilities` bit 7 `ENCRYPTED_ONLY`). Reading INFO or enabling
  notifications on an unencrypted link fails with ATT "insufficient encryption", which makes iOS start pairing.
- The advertised address is a resolvable private address rotated by the controller. The device advertises no `device_id`;
  it only appears in INFO_RESPONSE after encryption.
- Link-layer AES-CCM gives confidentiality and replay protection; the frame CRC is an integrity check only.
- Removing a bond needs a "forget" on the phone and a bond erase on the device.

## Advertising

| Item | Value |
|------|-------|
| Type | connectable, undirected, LE 1M; restarts after every disconnect and after boot |
| Advertising data | Flags `0x06` (3 bytes) + Complete List of 128-bit Service UUIDs with the service UUID above (18 bytes): 21 of 31 bytes |
| Scan response | Complete Local Name `Caseback-XXXX` (12 bytes), `XXXX` = the last two bytes of `device_id` in upper-case hex |
| Interval | 1022.5 ms idle; 152.5 ms for 30 s after a disconnect or while the pairing window is open (values from Apple's accessory guidelines) |

The UUID must be in the advertising data, not only in the scan response: CoreBluetooth background scanning and state
restoration filter on it. No manufacturer data is advertised.

## Connection

| Parameter | Value | Note |
|-----------|-------|------|
| Connection interval | 1000-1500 ms requested (`min` 800, `max` 1200 units of 1.25 ms) | see below |
| Peripheral latency | 0 | |
| Supervision timeout | 6000 ms (600 units of 10 ms) | |
| ATT MTU | device requests 247; iOS settles at 185 | frames are sized for 185 |
| Data length | 251 bytes (LE DLE) | needed for a 182-byte value in one link-layer packet train |
| PHY | 1M; 2M optional | |

The device sends an L2CAP connection parameter update after connecting; the central decides. iOS accepts a request when
`interval_max * (latency + 1) <= 2 s`, `interval_min >= 15 ms`, `interval_min + 15 ms <= interval_max`,
`timeout <= 6 s` and `timeout > 3 * interval_max * (latency + 1)`. A 2 s maximum with a 6 s timeout fails the last rule
(it needs a timeout above 6 s), so the requested range tops out at 1.5 s. With a persistent link the average power
scales with the interval the central actually grants; the design's 2 s figure is an upper bound that iOS may not give.
These rules are quoted from Apple's Accessory Design Guidelines from memory and must be checked against the current
document and on a phone. Android may grant longer intervals.

Before the MTU exchange completes the ATT MTU is 23 and only 20 bytes fit in a notification: the device does not send
frames longer than `ATT_MTU - 3` and the phone must exchange the MTU (automatic on iOS) before enabling DATA.

## iOS GATT cache

iOS caches the attribute table per bonded peripheral. The firmware exposes the GATT Service Changed characteristic and the
database hash (Zephyr `CONFIG_BT_GATT_SERVICE_CHANGED`, `CONFIG_BT_GATT_CACHING`), and a firmware update that changes the
table must keep every existing UUID and handle order, append new characteristics only and let the stack indicate the
change. If the table changes without that, iOS may keep the old cache until the user forgets the device.

## Constants

The identifiers above are exposed by every implementation: Python `caseback_protocol.constants` (`UUID_SERVICE`,
`UUID_INFO`, `UUID_CONTROL`, `UUID_DATA`, `UUID_SMP_SERVICE`, `UUID_SMP_CHARACTERISTIC`), Swift `GATTServiceUUID`,
`GATTInfoUUID`, `GATTControlUUID`, `GATTDataUUID`, `GATTSMPServiceUUID`, `GATTSMPCharacteristicUUID`, and C
`CASEBACK_UUID_*_STR` strings plus `CASEBACK_UUID_*_W32` words for `BT_UUID_128_ENCODE`.
