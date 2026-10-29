import XCTest

@testable import Caseback

final class DeviceInsightsTests: XCTestCase {
    private func snap(_ scenario: DeviceScenario) -> DeviceSnapshot { DeviceFixtures.snapshot(scenario) }

    func testEveryScenarioHasAHeadline() {
        for sc in DeviceScenario.allCases {
            XCTAssertFalse(DeviceInsights.status(snap(sc)).headline.isEmpty, "\(sc)")
        }
    }

    func testStatusNeedsActionOnlyWhenTheOwnerMustAct() {
        XCTAssertFalse(DeviceInsights.status(snap(.connected)).needsAction)
        XCTAssertFalse(DeviceInsights.status(snap(.outOfRange)).needsAction, "being away is normal")
        XCTAssertFalse(DeviceInsights.status(snap(.syncing)).needsAction)
        XCTAssertFalse(DeviceInsights.status(snap(.charging)).needsAction)
        XCTAssertTrue(DeviceInsights.status(snap(.lowBattery)).needsAction)
        XCTAssertTrue(DeviceInsights.status(snap(.bondLost)).needsAction)
        XCTAssertTrue(DeviceInsights.status(snap(.bluetoothOff)).needsAction)
    }

    func testLowBatteryDoesNotWarnWhileCharging() {
        var s = snap(.connected)
        s.battery = BatteryReading(percent: 10, charge: .charging)
        XCTAssertFalse(DeviceInsights.status(s).needsAction)
        s.battery = BatteryReading(percent: 15, charge: .notCharging)
        XCTAssertTrue(DeviceInsights.status(s).needsAction)
        s.battery = BatteryReading(percent: 16, charge: .notCharging)
        XCTAssertFalse(DeviceInsights.status(s).needsAction)
    }

    func testBatteryIsAlwaysApproximate() {
        XCTAssertEqual(DeviceInsights.batteryText(BatteryReading(percent: 64, charge: .notCharging)), "≈ 64 %")
        XCTAssertEqual(DeviceInsights.batteryText(BatteryReading(percent: nil, charge: .unknown)), "–")
        XCTAssertNil(DeviceInsights.chargeWord(BatteryReading(percent: 64, charge: .notCharging)))
        XCTAssertNotNil(DeviceInsights.chargeWord(BatteryReading(percent: 64, charge: .charging)))
        XCTAssertNotNil(DeviceInsights.chargeWord(BatteryReading(percent: nil, charge: .unknown)))
    }

    func testUpdateGateFollowsLinkAndBatteryThresholds() {
        var s = snap(.updateAvailable)
        XCTAssertEqual(DeviceInsights.updateGate(s), .ok)  // 64 % off the puck
        s.battery = BatteryReading(percent: 34, charge: .notCharging)
        XCTAssertEqual(DeviceInsights.updateGate(s), .needsCharge(percent: 50))
        s.battery = BatteryReading(percent: 34, charge: .charging)
        XCTAssertEqual(DeviceInsights.updateGate(s), .ok, "on the puck 30 % is enough")
        s.battery = BatteryReading(percent: 29, charge: .charging)
        XCTAssertEqual(DeviceInsights.updateGate(s), .needsCharge(percent: 30))
        s.battery = BatteryReading(percent: nil, charge: .unknown)
        XCTAssertEqual(DeviceInsights.updateGate(s), .needsCharge(percent: 50), "no estimate, no update")
        s.link = .outOfRange
        XCTAssertEqual(DeviceInsights.updateGate(s), .notConnected)
    }

    func testRowValues() {
        XCTAssertEqual(DeviceInsights.experimentalValue(snap(.connected)), L("device.exp.row.none"))
        var s = snap(.connected)
        s.spo2Enabled = true
        s.temperatureEnabled = true
        XCTAssertEqual(DeviceInsights.experimentalValue(s), L("device.exp.row.some", 2))
        XCTAssertEqual(DeviceInsights.updateValue(.transferring(0.425)), "43 %")
    }
}

@MainActor
final class DeviceModelTests: XCTestCase {
    private func wait(_ model: DeviceModel, until done: (FirmwareState) -> Bool) async {
        for _ in 0..<200 where !done(model.snapshot.firmware) { try? await Task.sleep(nanoseconds: 10_000_000) }
    }

    func testUpdateRunsToTheEndAndTakesTheNewVersion() async {
        let m = DeviceModel(snapshot: DeviceFixtures.snapshot(.updateAvailable), fast: true)
        m.startUpdate()
        await wait(m) { if case .done = $0 { return true } else { return false } }
        XCTAssertEqual(m.snapshot.firmware, .done(version: "0.3.0"))
        XCTAssertEqual(m.snapshot.firmwareVersion, "0.3.0")
    }

    func testFailedTransferKeepsTheOldVersionAndCanRetry() async {
        let m = DeviceModel(snapshot: DeviceFixtures.snapshot(.updateFailing), failTransfer: true, fast: true)
        m.startUpdate()
        await wait(m) { $0 == .failed }
        XCTAssertEqual(m.snapshot.firmware, .failed)
        XCTAssertEqual(m.snapshot.firmwareVersion, "0.2.1")
    }

    func testUpdateDoesNotStartBelowTheBatteryGate() {
        let m = DeviceModel(snapshot: DeviceFixtures.snapshot(.updateLowBattery), fast: true)
        m.startUpdate()
        XCTAssertEqual(m.snapshot.firmware, .available(version: "0.3.0"))
    }

    func testSwitchesRespectCapabilities() {
        var s = DeviceFixtures.snapshot(.connected)
        s.supportsSpO2 = false
        let m = DeviceModel(snapshot: s)
        m.setSpO2(true)
        m.setTemperature(true)
        XCTAssertFalse(m.snapshot.spo2Enabled)
        XCTAssertTrue(m.snapshot.temperatureEnabled)
    }

    func testDeleteClearsTheStoredDaysAndModeChanges() {
        let m = DeviceModel(snapshot: DeviceFixtures.snapshot(.connected))
        m.deleteData()
        XCTAssertEqual(m.snapshot.storedDays, 0)
        m.setMode(.raw)
        XCTAssertEqual(m.snapshot.mode, .raw)
    }
}
