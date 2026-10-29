import Foundation

/// Invented states of the disc, to design and test the Device tab before the CoreBluetooth transport exists.
enum DeviceScenario: String, CaseIterable {
    case connected, charging, lowBattery, syncing, outOfRange, bluetoothOff, bondLost
    case updateAvailable, updateLowBattery, updating, updateFailing, unpaired

    init?(launchValue: String?) {
        guard let v = launchValue else { return nil }
        self.init(rawValue: v)
    }
}

enum DeviceFixtures {
    static func snapshot(_ scenario: DeviceScenario) -> DeviceSnapshot {
        var s = DeviceSnapshot()
        switch scenario {
        case .connected:
            break
        case .charging:
            s.battery = BatteryReading(percent: 81, charge: .charging)
            s.minutesSinceSync = 3
        case .lowBattery:
            s.battery = BatteryReading(percent: 12, charge: .notCharging)
        case .syncing:
            s.link = .syncing(hoursLeft: 3)
            s.minutesSinceSync = 410
        case .outOfRange:
            s.link = .outOfRange
            s.minutesSinceSync = 125
        case .bluetoothOff:
            s.link = .bluetoothOff
        case .bondLost:
            s.link = .bondLost
        case .updateAvailable:
            s.firmware = .available(version: "0.3.0")
        case .updateLowBattery:
            s.firmware = .available(version: "0.3.0")
            s.battery = BatteryReading(percent: 34, charge: .notCharging)
        case .updating:
            s.firmware = .available(version: "0.3.0")
        case .updateFailing:
            s.firmware = .available(version: "0.3.0")
        case .unpaired:
            s.paired = false
        }
        return s
    }

    /// Screenshots: `-device-state updating` starts the update by itself.
    static func autoStartsUpdate(_ scenario: DeviceScenario) -> Bool { scenario == .updating || scenario == .updateFailing }
}
