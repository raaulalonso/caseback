import XCTest
@testable import CasebackProtocol

final class SimulatedPeripheralTests: XCTestCase {
    typealias Frames = AsyncStream<Data>.Iterator

    private func connected(seed: UInt64 = 1, clock: SimClock = SimClock()) async throws
        -> (SimulatedPeripheral, Frames)
    {
        let peripheral = SimulatedPeripheral(seed: seed, clock: clock)
        try await peripheral.connect()
        return (peripheral, peripheral.notifications().makeAsyncIterator())
    }

    private func next(_ it: inout Frames) async throws -> Frame {
        let next = await it.next()
        let data = try XCTUnwrap(next, "stream ended")
        return try decodeFrame(data)
    }

    /// Disconnects and returns everything that was still queued.
    private func drain(_ p: SimulatedPeripheral, _ it: inout Frames) async -> [Data] {
        await p.disconnect()
        var out: [Data] = []
        while let d = await it.next() { out.append(d) }
        return out
    }

    func testWritesRequireAConnection() async throws {
        let p = SimulatedPeripheral()
        do {
            try await p.writeControl(try encodeInfoRequest())
            XCTFail("expected notConnected")
        } catch {
            XCTAssertEqual(error as? TransportError, .notConnected)
        }
        var it = p.notifications().makeAsyncIterator()
        let none = await it.next()
        XCTAssertNil(none)
    }

    func testConnectTwiceThrows() async throws {
        let p = SimulatedPeripheral()
        try await p.connect()
        do {
            try await p.connect()
            XCTFail("expected alreadyConnected")
        } catch {
            XCTAssertEqual(error as? TransportError, .alreadyConnected)
        }
    }

    func testInfoRequestAndInfoCharacteristic() async throws {
        var (p, it) = try await connected()
        try await p.writeControl(try encodeInfoRequest())
        let frame = try await next(&it)
        XCTAssertEqual(try decodeInfoResponse(frame), SimulatedPeripheral.defaultInfo)
        let read = try await p.readInfo()
        XCTAssertEqual(read, try encodeInfoResponseFrame(SimulatedPeripheral.defaultInfo))
    }

    func testTimeAnchorAnswersWithBootIdAndUptime() async throws {
        let clock = SimClock(uptimeMs: 1_000)
        var (p, it) = try await connected(clock: clock)
        clock.advance(ms: 234)
        try await p.writeControl(try encodeTimeAnchorRequestFrame(Golden.anchorRequest))
        let frame = try await next(&it)
        XCTAssertEqual(try decodeTimeAnchorReply(frame), TimeAnchorReply(bootId: p.bootId, uptimeMs: 1_234))
        XCTAssertEqual(p.lastAnchorUtcMs, Golden.anchorRequest.utcMs)
    }

    func testConfigSetIsAppliedAndEchoedAsState() async throws {
        var (p, it) = try await connected()
        try await p.writeControl(try encodeConfigSetFrame(Golden.configSet))
        let echo = try await next(&it)
        XCTAssertEqual(try decodeConfigStateFrame(echo), Golden.configSet)
        XCTAssertEqual(p.config, Golden.configSet)
        try await p.writeControl(try encodeConfigQueryFrame())
        let state = try await next(&it)
        XCTAssertEqual(try decodeConfigStateFrame(state), Golden.configSet)
    }

    func testInvalidConfigIsRejectedWithErrorAndNotApplied() async throws {
        var (p, it) = try await connected()
        var payload = [UInt8](try Golden.configSet.payload())
        payload[14] = 0x08
        try await p.writeControl(try Frame(msgType: MSGConfigSet, payload: Data(payload)).encoded())
        let frame = try await next(&it)
        XCTAssertEqual(try decodeErrorMessage(frame), ErrorMessage(.invalidField, msgType: MSGConfigSet, detail: 14))
        XCTAssertEqual(p.config, SimulatedPeripheral.defaultConfig)
    }

    func testBatteryOnQueryAndUnsolicited() async throws {
        var (p, it) = try await connected()
        try await p.writeControl(try encodeBatteryQueryFrame())
        let first = try await next(&it)
        XCTAssertEqual(try decodeBatteryFrame(first), p.battery)
        p.battery.charging = ChargingCharging
        p.emitBattery()
        let second = try await next(&it)
        XCTAssertEqual(try decodeBatteryFrame(second).charging, ChargingCharging)
    }

    func testUnknownAndMalformedInputGetErrors() async throws {
        var (p, it) = try await connected()
        try await p.writeControl(try Frame(msgType: 0x7F, payload: Data()).encoded())
        var frame = try await next(&it)
        XCTAssertEqual(try decodeErrorMessage(frame), ErrorMessage(.unknownMsgType, msgType: 0x7F))
        var bad = try encodeInfoRequest()
        bad[bad.count - 1] ^= 0xFF
        try await p.writeControl(bad)
        frame = try await next(&it)
        XCTAssertEqual(try decodeErrorMessage(frame).code, ErrorCode.badCRC.rawValue)
        try await p.writeControl(try encodeTimeAnchorReplyFrame(Golden.anchorReply))
        frame = try await next(&it)
        XCTAssertEqual(try decodeErrorMessage(frame).code, ErrorCode.badPayloadLength.rawValue)
        try await p.writeControl(try encodeConfigStateFrame(Golden.configState))
        frame = try await next(&it)
        XCTAssertEqual(try decodeErrorMessage(frame).code, ErrorCode.wrongDirection.rawValue)
    }

    func testFrameLargerThanMTUIsRefused() async throws {
        let (p, _) = try await connected()
        p.attMTU = 23
        do {
            try await p.writeControl(try encodeConfigSetFrame(Golden.configSet))
            XCTFail("expected frameTooLarge")
        } catch {
            XCTAssertEqual(error as? TransportError, .frameTooLarge(33))
        }
    }

    // MARK: fault injection

    func testDropLosesTheReply() async throws {
        var (p, it) = try await connected()
        p.faults.dropRate = 1
        try await p.writeControl(try encodeInfoRequest())
        let frames = await drain(p, &it)
        XCTAssertTrue(frames.isEmpty)
    }

    func testDuplicateDeliversTheReplyTwice() async throws {
        var (p, it) = try await connected()
        p.faults.duplicateRate = 1
        try await p.writeControl(try encodeInfoRequest())
        let frames = await drain(p, &it)
        XCTAssertEqual(frames.count, 2)
        XCTAssertEqual(frames[0], frames[1])
    }

    func testReorderSwapsTwoConsecutiveReplies() async throws {
        var (p, it) = try await connected()
        p.faults.reorderRate = 1
        try await p.writeControl(try encodeInfoRequest())
        try await p.writeControl(try encodeBatteryQueryFrame())
        let frames = try await drain(p, &it).map(decodeFrame)
        XCTAssertEqual(frames.map(\.msgType), [MSGBattery, MSGInfoResponse])
    }

    func testHeldFrameIsReleasedByFlush() async throws {
        var (p, it) = try await connected()
        p.faults.reorderRate = 1
        try await p.writeControl(try encodeInfoRequest())
        p.flush()
        let frames = await drain(p, &it)
        XCTAssertEqual(frames.count, 1)
    }

    func testCorruptCRCIsDetectedByTheDecoder() async throws {
        var (p, it) = try await connected()
        p.faults.corruptCRCRate = 1
        try await p.writeControl(try encodeInfoRequest())
        let next = await it.next()
        let data = try XCTUnwrap(next)
        XCTAssertThrowsError(try decodeFrame(data)) {
            XCTAssertEqual(($0 as? FrameError)?.code, .badCRC)
        }
    }

    func testDisconnectAfterNNotifications() async throws {
        var (p, it) = try await connected()
        p.faults.disconnectAfterNotifications = 1
        try await p.writeControl(try encodeInfoRequest())
        _ = try await next(&it)
        let end = await it.next()
        XCTAssertNil(end)
        XCTAssertFalse(p.isConnected)
        do {
            try await p.writeControl(try encodeInfoRequest())
            XCTFail("expected notConnected")
        } catch {
            XCTAssertEqual(error as? TransportError, .notConnected)
        }
    }

    func testReconnectGivesAFreshStream() async throws {
        let (p, _) = try await connected()
        await p.disconnect()
        try await p.connect()
        var it = p.notifications().makeAsyncIterator()
        try await p.writeControl(try encodeInfoRequest())
        let frame = try await next(&it)
        XCTAssertEqual(frame.msgType, MSGInfoResponse)
    }

    func testSameSeedGivesTheSameFaultSequence() async throws {
        func delivered(seed: UInt64) async throws -> [Data] {
            var (p, it) = try await connected(seed: seed)
            p.faults.dropRate = 0.5
            for _ in 0..<40 { try await p.writeControl(try encodeInfoRequest()) }
            return await drain(p, &it)
        }
        let a = try await delivered(seed: 42)
        let b = try await delivered(seed: 42)
        XCTAssertEqual(a.count, b.count)
        XCTAssertTrue(a.count > 5 && a.count < 35, "\(a.count)")
    }

    func testSeededGeneratorIsStable() {
        var g = SeededGenerator(seed: 0)
        XCTAssertEqual(g.next(), 0xE220_A839_7B1D_CDAF)
        XCTAssertEqual(g.next(), 0x6E78_9E6A_A1B9_65F4)
    }
}
