import Foundation
import Observation

// The Device tab's data. Plain words first (D41): the screen says how the disc is, in a sentence, and keeps versions and
// identifiers one level down. Everything here is derived from fields the protocol already carries (the design notes G).

/// `CONFIG_STATE.mode` (decision D8).
enum DeviceMode: Int, CaseIterable, Identifiable {
    case night, day, workout, raw

    var id: Int { rawValue }
    var key: String {
        switch self {
        case .night: return "night"
        case .day: return "day"
        case .workout: return "workout"
        case .raw: return "raw"
        }
    }
    var name: String { L("device.mode.\(key)") }
    var about: String { L("device.mode.\(key).about") }
}

/// `BATTERY.charging`: 0 not charging, 1 charging, 2 complete, 3 fault, 0xFF unknown.
enum ChargeState: Equatable {
    case notCharging, charging, full, fault, unknown
}

struct BatteryReading: Equatable {
    /// 0...100, an estimate from the voltage (always shown with "≈"); nil when the disc says 0xFF.
    var percent: Int?
    var charge: ChargeState
}

enum DeviceLink: Equatable {
    case connected
    /// Catching up on history the disc stored while the phone was away.
    case syncing(hoursLeft: Int)
    case outOfRange
    case bluetoothOff
    /// The phone and the disc no longer share a bond: it has to be paired again.
    case bondLost
}

enum FirmwareState: Equatable {
    case upToDate
    case available(version: String)
    case downloading(Double)
    case transferring(Double)
    case verifying
    case done(version: String)
    case failed
}

/// Why an update cannot start right now.
enum UpdateGate: Equatable {
    case ok
    case notConnected
    /// The charge needed first; the thresholds are placeholders until the power model is measured (03 G2).
    case needsCharge(percent: Int)
}

enum HealthWriting: Equatable { case on, off, denied }

struct DeviceSnapshot: Equatable {
    var paired = true
    /// Advertising name, `Caseback-XXXX`.
    var name = "Caseback-3F2A"
    var link: DeviceLink = .connected
    var minutesSinceSync: Int? = 12
    var battery = BatteryReading(percent: 64, charge: .notCharging)
    var mode: DeviceMode = .night
    var firmwareVersion = "0.2.1"
    var hardwareRevision = "A"
    var deviceID = "3F2A 91C4 07B8 55E0"
    var protocolVersion = "0.2"
    var firmware: FirmwareState = .upToDate
    /// `INFO_RESPONSE.capabilities` bits that decide what the app can offer.
    var supportsSpO2 = true
    var supportsTemperature = true
    var spo2Enabled = false
    var temperatureEnabled = false
    var health: HealthWriting = .on
    var storedDays = 41
}

/// The sentence at the top: what the disc is doing and whether the owner has to do something.
struct DeviceStatus: Equatable {
    var headline: String
    var detail: String
    var needsAction = false
}

enum DeviceInsights {
    /// Below this the app warns (spec: "app warns at 15 % / 5 %").
    static let lowBattery = 15
    static let criticalBattery = 5

    static func status(_ s: DeviceSnapshot) -> DeviceStatus {
        let synced = s.minutesSinceSync.map { TodayFormat.age(minutes: $0) }
        switch s.link {
        case .bondLost:
            return DeviceStatus(headline: L("device.status.bondLost"), detail: L("device.status.bondLost.detail"), needsAction: true)
        case .bluetoothOff:
            return DeviceStatus(headline: L("device.status.btOff"), detail: L("device.status.btOff.detail"), needsAction: true)
        case .outOfRange:
            let detail = synced.map { L("device.status.out.detail", $0) } ?? L("device.status.out.never")
            return DeviceStatus(headline: L("device.status.out"), detail: detail)
        case .syncing(let hours):
            return DeviceStatus(headline: L("device.status.syncing"), detail: L("device.status.syncing.detail", hours))
        case .connected:
            if let p = s.battery.percent, s.battery.charge != .charging, p <= lowBattery {
                return DeviceStatus(
                    headline: L("device.status.low"), detail: L(p <= criticalBattery ? "device.status.critical.detail" : "device.status.low.detail"),
                    needsAction: true)
            }
            if s.battery.charge == .fault {
                return DeviceStatus(headline: L("device.status.fault"), detail: L("device.status.fault.detail"), needsAction: true)
            }
            if s.battery.charge == .charging {
                return DeviceStatus(headline: L("device.status.charging"), detail: synced.map { L("device.status.synced", $0) } ?? "")
            }
            return DeviceStatus(headline: L("device.status.connected"), detail: synced.map { L("device.status.synced", $0) } ?? L("device.status.notYet"))
        }
    }

    /// "≈ 64 %", or an en dash when the disc has no estimate.
    static func batteryText(_ b: BatteryReading) -> String {
        b.percent.map { L("status.battery", $0) } ?? "–"
    }

    /// The word beside the number, from the `charging` enum.
    static func chargeWord(_ b: BatteryReading) -> String? {
        switch b.charge {
        case .charging: return L("device.charge.charging")
        case .full: return L("device.charge.full")
        case .fault: return L("device.charge.fault")
        case .unknown: return b.percent == nil ? L("device.charge.unknown") : nil
        case .notCharging: return nil
        }
    }

    static func updateGate(_ s: DeviceSnapshot) -> UpdateGate {
        guard s.link == .connected else { return .notConnected }
        let need = s.battery.charge == .charging ? 30 : 50
        if let p = s.battery.percent, p < need { return .needsCharge(percent: need) }
        if s.battery.percent == nil { return .needsCharge(percent: need) }
        return .ok
    }

    /// Value shown on the row of each part of the screen.
    static func updateValue(_ f: FirmwareState) -> String {
        switch f {
        case .upToDate: return L("device.update.row.upToDate")
        case .available: return L("device.update.row.available")
        case .downloading(let p), .transferring(let p): return "\(Int((p * 100).rounded())) %"
        case .verifying: return L("device.update.row.verifying")
        case .done: return L("device.update.row.done")
        case .failed: return L("device.update.row.failed")
        }
    }

    static func healthValue(_ h: HealthWriting) -> String {
        switch h {
        case .on: return L("device.health.row.on")
        case .off: return L("device.health.row.off")
        case .denied: return L("device.health.row.denied")
        }
    }

    static func experimentalValue(_ s: DeviceSnapshot) -> String {
        let n = (s.spo2Enabled ? 1 : 0) + (s.temperatureEnabled ? 1 : 0)
        return n == 0 ? L("device.exp.row.none") : L("device.exp.row.some", n)
    }
}

/// The detail screens, each a sheet over the tab.
enum DeviceSheet: String, Identifiable {
    case mode, update, health, data, experimental, forget, about
    var id: String { rawValue }
}

enum ExportFormat: String, CaseIterable, Identifiable {
    case csv = "CSV", json = "JSON"
    var id: String { rawValue }
}

enum ExportRange: Int, CaseIterable, Identifiable {
    case week = 7, month = 30, all = 0
    var id: Int { rawValue }
}

enum ExportState: Equatable { case idle, working, done }

@MainActor
@Observable
final class DeviceModel {
    private(set) var snapshot: DeviceSnapshot
    var sheet: DeviceSheet?
    var exportState: ExportState = .idle
    private var updateTask: Task<Void, Never>?
    /// Fixtures: the transfer fails at 60 %, to exercise the rollback message.
    private let failTransfer: Bool
    private let fast: Bool

    /// `sheet` and `autoStart` are for screenshots (launch arguments): they act once, when the model is made.
    init(snapshot: DeviceSnapshot, failTransfer: Bool = false, fast: Bool = false, sheet: DeviceSheet? = nil, autoStart: Bool = false) {
        self.snapshot = snapshot
        self.failTransfer = failTransfer
        self.fast = fast
        self.sheet = sheet
        if autoStart { startUpdate() }
    }

    var status: DeviceStatus { DeviceInsights.status(snapshot) }
    var gate: UpdateGate { DeviceInsights.updateGate(snapshot) }

    // MARK: actions

    /// `CONFIG_SET` with the new mode; the disc answers with `CONFIG_STATE` carrying what it applied.
    func setMode(_ mode: DeviceMode) { snapshot.mode = mode }

    func setHealth(_ on: Bool) { snapshot.health = on ? .on : .off }

    func setSpO2(_ on: Bool) { if snapshot.supportsSpO2 { snapshot.spo2Enabled = on } }
    func setTemperature(_ on: Bool) { if snapshot.supportsTemperature { snapshot.temperatureEnabled = on } }

    func startUpdate() {
        guard case .available(let version) = snapshot.firmware, gate == .ok else { return }
        startSimulation(version: version)
    }

    func retryUpdate() {
        guard snapshot.firmware == .failed, gate == .ok else { return }
        startSimulation(version: "0.3.0")
    }

    func cancelUpdate() {
        updateTask?.cancel()
        if case .downloading = snapshot.firmware { snapshot.firmware = .available(version: "0.3.0") }
    }

    /// The transfer is simulated until the SMP transport exists (03 G2): download, transfer, verify, reboot.
    private func startSimulation(version: String) {
        updateTask?.cancel()
        updateTask = Task { [weak self] in
            guard let self else { return }
            let step: UInt64 = fast ? 0 : 90_000_000
            for i in 1...10 {
                if Task.isCancelled { return }
                snapshot.firmware = .downloading(Double(i) / 10)
                try? await Task.sleep(nanoseconds: step)
            }
            for i in 1...20 {
                if Task.isCancelled { return }
                let p = Double(i) / 20
                snapshot.firmware = .transferring(p)
                if failTransfer && p >= 0.6 {
                    snapshot.firmware = .failed
                    return
                }
                try? await Task.sleep(nanoseconds: step)
            }
            snapshot.firmware = .verifying
            try? await Task.sleep(nanoseconds: fast ? 0 : 900_000_000)
            snapshot.firmware = .done(version: version)
            snapshot.firmwareVersion = version
        }
    }

    func export() {
        exportState = .working
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: self?.fast == true ? 0 : 1_200_000_000)
            self?.exportState = .done
        }
    }

    func deleteData() {
        snapshot.storedDays = 0
    }
}
