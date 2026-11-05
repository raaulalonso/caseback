import CoreBluetooth
import Foundation
import HealthKit
import CasebackProtocol

/// Bluetooth authorisation through CoreBluetooth. In the Simulator the manager reports `.unsupported`; the onboarding
/// treats that as "allowed" there (the simulated disc takes over) and as a hard failure on a real phone.
@MainActor
final class CoreBluetoothPermission: NSObject, BluetoothPermission, CBCentralManagerDelegate {
    private var manager: CBCentralManager?
    private var continuation: CheckedContinuation<BluetoothAccess, Never>?

    var current: BluetoothAccess {
        switch CBManager.authorization {
        case .notDetermined: return .notDetermined
        case .denied, .restricted: return .denied
        case .allowedAlways: return manager.map { Self.map($0.state) } ?? .allowed
        @unknown default: return .notDetermined
        }
    }

    func request() async -> BluetoothAccess {
        if CBManager.authorization == .allowedAlways, let manager, manager.state != .unknown, manager.state != .resetting {
            return Self.map(manager.state)
        }
        return await withCheckedContinuation { cont in
            continuation = cont
            if manager == nil {
                // Creating the manager is what shows the system prompt.
                manager = CBCentralManager(delegate: self, queue: .main, options: [CBCentralManagerOptionShowPowerAlertKey: false])
            } else {
                resolve(manager!.state)
            }
        }
    }

    nonisolated func centralManagerDidUpdateState(_ central: CBCentralManager) {
        let state = central.state
        Task { @MainActor in self.resolve(state) }
    }

    private func resolve(_ state: CBManagerState) {
        guard state != .unknown, state != .resetting, let c = continuation else { return }
        continuation = nil
        c.resume(returning: Self.map(state))
    }

    private static func map(_ s: CBManagerState) -> BluetoothAccess {
        switch s {
        case .poweredOn: return .allowed
        case .poweredOff: return .off
        case .unauthorized: return .denied
        case .unsupported: return .unsupported
        default: return .notDetermined
        }
    }
}

@MainActor
final class AppleHealthPermission: HealthPermission {
    private let store = HKHealthStore()
    var isAvailable: Bool { HKHealthStore.isHealthDataAvailable() }

    /// Types written (D13, D17): heart rate, HRV as SDNN, steps, sleep. SpO2 and temperature are never requested.
    static func shareTypes(for metrics: Set<Metric>) -> Set<HKSampleType> {
        var out = Set<HKSampleType>()
        if metrics.contains(.heartRate), let t = HKQuantityType.quantityType(forIdentifier: .heartRate) { out.insert(t) }
        if metrics.contains(.hrv), let t = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN) { out.insert(t) }
        if metrics.contains(.steps), let t = HKQuantityType.quantityType(forIdentifier: .stepCount) { out.insert(t) }
        if metrics.contains(.sleep), let t = HKCategoryType.categoryType(forIdentifier: .sleepAnalysis) { out.insert(t) }
        return out
    }

    func request(writing metrics: Set<Metric>) async -> HealthAccess {
        guard isAvailable else { return .unavailable }
        let share = Self.shareTypes(for: metrics)
        guard !share.isEmpty else { return .notAsked }
        do {
            try await store.requestAuthorization(toShare: share, read: [])
            return .asked
        } catch {
            return .notAsked
        }
    }
}

/// Stand-ins for screenshots and tests.
@MainActor
final class FixedBluetoothPermission: BluetoothPermission {
    var current: BluetoothAccess
    var onRequest: BluetoothAccess
    init(current: BluetoothAccess = .notDetermined, onRequest: BluetoothAccess = .allowed) {
        self.current = current; self.onRequest = onRequest
    }
    func request() async -> BluetoothAccess { current = onRequest; return onRequest }
}

@MainActor
final class FixedHealthPermission: HealthPermission {
    var isAvailable = true
    var result: HealthAccess = .asked
    private(set) var requested: Set<Metric> = []
    func request(writing metrics: Set<Metric>) async -> HealthAccess { requested = metrics; return result }
}
