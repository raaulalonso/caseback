# Caseback for iOS

Use Xcode 16 or later and XcodeGen to open the iOS 17 project.

```sh
cd apps/ios
xcodegen generate
open Caseback.xcodeproj
```

The Caseback app uses CoreBluetooth on an iPhone. It can retrieve recorded activity
after the phone has been away, display gaps, capture live optical and motion samples,
and export sessions as CSV. Data is kept in a local SQLite archive per device.
The simulator starts with an empty device list. The separate interface preview
uses example values and is available with `-caseback-preview` in a debug simulator build.

Select **CasebackDemo** for the device user or **CasebackBench** for workshop operations.
Both use the same radio and archive implementation. Run protocol tests on macOS with
`swift test --package-path CasebackProtocol`. For installation on a development iPhone,
use your own signing team, bundle identifiers and matching App Group.

The interface uses IBM Plex Mono under its [font licence](Caseback/Resources/Fonts/OFL-IBMPlexMono.txt).
