import Foundation
import CasebackProtocol

/// What the simulated disc does, selectable with the launch argument `-caseback-sim <scenario>`.
/// Each scenario exercises one state in the design notes section A.
enum SimScenario: String, CaseIterable {
    case happy, noDisc, twoDiscs, bondMismatch, newerApp, weakContact

    static var current: SimScenario {
        let raw = UserDefaults.standard.string(forKey: "caseback-sim") ?? ""
        return SimScenario(rawValue: raw) ?? .happy
    }
}

struct SimTiming: Equatable {
    var scanDelay: Duration
    var phaseDelay: Duration
    var signalInterval: Duration

    static let realistic = SimTiming(scanDelay: .milliseconds(3200), phaseDelay: .milliseconds(750), signalInterval: .seconds(1))
    static let instant = SimTiming(scanDelay: .zero, phaseDelay: .zero, signalInterval: .milliseconds(5))
}

/// The disc as the onboarding sees it in the Simulator (CoreBluetooth cannot run there) and in tests. The pairing
/// conversation is the real `Handshake` over `SimulatedPeripheral`, paced so the UI has time to be read.
@MainActor
final class SimulatedDiscSetup: DiscSetupService {
    let scenario: SimScenario
    let timing: SimTiming
    private let peripheral: SimulatedPeripheral
    private var scanTask: Task<Void, Never>?

    init(scenario: SimScenario = .current, timing: SimTiming = .realistic, peripheral: SimulatedPeripheral = SimulatedPeripheral()) {
        self.scenario = scenario
        self.timing = timing
        self.peripheral = peripheral
    }

    private var discs: [DiscoveredDisc] {
        let suffix = SimulatedPeripheral.defaultInfo.deviceId.suffix(2).map { String(format: "%02X", $0) }.joined()
        switch scenario {
        case .noDisc: return []
        case .twoDiscs: return [DiscoveredDisc(name: "Caseback-\(suffix)", rssi: -54), DiscoveredDisc(name: "Caseback-7A31", rssi: -78)]
        default: return [DiscoveredDisc(name: "Caseback-\(suffix)", rssi: -58)]
        }
    }

    func scan() -> AsyncStream<[DiscoveredDisc]> {
        scanTask?.cancel()
        let (stream, continuation) = AsyncStream<[DiscoveredDisc]>.makeStream()
        let delay = timing.scanDelay
        let found = discs
        scanTask = Task {
            try? await Task.sleep(for: delay)
            guard !Task.isCancelled else { continuation.finish(); return }
            continuation.yield(found)
            // Signal strength wobbles a little while the scan stays open.
            var tick = 0
            while !Task.isCancelled, !found.isEmpty {
                try? await Task.sleep(for: .seconds(1))
                tick += 1
                let jittered = found.enumerated().map { DiscoveredDisc(name: $1.name, rssi: $1.rssi + [0, 2, -1, 1][(tick + $0) % 4]) }
                continuation.yield(jittered)
            }
            continuation.finish()
        }
        continuation.onTermination = { [weak self] _ in Task { @MainActor in self?.scanTask?.cancel() } }
        return stream
    }

    func stopScan() { scanTask?.cancel(); scanTask = nil }

    func pair(_ disc: DiscoveredDisc, progress: @escaping (PairingPhase) -> Void) async throws -> PairedDisc {
        let transport = PacedTransport(base: peripheral, delay: timing.phaseDelay)
        switch scenario {
        case .bondMismatch:
            progress(.connecting)
            try await Task.sleep(for: timing.phaseDelay)
            progress(.securing)
            try await Task.sleep(for: timing.phaseDelay * 2)
            throw PairingFailure.bondMismatch(disc.name)
        case .newerApp:
            progress(.connecting)
            try await Task.sleep(for: timing.phaseDelay)
            progress(.securing)
            progress(.readingInfo)
            try await Task.sleep(for: timing.phaseDelay)
            throw PairingFailure.needsNewerApp
        default:
            await peripheral.disconnect()
            return try await Handshake.run(transport: transport, progress: progress)
        }
    }

    func signal() -> AsyncStream<SignalSample> {
        let interval = timing.signalInterval
        let weak = scenario == .weakContact
        let (stream, continuation) = AsyncStream<SignalSample>.makeStream()
        let task = Task {
            var t = 0
            while !Task.isCancelled {
                // A ramp as the disc settles against the skin, then steady. The weak scenario never gets there.
                let target = weak ? 40 : 205
                let quality = min(target, 20 + t * 38) + [0, 4, -3, 2][t % 4]
                let rssi = -62 + [0, 1, -2, 1][t % 4]
                continuation.yield(SignalSample(quality: max(quality, 0), rssi: rssi, contact: Double(max(quality, 0)) / 255))
                t += 1
                try? await Task.sleep(for: interval)
            }
            continuation.finish()
        }
        continuation.onTermination = { _ in task.cancel() }
        return stream
    }
}

/// Sleeps before each operation so each pairing phase is visible on screen.
final class PacedTransport: BLETransport, @unchecked Sendable {
    private let base: BLETransport
    private let delay: Duration

    init(base: BLETransport, delay: Duration) { self.base = base; self.delay = delay }

    var isConnected: Bool { base.isConnected }
    func connect() async throws { try? await Task.sleep(for: delay); try await base.connect() }
    func disconnect() async { await base.disconnect() }
    func readInfo() async throws -> Data { try? await Task.sleep(for: delay); return try await base.readInfo() }
    func writeControl(_ frame: Data) async throws { try? await Task.sleep(for: delay); try await base.writeControl(frame) }
    func notifications() -> AsyncStream<Data> { base.notifications() }
}
