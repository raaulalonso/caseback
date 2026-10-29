# Caseback for iOS

SwiftUI app, iOS 17 or later. It runs against a simulated disc; the screens show invented fixtures (see
`Today/TodayFixtures.swift`).

```
apps/ios/
├─ CasebackProtocol/   Swift package: frame codec, messages, SimulatedPeripheral (iOS 16 / macOS 13)
├─ Caseback/           the app: Design/ tokens, Blobs/ Metal field, Onboarding/ flow and setup seam, Today/ panel, Trends/ screen, Detail/ metric screens, Device/ tab
├─ CasebackTests/      app tests (handshake, onboarding state machine, blob physics, Today logic and the pull)
├─ CasebackUITests/    UI tests that drive the pull, the sheet scroll and the pages with a real finger
└─ project.yml      XcodeGen spec; the .xcodeproj, Info.plist and entitlements are generated
```

## Build and test

```sh
brew install xcodegen            # once
cd apps/ios && xcodegen generate
xcodebuild -project Caseback.xcodeproj -scheme Caseback \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' test
(cd CasebackProtocol && swift test)
```

Signing: no team is set. The Simulator runs unsigned; on a device set your own team in Xcode (HealthKit needs it).

## Simulator launch arguments (debug)

| Argument | Effect |
|---|---|
| `-onboarding-reset YES` | forget that onboarding finished |
| `-onboarding-step N` | start at step N (0 welcome … 6 done) |
| `-caseback-sim <scenario>` | `happy`, `noDisc`, `twoDiscs`, `bondMismatch`, `newerApp`, `weakContact` |
| `-caseback-fast YES` | instant timings |
| `-caseback-autopair YES` | tap Pair by itself (debug builds) |
| `-onboarding-done YES` | skip onboarding and open Today |
| `-widget-age-hours N` | store what the widgets show as if the disc had last synced N hours ago (screenshots of the widgets on a Home Screen) |
| `-today-state <name>` | `normal`, `high`, `low`, `partial`, `calibrating`, `noData`, `outOfRange`, `backfilling`, `bondLost`, `lowBattery`, `bluetoothOff`, `unpaired` |
| `-today-page N` | 0 Now, 1 Last night |
| `-today-drawer V` | `1` opens the conclusions sheet, `0.4` freezes it part way (screenshots) |
| `-today-open <name>` | open that metric's screen: `readiness`, `sleep`, `steps`, `restingHR`, `hrv`, `pulse`, `skinTemp`, `spo2`, `day` (screenshots; acts once per launch) |
| `-widget-gallery <name>` | draw the widgets at their real size instead of the app: `YES` for all, or `small`, `states`, `medium`, `lock` (screenshots) |
| `-detail-scroll <name>` | scroll that screen to its section `a`, `b` or `affects` (screenshots) |
| `-tab trends` | open that tab (`trends`, `device`) |
| `-trends-state <name>` | `normal`, `full`, `young`, `empty` (invented fixtures) |
| `-trends-metric <name>` / `-trends-range N` | `readiness`, `sleep`, `restingHR`, `hrv`, `steps`, `skinTemp`, `spo2` / 7, 30 or 90 |
| `-trends-scrub N` / `-trends-info YES` | hold the cursor on day N / show the "i" explanation (screenshots) |
| `-today-info readiness` | show the "i" explanation of that chart (screenshots) |
| `-device-state <name>` | `connected`, `charging`, `lowBattery`, `syncing`, `outOfRange`, `bluetoothOff`, `bondLost`, `updateAvailable`, `updateLowBattery`, `updating`, `updateFailing`, `unpaired` (invented fixtures) |
| `-device-sheet <name>` / `-device-autostart YES` | open that sheet (`mode`, `update`, `health`, `data`, `experimental`, `forget`, `about`) / start the simulated update when its sheet opens |

## Where the seams are

- `Onboarding/Setup/DiscSetup.swift`: the protocols the flow needs from the disc and from the system. The CoreBluetooth
  transport (a `BLETransport`) is the next piece; `Handshake.run` already works over any transport.
- `Blobs/`: `BlobSimulator` (spring physics), `BlobScenes` (poses and choreography), `Blobs.metal` (the shader).
  Setup only; Today does not use blobs.
- `Today/`: the panel (`TodayModel` and its word rules, `TodayFixtures`, `Charts` thick-line charts, `Tiles`, `TodayPanel`, the conclusions
  `Drawer` with its `DrawerController` pull, `Insights`). The fixtures stand in for the data store.
- Fonts: IBM Plex Mono (OFL) in `Caseback/Resources/Fonts/`, listed in the root `NOTICE`.
