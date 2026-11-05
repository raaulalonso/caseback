import Foundation
import Observation
import CasebackProtocol
import SwiftUI

enum OnboardingStep: Int, CaseIterable, Comparable {
    case welcome, bluetooth, mount, pair, contact, health, done

    static func < (a: Self, b: Self) -> Bool { a.rawValue < b.rawValue }
    /// Steps that count in the progress rule (welcome is not a step).
    static let counted: [OnboardingStep] = [.bluetooth, .mount, .pair, .contact, .health, .done]
}

enum PairState: Equatable {
    case idle
    case searching
    case found([DiscoveredDisc])
    case pairing(DiscoveredDisc, PairingPhase)
    case paired(PairedDisc)
    case failed(PairingFailure)
}

/// The onboarding state machine (the design notes section A). No views in here: it is driven by the
/// screens and tested without them.
@Observable @MainActor
final class OnboardingModel {
    // MARK: state
    private(set) var step: OnboardingStep
    /// +1 going forward, -1 going back; used by the screens for transitions.
    private(set) var direction = 1
    private(set) var bluetooth: BluetoothAccess
    private(set) var pair: PairState = .idle
    private(set) var searchStartedAt: Date?
    private(set) var signal: SignalSample?
    private(set) var signalSeconds = 0
    private(set) var beat = 0
    var healthChoice: Set<Metric> = Set(Metric.allCases.filter(\.writtenToHealth))
    private(set) var healthAccess: HealthAccess = .notAsked
    private(set) var paired: PairedDisc?
    /// After pairing succeeds the field bursts, then settles into the marks.
    private(set) var burstSettled = false
    /// The finale: flood, then settle.
    private(set) var finaleSettled = false
    private(set) var finished = false

    // MARK: collaborators
    private let setup: DiscSetupService
    private let bluetoothPermission: BluetoothPermission
    private let healthPermission: HealthPermission
    private let store: OnboardingStore
    private let timing: OnboardingTiming

    private var scanTask: Task<Void, Never>?
    private var pairTask: Task<Void, Never>?
    private var signalTask: Task<Void, Never>?
    private var beatTask: Task<Void, Never>?
    private var finaleTask: Task<Void, Never>?
    private var searchDeadline: Task<Void, Never>?

    init(
        setup: DiscSetupService, bluetooth: BluetoothPermission, health: HealthPermission,
        store: OnboardingStore = OnboardingStore(), timing: OnboardingTiming = .realistic,
        startAt: OnboardingStep = .welcome
    ) {
        self.setup = setup
        self.bluetoothPermission = bluetooth
        self.healthPermission = health
        self.store = store
        self.timing = timing
        self.step = startAt
        self.bluetooth = bluetooth.current
        if startAt >= .contact { paired = Self.placeholderDisc }
        enter(startAt)
    }

    // MARK: derived
    var pose: BlobPose {
        switch step {
        case .welcome: return .welcome
        case .bluetooth: return .bluetooth
        case .mount: return .mount
        case .pair:
            switch pair {
            case .idle, .searching: return .searching
            case .found, .pairing: return .fused
            case .paired: return burstSettled ? .marks : .burst
            case .failed: return .bluetooth
            }
        case .contact: return .marks
        case .health: return .marks
        case .done: return finaleSettled ? .settle : .flood
        }
    }

    var blobInputs: BlobInputs {
        var inputs = BlobInputs()
        switch step {
        case .contact:
            let level = Double(signal?.quality ?? 0) / 255
            inputs.levels = Array(repeating: max(level, 0.12), count: 7)
        case .health:
            inputs.lit = healthChoice
            inputs.levels = Array(repeating: 0.7, count: 7)
        case .pair:
            inputs.levels = Array(repeating: 0.6, count: 7)
        default:
            break
        }
        return inputs
    }

    var canGoBack: Bool {
        switch step {
        case .welcome, .done: return false
        case .pair:
            if case .pairing = pair { return false }
            if case .paired = pair { return false }
            return true
        default: return true
        }
    }

    var progressIndex: Int { OnboardingStep.counted.firstIndex(of: step).map { $0 + 1 } ?? 0 }

    // MARK: navigation
    func next() {
        guard let to = OnboardingStep(rawValue: step.rawValue + 1) else { return }
        go(to, direction: 1)
    }

    func back() {
        guard canGoBack, let to = OnboardingStep(rawValue: step.rawValue - 1) else { return }
        go(to, direction: -1)
    }

    /// "I'll do this later": leaves the flow without a disc. Today shows the setup prompt (03 section B).
    func skip() {
        cancelAll()
        finished = true
    }

    func complete() {
        store.markCompleted(disc: paired)
        cancelAll()
        finished = true
    }

    private func go(_ to: OnboardingStep, direction: Int) {
        leave(step)
        self.direction = direction
        withAnimation(Motion.standard(0.5)) { step = to }
        enter(to)
    }

    private func leave(_ s: OnboardingStep) {
        switch s {
        case .pair:
            scanTask?.cancel(); searchDeadline?.cancel(); setup.stopScan()
            if case .paired = pair {} else if case .pairing = pair {} else { pair = .idle }
        case .contact:
            signalTask?.cancel(); beatTask?.cancel()
        default: break
        }
    }

    private func enter(_ s: OnboardingStep) {
        switch s {
        case .pair:
            if case .paired = pair { return }
            startSearch()
        case .contact:
            startSignal()
        case .done:
            startFinale()
        default: break
        }
    }

    // MARK: bluetooth
    func requestBluetooth() async {
        let result = await bluetoothPermission.request()
        bluetooth = result
        if Self.passesBluetooth(result) { next() }
    }

    /// The Simulator reports `.unsupported`: there the simulated disc takes over.
    static func passesBluetooth(_ access: BluetoothAccess) -> Bool {
        #if targetEnvironment(simulator)
        return access == .allowed || access == .unsupported
        #else
        return access == .allowed
        #endif
    }

    func refreshBluetooth() { bluetooth = bluetoothPermission.current }

    // MARK: pairing
    func startSearch() {
        scanTask?.cancel(); searchDeadline?.cancel()
        searchStartedAt = Date()
        pair = .searching
        let stream = setup.scan()
        scanTask = Task { [weak self] in
            for await discs in stream {
                guard let self, !Task.isCancelled else { return }
                if case .pairing = self.pair { return }
                if !discs.isEmpty {
                    self.searchDeadline?.cancel()
                    let wasEmpty: Bool
                    if case .found = self.pair { wasEmpty = false } else { wasEmpty = true }
                    withAnimation(Motion.standard) { self.pair = .found(discs.sorted { $0.rssi > $1.rssi }) }
                    if wasEmpty { Haptics.step() }
                    #if DEBUG
                    if wasEmpty, UserDefaults.standard.bool(forKey: "caseback-autopair"), let first = discs.first {
                        try? await Task.sleep(for: .milliseconds(900))
                        self.pairWith(first)
                    }
                    #endif
                }
            }
        }
        searchDeadline = Task { [weak self] in
            guard let timing = self?.timing else { return }
            try? await Task.sleep(for: timing.searchTimeout)
            guard !Task.isCancelled, let self else { return }
            if case .searching = self.pair {
                self.setup.stopScan()
                withAnimation(Motion.standard) { self.pair = .failed(.noDiscFound) }
                Haptics.warning()
            }
        }
    }

    func pairWith(_ disc: DiscoveredDisc) {
        guard case .found = pair else { return }
        scanTask?.cancel(); searchDeadline?.cancel(); setup.stopScan()
        pair = .pairing(disc, .connecting)
        Haptics.tap()
        pairTask = Task { [weak self] in
            guard let self else { return }
            do {
                let result = try await self.setup.pair(disc) { phase in
                    Task { @MainActor [weak self] in
                        guard let self, case .pairing(let d, _) = self.pair else { return }
                        self.pair = .pairing(d, phase)
                    }
                }
                self.paired = result
                self.burstSettled = false
                withAnimation(Motion.standard) { self.pair = .paired(result) }
                Haptics.success()
                try? await Task.sleep(for: self.timing.burstHold)
                guard !Task.isCancelled else { return }
                self.burstSettled = true
                try? await Task.sleep(for: self.timing.pairedHold)
                guard !Task.isCancelled, self.step == .pair else { return }
                self.next()
            } catch let failure as PairingFailure {
                withAnimation(Motion.standard) { self.pair = .failed(failure) }
                Haptics.warning()
            } catch {
                withAnimation(Motion.standard) { self.pair = .failed(.link("unknown")) }
                Haptics.warning()
            }
        }
    }

    func retryPairing() { startSearch() }

    // MARK: contact
    private func startSignal() {
        signal = nil
        signalSeconds = 0
        signalTask?.cancel(); beatTask?.cancel()
        let stream = setup.signal()
        signalTask = Task { [weak self] in
            for await sample in stream {
                guard let self, !Task.isCancelled else { return }
                self.signal = sample
                self.signalSeconds += 1
            }
        }
        // 72 beats per minute while the signal is good; in the real flow this is the detected IBI (04 section 5).
        beatTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(833))
                guard let self, !Task.isCancelled else { return }
                if let s = self.signal, s.word == .good || s.word == .strong {
                    self.beat += 1
                    Haptics.tick()
                }
            }
        }
    }

    func recheckContact() { startSignal() }

    /// Contact is judged after 20 s without a usable reading (03 section A5).
    var contactStalled: Bool {
        guard let s = signal else { return signalSeconds >= timing.contactStallSeconds }
        return (s.word == .poor || s.word == .fair) && signalSeconds >= timing.contactStallSeconds
    }

    // MARK: health
    func toggleHealth(_ metric: Metric) {
        guard metric.writtenToHealth else { return }
        if healthChoice.contains(metric) { healthChoice.remove(metric) } else { healthChoice.insert(metric) }
        Haptics.tick()
    }

    func requestHealth() async {
        healthAccess = await healthPermission.request(writing: healthChoice)
        next()
    }

    var healthAvailable: Bool { healthPermission.isAvailable }

    // MARK: finale
    private func startFinale() {
        finaleSettled = false
        Haptics.thud()
        finaleTask?.cancel()
        finaleTask = Task { [weak self] in
            guard let timing = self?.timing else { return }
            try? await Task.sleep(for: timing.floodHold)
            guard !Task.isCancelled, let self else { return }
            self.finaleSettled = true
        }
    }

    private func cancelAll() {
        [scanTask, pairTask, signalTask, beatTask, finaleTask, searchDeadline].forEach { $0?.cancel() }
        setup.stopScan()
    }

    static let placeholderDisc = PairedDisc(
        name: "Caseback-E1F2", deviceId: SimulatedPeripheral.defaultInfo.deviceId, hwRev: 0x0100, fwRev: 0x0002,
        capabilities: SimulatedPeripheral.defaultInfo.capabilities, batteryPercent: 87, charging: 0, bootId: 1)
}

struct OnboardingTiming: Equatable {
    var searchTimeout: Duration
    var burstHold: Duration
    var pairedHold: Duration
    var floodHold: Duration
    var contactStallSeconds: Int

    static let realistic = OnboardingTiming(
        searchTimeout: .seconds(30), burstHold: .milliseconds(1100), pairedHold: .milliseconds(1700),
        floodHold: .milliseconds(1100), contactStallSeconds: 20)
    static let instant = OnboardingTiming(
        searchTimeout: .milliseconds(300), burstHold: .zero, pairedHold: .zero, floodHold: .zero, contactStallSeconds: 2)
}

/// Remembers that onboarding finished and which disc was paired.
struct OnboardingStore {
    private let defaults: UserDefaults
    init(defaults: UserDefaults = .standard) { self.defaults = defaults }

    var isCompleted: Bool { defaults.bool(forKey: "onboarding.completed") }
    var discName: String? { defaults.string(forKey: "onboarding.discName") }

    func markCompleted(disc: PairedDisc?) {
        defaults.set(true, forKey: "onboarding.completed")
        if let disc { defaults.set(disc.name, forKey: "onboarding.discName") }
    }

    func reset() {
        defaults.removeObject(forKey: "onboarding.completed")
        defaults.removeObject(forKey: "onboarding.discName")
    }
}
