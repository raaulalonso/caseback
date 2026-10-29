import XCTest
@testable import CasebackProtocol

final class FramingTests: XCTestCase {
    private func raw(protoVer: UInt8 = 1, type: UInt8 = 0x7F, declared: Int? = nil, payload: [UInt8] = []) -> Data {
        let n = declared ?? payload.count
        var body = Data([CasebackMagic, protoVer, type, UInt8(n & 0xFF), UInt8(n >> 8)])
        body.append(contentsOf: payload)
        let crc = CRC16.ccittFalse(body)
        body.append(UInt8(crc & 0xFF))
        body.append(UInt8(crc >> 8))
        return body
    }

    private func frameError(_ data: Data, file: StaticString = #filePath, line: UInt = #line) -> FrameError? {
        do {
            _ = try decodeFrame(data)
            XCTFail("expected an error", file: file, line: line)
            return nil
        } catch {
            return error as? FrameError
        }
    }

    func testLimits() {
        XCTAssertEqual(CasebackMaxPayload, 175)
        XCTAssertEqual(CasebackMaxFrame, 182)
        XCTAssertEqual(CasebackMaxFrame, 185 - 3)
    }

    func testEncodeLayout() throws {
        let raw = try Frame(msgType: 0x02, payload: Data([0x01, 0x02])).encoded()
        XCTAssertEqual(raw[0], 0xA5)
        XCTAssertEqual(raw[1], 0x01)
        XCTAssertEqual(raw[2], 0x02)
        XCTAssertEqual(UInt16(raw[3]) | (UInt16(raw[4]) << 8), 2)
        XCTAssertEqual(Data(raw[5..<7]), Data([0x01, 0x02]))
        XCTAssertEqual(raw.count, 9)
    }

    func testRoundtripEmptyPayload() throws {
        let decoded = try decodeFrame(try Frame(msgType: 0x01, payload: Data()).encoded())
        XCTAssertEqual(decoded.msgType, 0x01)
        XCTAssertTrue(decoded.payload.isEmpty)
        XCTAssertEqual(decoded.protoVer, 0x01)
    }

    func testRoundtripWithPayload() throws {
        let payload = Data(0..<32)
        let decoded = try decodeFrame(try Frame(msgType: 0x10, payload: payload).encoded())
        XCTAssertEqual(decoded.msgType, 0x10)
        XCTAssertEqual(decoded.payload, payload)
    }

    func testMaxPayloadRoundtrip() throws {
        let payload = Data(repeating: 0xAB, count: CasebackMaxPayload)
        let wire = try Frame(msgType: 0x7F, payload: payload).encoded()
        XCTAssertEqual(wire.count, CasebackMaxFrame)
        XCTAssertEqual(try decodeFrame(wire).payload, payload)
    }

    func testOversizePayload() {
        XCTAssertEqual(frameError(raw(payload: [UInt8](repeating: 0, count: 176))), .payloadTooLong(176))
        XCTAssertEqual(frameError(raw(payload: [UInt8](repeating: 0, count: 512))), .payloadTooLong(512))
    }

    func testEncodeOversizeThrowsInsteadOfCrashing() {
        let frame = Frame(msgType: 0x01, payload: Data(count: CasebackMaxPayload + 1))
        XCTAssertThrowsError(try frame.encoded()) { error in
            XCTAssertEqual(error as? FrameError, .payloadTooLong(CasebackMaxPayload + 1))
        }
    }

    func testBadMagic() {
        var wire = raw()
        wire[0] = 0
        XCTAssertEqual(frameError(wire), .badMagic(0))
    }

    func testBadCRC() {
        var wire = raw()
        wire[wire.count - 1] ^= 0xFF
        guard case .crcMismatch? = frameError(wire) else { return XCTFail("expected crcMismatch") }
    }

    func testUnsupportedVersion() {
        for v: UInt8 in [0, 2, 0xFF] {
            XCTAssertEqual(frameError(raw(protoVer: v)), .unsupportedVersion(v))
        }
    }

    func testTruncatedVariants() {
        let wire = raw(payload: [0xAA])
        XCTAssertEqual(frameError(Data()), .truncated)
        XCTAssertEqual(frameError(wire.prefix(1)), .truncated)
        XCTAssertEqual(frameError(wire.prefix(4)), .truncated)
        XCTAssertEqual(frameError(wire.dropLast()), .truncated)
        XCTAssertEqual(frameError(raw(declared: 8, payload: [1, 2, 3])), .truncated)
    }

    func testLengthMismatchTrailingBytes() {
        XCTAssertEqual(frameError(raw(payload: [0, 0]) + Data([0])), .lengthMismatch(got: 10, want: 9))
        XCTAssertEqual(frameError(raw(declared: 3, payload: [0x11, 0x22, 0x33, 0x44, 0x55])),
                       .lengthMismatch(got: 12, want: 10))
    }

    func testDecodeErrorOrder() {
        XCTAssertEqual(frameError(Data([0x5A, 0x02, 0x01, 0x00, 0x00, 0, 0])), .badMagic(0x5A))
        XCTAssertEqual(frameError(Data([0xA5, 0x02, 0x7F, 0xF4, 0x01])), .unsupportedVersion(2))
        XCTAssertEqual(frameError(Data([0xA5, 0x01, 0x7F, 0xB0, 0x00, 0, 0])), .payloadTooLong(176))
    }

    func testUnassignedMsgTypeDecodes() throws {
        XCTAssertEqual(try decodeFrame(raw(type: 0xFE)).msgType, 0xFE)
    }

    func testDecodeAcceptsDataSliceWithNonZeroStartIndex() throws {
        let wire = try Frame(msgType: 0x10, payload: Data([1, 2, 3])).encoded()
        let padded = Data([0xFF, 0xEE, 0xDD]) + wire
        let slice = padded[3...]
        XCTAssertEqual(slice.startIndex, 3)
        XCTAssertEqual(try decodeFrame(slice).payload, Data([1, 2, 3]))
    }

    func testErrorCodesMatchTheSpecValues() {
        let expect: [(ErrorCode, UInt16)] = [
            (.truncated, 1), (.badMagic, 2), (.unsupportedVersion, 3), (.payloadTooLong, 4),
            (.lengthMismatch, 5), (.badCRC, 6), (.unknownMsgType, 0x100), (.badPayloadLength, 0x101),
            (.invalidField, 0x102), (.unsupported, 0x103), (.wrongDirection, 0x104),
            (.linkNotEncrypted, 0x200), (.busy, 0x201), (.badState, 0x202), (.noSuchStream, 0x203),
            (.cursorOutOfRange, 0x204), (.internalError, 0x300), (.bufferTooSmall, 0xF001),
            (.nullArgument, 0xF002),
        ]
        for (code, value) in expect { XCTAssertEqual(code.rawValue, value) }
    }
}
