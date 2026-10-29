import CasebackProtocol
import XCTest

@testable import Caseback

final class HandshakeTests: XCTestCase {
    func testHappyPathReadsInfoClockAndBattery() async throws {
        let peripheral = SimulatedPeripheral()
        var phases: [PairingPhase] = []
        let disc = try await Handshake.run(transport: peripheral, utcNow: { 1_760_000_000_000 }) { phases.append($0) }

        XCTAssertEqual(disc.name, "Caseback-E1F2")
        XCTAssertEqual(disc.deviceId, SimulatedPeripheral.defaultInfo.deviceId)
        XCTAssertEqual(disc.batteryPercent, 87)
        XCTAssertEqual(disc.bootId, 0xC0DE_FACE)
        XCTAssertEqual(disc.firmwareText, "fw 0.2")
        XCTAssertEqual(peripheral.lastAnchorUtcMs, 1_760_000_000_000, "the phone's UTC reaches the disc")
        XCTAssertEqual(phases, PairingPhase.allCases, "every phase is reported once, in order")
    }

    func testUnknownBatteryBecomesNil() async throws {
        let peripheral = SimulatedPeripheral(
            battery: Battery(voltageMv: 3900, charging: ChargingUnknown, percent: 0xFF, avgCurrentUa: [0, 0, 0, 0]))
        let disc = try await Handshake.run(transport: peripheral)
        XCTAssertNil(disc.batteryPercent)
        XCTAssertEqual(disc.charging, ChargingUnknown)
    }

    func testLostRepliesTimeOut() async {
        let peripheral = SimulatedPeripheral()
        peripheral.faults.dropRate = 1  // every notification is lost
        do {
            _ = try await Handshake.run(transport: peripheral, reply: .milliseconds(80))
            XCTFail("expected a timeout")
        } catch let failure as PairingFailure {
            guard case .timedOut = failure else { return XCTFail("wrong failure \(failure)") }
        } catch {
            XCTFail("unexpected error \(error)")
        }
    }

    func testCorruptedRepliesAreDroppedNotTrusted() async {
        let peripheral = SimulatedPeripheral()
        peripheral.faults.corruptCRCRate = 1
        do {
            _ = try await Handshake.run(transport: peripheral, reply: .milliseconds(80))
            XCTFail("a frame with a bad CRC must never be accepted")
        } catch let failure as PairingFailure {
            guard case .timedOut = failure else { return XCTFail("wrong failure \(failure)") }
        } catch {
            XCTFail("unexpected error \(error)")
        }
    }

    func testDuplicatedRepliesStillPair() async throws {
        let peripheral = SimulatedPeripheral()
        peripheral.faults.duplicateRate = 1
        let disc = try await Handshake.run(transport: peripheral)
        XCTAssertEqual(disc.name, "Caseback-E1F2")
    }

    func testSignalWordThresholds() {
        XCTAssertEqual(SignalWord(quality: 0), .poor)
        XCTAssertEqual(SignalWord(quality: 63), .poor)
        XCTAssertEqual(SignalWord(quality: 64), .fair)
        XCTAssertEqual(SignalWord(quality: 127), .fair)
        XCTAssertEqual(SignalWord(quality: 128), .good)
        XCTAssertEqual(SignalWord(quality: 191), .good)
        XCTAssertEqual(SignalWord(quality: 192), .strong)
        XCTAssertEqual(SignalWord(quality: 255), .strong)
    }
}
