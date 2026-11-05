import Foundation
import CasebackProtocol

// Everything the onboarding needs from the disc, behind one seam so the same screens run against
// CoreBluetooth on a phone and against `SimulatedPeripheral` in the Simulator and in tests.
// Flow and states: the design notes section A, errors: 04-states-and-copy.md.

struct DiscoveredDisc: Identifiable, Equatable {
    /// `Caseback-XXXX`: the last two bytes of `device_id`.
    let name: String
    let rssi: Int
    var id: String { name }
}

struct PairedDisc: Equatable {
    let name: String
    let deviceId: [UInt8]
    let hwRev: UInt16
    let fwRev: UInt16
    let capabilities: UInt32
    let batteryPercent: Int?
    let charging: UInt8
    let bootId: UInt32

    var firmwareText: String { "fw \(fwRev >> 8).\(fwRev & 0xFF)" }
}

enum PairingPhase: Int, CaseIterable, Equatable {
    case connecting, securing, readingInfo, settingClock, readingBattery

    var progress: Double { Double(rawValue + 1) / Double(Self.allCases.count) }
}

enum PairingFailure: Error, Equatable {
    /// Nothing advertised within the scan window (03 section A4).
    case noDiscFound
    /// iOS reports an older bond that the disc no longer knows (`linkNotEncrypted` that does not recover).
    case bondMismatch(String)
    /// `unsupportedVersion`: the disc speaks a newer protocol.
    case needsNewerApp
    case timedOut(String)
    case link(String)
}

struct SignalSample: Equatable {
    /// 0...255, the `quality` byte of PPG_SUMMARY.
    let quality: Int
    let rssi: Int
    let contact: Double

    var word: SignalWord { SignalWord(quality: quality) }
}

enum SignalWord: String, Equatable {
    case poor, fair, good, strong

    /// Thresholds are provisional until the first own-hardware recordings (04 section 6).
    init(quality: Int) {
        switch quality {
        case ..<64: self = .poor
        case 64..<128: self = .fair
        case 128..<192: self = .good
        default: self = .strong
        }
    }
}

@MainActor
protocol DiscSetupService: AnyObject {
    /// Discs advertising the Caseback service, strongest first. Finishes when `stopScan()` is called.
    func scan() -> AsyncStream<[DiscoveredDisc]>
    func stopScan()
    func pair(_ disc: DiscoveredDisc, progress: @escaping (PairingPhase) -> Void) async throws -> PairedDisc
    /// Signal quality while the disc is on the wrist, about once per second.
    func signal() -> AsyncStream<SignalSample>
}

/// Bluetooth authorisation, abstracted so the Simulator (which cannot run CoreBluetooth) can pass through.
enum BluetoothAccess: Equatable {
    case notDetermined, allowed, denied, off, unsupported
}

@MainActor
protocol BluetoothPermission: AnyObject {
    var current: BluetoothAccess { get }
    /// Triggers the system prompt if needed and returns the resulting state.
    func request() async -> BluetoothAccess
}

enum HealthAccess: Equatable {
    case unavailable, notAsked, asked
}

@MainActor
protocol HealthPermission: AnyObject {
    var isAvailable: Bool { get }
    func request(writing metrics: Set<Metric>) async -> HealthAccess
}
