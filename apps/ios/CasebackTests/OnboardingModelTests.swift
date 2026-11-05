import CasebackProtocol
import XCTest

@testable import Caseback

@MainActor
final class OnboardingModelTests: XCTestCase {
    private func makeModel(
        scenario: SimScenario = .happy, bluetooth: FixedBluetoothPermission? = nil,
        health: FixedHealthPermission? = nil, startAt: OnboardingStep = .welcome,
        defaults: UserDefaults? = nil
    ) -> OnboardingModel {
        let defaults = defaults ?? isolatedDefaults()
        return OnboardingModel(
            setup: SimulatedDiscSetup(scenario: scenario, timing: .instant),
            bluetooth: bluetooth ?? FixedBluetoothPermission(), health: health ?? FixedHealthPermission(),
            store: OnboardingStore(defaults: defaults), timing: .instant, startAt: startAt)
    }

    // MARK: navigation

    func testStartsAtWelcomeAndCannotGoBack() {
        let m = makeModel()
        XCTAssertEqual(m.step, .welcome)
        XCTAssertFalse(m.canGoBack)
        XCTAssertEqual(m.progressIndex, 0, "the welcome is not a counted step")
    }

    func testNextAndBackWalkTheSteps() {
        let m = makeModel()
        m.next()
        XCTAssertEqual(m.step, .bluetooth)
        XCTAssertEqual(m.progressIndex, 1)
        XCTAssertTrue(m.canGoBack)
        m.next()
        XCTAssertEqual(m.step, .mount)
        m.back()
        XCTAssertEqual(m.step, .bluetooth)
        XCTAssertEqual(m.direction, -1)
    }

    func testSkipFinishesWithoutMarkingCompleted() {
        let defaults = isolatedDefaults()
        let m = makeModel(defaults: defaults)
        m.skip()
        XCTAssertTrue(m.finished)
        XCTAssertFalse(OnboardingStore(defaults: defaults).isCompleted, "skipping must bring the setup prompt back")
    }

    // MARK: bluetooth

    func testBluetoothAllowedAdvances() async {
        let m = makeModel(startAt: .bluetooth)
        await m.requestBluetooth()
        XCTAssertEqual(m.step, .mount)
    }

    func testBluetoothDeniedStaysAndShowsIt() async {
        let m = makeModel(bluetooth: FixedBluetoothPermission(onRequest: .denied), startAt: .bluetooth)
        await m.requestBluetooth()
        XCTAssertEqual(m.step, .bluetooth)
        XCTAssertEqual(m.bluetooth, .denied)
    }

    func testBluetoothOffStays() async {
        let m = makeModel(bluetooth: FixedBluetoothPermission(onRequest: .off), startAt: .bluetooth)
        await m.requestBluetooth()
        XCTAssertEqual(m.step, .bluetooth)
        XCTAssertEqual(m.bluetooth, .off)
    }

    func testOnlyAllowedPassesOnADevice() {
        XCTAssertTrue(OnboardingModel.passesBluetooth(.allowed))
        XCTAssertFalse(OnboardingModel.passesBluetooth(.denied))
        XCTAssertFalse(OnboardingModel.passesBluetooth(.off))
        XCTAssertFalse(OnboardingModel.passesBluetooth(.notDetermined))
    }

    // MARK: pairing

    func testPairingHappyPathEndsAtContact() async {
        let m = makeModel(startAt: .pair)
        await waitUntil("a disc is found") { if case .found = m.pair { return true } else { return false } }
        guard case .found(let discs) = m.pair, let disc = discs.first else { return XCTFail("no disc") }
        XCTAssertEqual(disc.name, "Caseback-E1F2")
        XCTAssertEqual(m.pose, .fused)

        m.pairWith(disc)
        await waitUntil("pairing finishes and the flow advances") { m.step == .contact }
        XCTAssertEqual(m.paired?.name, "Caseback-E1F2")
        XCTAssertEqual(m.paired?.batteryPercent, 87)
    }

    func testCannotGoBackWhilePairing() async {
        let m = makeModel(startAt: .pair)
        await waitUntil("found") { if case .found = m.pair { return true } else { return false } }
        guard case .found(let discs) = m.pair else { return }
        XCTAssertTrue(m.canGoBack, "before the user taps Pair, going back is fine")
        m.pairWith(discs[0])
        if case .pairing = m.pair { XCTAssertFalse(m.canGoBack) }
    }

    func testNoDiscFoundFails() async {
        let m = makeModel(scenario: .noDisc, startAt: .pair)
        await waitUntil("the search gives up") { m.pair == .failed(.noDiscFound) }
        XCTAssertEqual(m.pose, .bluetooth, "the field calms down on failure")
    }

    func testBondMismatchFailsWithTheDiscName() async {
        let m = makeModel(scenario: .bondMismatch, startAt: .pair)
        await waitUntil("found") { if case .found = m.pair { return true } else { return false } }
        guard case .found(let discs) = m.pair else { return }
        m.pairWith(discs[0])
        await waitUntil("bond failure") { if case .failed(.bondMismatch) = m.pair { return true } else { return false } }
        XCTAssertEqual(m.pair, .failed(.bondMismatch("Caseback-E1F2")))
    }

    func testNewerAppIsReported() async {
        let m = makeModel(scenario: .newerApp, startAt: .pair)
        await waitUntil("found") { if case .found = m.pair { return true } else { return false } }
        guard case .found(let discs) = m.pair else { return }
        m.pairWith(discs[0])
        await waitUntil("version failure") { m.pair == .failed(.needsNewerApp) }
    }

    func testTwoDiscsAreListedStrongestFirst() async {
        let m = makeModel(scenario: .twoDiscs, startAt: .pair)
        await waitUntil("found") { if case .found = m.pair { return true } else { return false } }
        guard case .found(let discs) = m.pair else { return }
        XCTAssertEqual(discs.count, 2)
        XCTAssertGreaterThan(discs[0].rssi, discs[1].rssi)
    }

    func testRetryAfterFailureSearchesAgain() async {
        let m = makeModel(scenario: .noDisc, startAt: .pair)
        await waitUntil("failure") { m.pair == .failed(.noDiscFound) }
        m.retryPairing()
        XCTAssertEqual(m.pair, .searching)
    }

    // MARK: contact

    func testContactReachesGoodSignal() async {
        let m = makeModel(startAt: .contact)
        await waitUntil("good signal") { (m.signal?.word ?? .poor) >= .good }
        XCTAssertFalse(m.contactStalled)
        XCTAssertGreaterThan(m.blobInputs.levels[0], 0.5)
    }

    func testWeakContactStalls() async {
        let m = makeModel(scenario: .weakContact, startAt: .contact)
        await waitUntil("stalled") { m.contactStalled }
        XCTAssertLessThan(m.signal?.quality ?? 255, 128)
    }

    // MARK: health

    func testSpO2AndTemperatureCanNeverBeSelected() {
        let m = makeModel(startAt: .health)
        XCTAssertFalse(m.healthChoice.contains(.spo2))
        XCTAssertFalse(m.healthChoice.contains(.skinTemp))
        m.toggleHealth(.spo2)
        m.toggleHealth(.skinTemp)
        XCTAssertFalse(m.healthChoice.contains(.spo2), "D13: SpO2 is never written")
        XCTAssertFalse(m.healthChoice.contains(.skinTemp))
    }

    func testToggleHealthMetric() {
        let m = makeModel(startAt: .health)
        XCTAssertTrue(m.healthChoice.contains(.heartRate))
        m.toggleHealth(.heartRate)
        XCTAssertFalse(m.healthChoice.contains(.heartRate))
        m.toggleHealth(.heartRate)
        XCTAssertTrue(m.healthChoice.contains(.heartRate))
    }

    func testRequestHealthPassesTheChoiceAndAdvances() async {
        let health = FixedHealthPermission()
        let m = makeModel(health: health, startAt: .health)
        m.toggleHealth(.steps)
        await m.requestHealth()
        XCTAssertEqual(health.requested, [.heartRate, .hrv, .sleep])
        XCTAssertEqual(m.step, .done)
    }

    func testHealthSampleTypesExcludeSpO2() {
        let types = AppleHealthPermission.shareTypes(for: Set(Metric.allCases))
        XCTAssertEqual(types.count, 4, "heart rate, SDNN, steps, sleep")
        XCTAssertFalse(types.contains { $0.identifier.contains("OxygenSaturation") })
    }

    // MARK: finale and persistence

    func testCompleteStoresTheDisc() async {
        let defaults = isolatedDefaults()
        let m = makeModel(startAt: .done, defaults: defaults)
        m.complete()
        XCTAssertTrue(m.finished)
        let store = OnboardingStore(defaults: defaults)
        XCTAssertTrue(store.isCompleted)
        XCTAssertEqual(store.discName, "Caseback-E1F2")
    }

    func testFinaleFloodsThenSettles() async {
        let m = makeModel(startAt: .done)
        await waitUntil("settle") { m.finaleSettled }
        XCTAssertEqual(m.pose, .settle)
    }

    func testResetForgetsCompletion() {
        let defaults = isolatedDefaults()
        let store = OnboardingStore(defaults: defaults)
        store.markCompleted(disc: OnboardingModel.placeholderDisc)
        XCTAssertTrue(store.isCompleted)
        store.reset()
        XCTAssertFalse(store.isCompleted)
        XCTAssertNil(store.discName)
    }
}

extension SignalWord: Comparable {
    private var order: Int {
        switch self {
        case .poor: return 0
        case .fair: return 1
        case .good: return 2
        case .strong: return 3
        }
    }
    public static func < (a: SignalWord, b: SignalWord) -> Bool { a.order < b.order }
}
