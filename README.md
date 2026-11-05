# Caseback software

Caseback is a biometric sensor worn under a wristwatch. This repository contains
the Bluetooth protocol, firmware and iPhone software.

| Directory | Contents |
| --- | --- |
| [caseback-protocol](caseback-protocol/) | BLE framing and messages, the Python implementation, generated test vectors |
| [firmware](firmware/) | Zephyr application for nRF52840 and an Arduino sensor recorder |
| [apps/ios](apps/ios/) | SwiftUI app, widgets, Swift protocol package and tests |

Run the protocol tests with `swift test --package-path apps/ios/CasebackProtocol`.
For Python 3.12 or later, create a virtual environment, install
`caseback-protocol/python[dev]` and run `python -m pytest caseback-protocol/python/tests`.
Build instructions are included for the [firmware](firmware/caseback-fw/README.md)
and [iOS app](apps/ios/README.md).

Caseback-owned software is available under [Apache-2.0](LICENSE). Bundled IBM Plex
fonts use the SIL Open Font License. See [NOTICE](NOTICE) for attribution.
