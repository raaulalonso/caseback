# Security policy

Caseback handles health data and a Bluetooth link, so security reports are welcome.

## Reporting

Use GitHub's private vulnerability reporting for this repository (Security tab, "Report a vulnerability"). Please do not
open a public issue for a vulnerability. Include what you found, how to reproduce it, the firmware and app versions, and
the impact you expect. There is no bounty programme; reports are acknowledged on a best-effort basis.

## Scope

- BLE link: pairing and bonding, the GATT surface, the `caseback-protocol` parser in C, Swift and Python.
- Firmware update: MCUboot image signing and the SMP DFU path.
- The iOS app's local storage and export.

## Known state

The firmware has not been built on a board yet and pairing, privacy and DFU signing are designed but not shipped
(decisions D4 and D5). Do not rely on this project for security until they are.
