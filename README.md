# Caseback

Health sensor that hides under the watch you already love. The design and the code are published here, so you can see how it is built and what it does. Part of it is open source and part is source-available: see [Licenses](#licenses).

<p>
  <a href="LICENSE-FSL"><img alt="Source-available license" src="https://img.shields.io/badge/hardware%20%C2%B7%20firmware%20%C2%B7%20app-FSL--1.1-3fb950"/></a>
  <a href="LICENSE-SOFTWARE"><img alt="Open source license" src="https://img.shields.io/badge/protocol%20%C2%B7%20algorithms%20%C2%B7%20tools-Apache--2.0-58a6ff"/></a>
  <img alt="Platform" src="https://img.shields.io/badge/platform-nRF52840%20%7C%20iOS-9cf"/>
</p>

Dia. 25 mm, 3.1 mm biometric disc (the first working prototype is 34 mm) / microsuction on the caseback / HR / HRV / SpO2 / skin temp / steps / sleep / readiness  
No subscription / no account / data stays on your phone.

## What is in this repository

| Folder | What it holds |
|---|---|
| [`hardware/`](hardware/) | The disc and its charging base: generators and STL files, the printable mocks, the V0.1 board in KiCad with its fabrication files |
| [`firmware/`](firmware/) | Zephyr application for the nRF52840 and a recorder sketch |
| [`apps/ios/`](apps/ios/) | The iOS app (SwiftUI) and the Swift implementation of the protocol |
| [`caseback-protocol/`](caseback-protocol/) | The Bluetooth messages, byte by byte, with reference implementations and golden test vectors |
| [`algorithms/`](algorithms/) | Heart rate, HRV, SpO2, steps, sleep, skin temperature and readiness, with the tools that evaluate them |
| [`web/`](web/) | The website (Next.js, English and Spanish) |
| [`tools/`](tools/) | Scripts that draw the website figures and the app captures |

## How it mounts

1. **STICK** - microsuction on the caseback (no glue, no magnets on the watch)
2. **WEAR** - style unchanged, 24/7 tracking
3. **SYNC** - BLE to iOS, local data only

## Verify

```bash
cd caseback-protocol/python && python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]" && pytest -v

cd apps/ios/CasebackProtocol && swift test

cd algorithms/ppg && pip install -e . && pytest
cd algorithms/wellness && pip install -e . && pytest
```

The website: `cd web && npm install && npm run dev`.

## Licenses

| Folder | License | Kind |
|--------|---------|------|
| `hardware/`, `firmware/`, `apps/` | [FSL-1.1-ALv2](LICENSE-FSL) | Source-available: read, run, modify and redistribute for any purpose except a competing product. Each version becomes Apache-2.0 two years after it is published. |
| `caseback-protocol/`, `algorithms/`, `tools/`, `tests/`, `web/` | [Apache-2.0](LICENSE-SOFTWARE) | Open source. Includes the Swift and C implementations of the protocol inside `apps/` and `firmware/`. |
| Markdown documents | [CC-BY-SA-4.0](LICENSE-DOCS) | Open source |

[NOTICE](NOTICE) has the exceptions, the third-party data and the trademark policy. Versions published up to 27 October 2026 keep the licences they were published with: CERN-OHL-S-2.0 for the hardware ([text](licenses/CERN-OHL-S-2.0.txt)), Apache-2.0 for the software.

Caseback / health data stays yours.
