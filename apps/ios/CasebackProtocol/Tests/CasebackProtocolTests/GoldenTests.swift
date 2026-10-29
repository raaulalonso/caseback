import XCTest
@testable import CasebackProtocol

final class GoldenTests: XCTestCase {
    // Hand-derived vectors of spec/messages.md.
    private let specVectors: [String: [UInt8]] = [
        "info_request": [0xA5, 0x01, 0x01, 0x00, 0x00, 0xBB, 0x59],
        "info_response": [
            0xA5, 0x01, 0x02, 0x10, 0x00, 0x8B, 0x9C, 0xAD, 0xBE, 0xCF, 0xD0, 0xE1, 0xF2, 0x02, 0x81, 0x04,
            0x93, 0xC3, 0x00, 0x00, 0x00, 0x82, 0xBB,
        ],
        "error": [0xA5, 0x01, 0x03, 0x04, 0x00, 0x02, 0x01, 0x20, 0x0C, 0x32, 0xF3],
        "time_anchor_request": [
            0xA5, 0x01, 0x04, 0x08, 0x00, 0xE6, 0xD5, 0xC4, 0xB3, 0xA2, 0x01, 0x00, 0x00, 0x1B, 0x68,
        ],
        "time_anchor_reply": [
            0xA5, 0x01, 0x04, 0x0C, 0x00, 0xCE, 0xFA, 0xDE, 0xC0, 0xA0, 0xB1, 0xC2, 0xD3, 0xE4, 0x00, 0x00,
            0x00, 0x26, 0x9F,
        ],
    ]

    func testManifestDrivesEveryFixture() throws {
        let entries = try Fixtures.manifest()
        XCTAssertGreaterThanOrEqual(entries.count, 20)
        for entry in entries {
            let data = try Data(contentsOf: try Fixtures.url(named: entry.file))
            if entry.status == "ok" {
                let frame = try decodeFrame(data)
                XCTAssertEqual(frame.msgType, entry.msgType, entry.file)
                XCTAssertEqual(frame.payload.count, entry.payloadLen, entry.file)
                XCTAssertEqual(try frame.encoded(), data, entry.file)
            } else {
                XCTAssertThrowsError(try decodeFrame(data), entry.file) { error in
                    guard let e = error as? FrameError else { return XCTFail("\(entry.file): \(error)") }
                    XCTAssertEqual(Fixtures.errorName(e.code), entry.status, entry.file)
                }
            }
        }
    }

    func testEverySpecVectorEqualsTheGoldenFile() throws {
        for (name, bytes) in specVectors {
            XCTAssertEqual(try Fixtures.data(named: name), Data(bytes), name)
        }
    }

    func testMessageLevelDecodeOfEveryPositiveGolden() throws {
        func frame(_ name: String) throws -> Frame { try decodeFrame(try Fixtures.data(named: name)) }
        XCTAssertEqual(try decodeInfoResponse(frame("info_response")), Golden.info)
        XCTAssertEqual(try decodeErrorMessage(frame("error")), Golden.error)
        XCTAssertEqual(try decodeErrorMessage(frame("error_unknown_code")), Golden.errorUnknown)
        XCTAssertEqual(try decodeTimeAnchorRequest(frame("time_anchor_request")), Golden.anchorRequest)
        XCTAssertEqual(try decodeTimeAnchorReply(frame("time_anchor_reply")), Golden.anchorReply)
        XCTAssertEqual(try decodeConfigSetFrame(frame("config_set")), Golden.configSet)
        XCTAssertEqual(try decodeConfigStateFrame(frame("config_state")), Golden.configState)
        XCTAssertEqual(try decodeBatteryFrame(frame("battery")), Golden.battery)
        for name in ["info_request", "config_query", "battery_query"] {
            XCTAssertTrue(try frame(name).payload.isEmpty, name)
        }
        XCTAssertEqual(try frame("max_payload").payload.count, CasebackMaxPayload)
        XCTAssertEqual(try frame("a5_payload").payload.count, 21)
    }

    func testSwiftEncodersReproduceTheGoldenFiles() throws {
        let cases: [(String, Data)] = [
            ("info_request", try encodeInfoRequest()),
            ("info_response", try encodeInfoResponseFrame(Golden.info)),
            ("error", try encodeErrorFrame(Golden.error)),
            ("error_unknown_code", try encodeErrorFrame(Golden.errorUnknown)),
            ("time_anchor_request", try encodeTimeAnchorRequestFrame(Golden.anchorRequest)),
            ("time_anchor_reply", try encodeTimeAnchorReplyFrame(Golden.anchorReply)),
            ("config_query", try encodeConfigQueryFrame()),
            ("config_set", try encodeConfigSetFrame(Golden.configSet)),
            ("config_state", try encodeConfigStateFrame(Golden.configState)),
            ("battery_query", try encodeBatteryQueryFrame()),
            ("battery", try encodeBatteryFrame(Golden.battery)),
        ]
        for (name, bytes) in cases { XCTAssertEqual(bytes, try Fixtures.data(named: name), name) }
    }
}
