import XCTest
@testable import CasebackProtocol

/// Values shared with Python, C and spec/messages.md.
enum Golden {
    static let info = InfoResponse(
        deviceId: [0x8B, 0x9C, 0xAD, 0xBE, 0xCF, 0xD0, 0xE1, 0xF2],
        hwRev: 0x8102, fwRev: 0x9304,
        capabilities: CAPPPGRaw | CAPPPGSummary | CAPIBILog | CAPEncryptedOnly
    )
    static let error = ErrorMessage(code: 0x0102, msgType: 0x20, detail: 0x0C)
    static let errorUnknown = ErrorMessage(code: 0x9ABC, msgType: 0xC7, detail: 0xE1)
    static let anchorRequest = TimeAnchorRequest(utcMs: 0x0000_01A2_B3C4_D5E6)
    static let anchorReply = TimeAnchorReply(bootId: 0xC0DE_FACE, uptimeMs: 0x0000_00E4_D3C2_B1A0)
    static let configSet = Config(
        mode: 2, payloadFormat: 1, ppgRateHz: [25, 200, 100, 400], burstPeriodS: 300, burstLenS: 30,
        ledMask: 0b101, ledGreenMa: 42, ledRedMa: 27, ledIrMa: 33, wearPpgDc: 0x0005_B7C9,
        wearMotionThr: 500, wearProbePeriodMs: 1000
    )
    static let configState = Config(
        mode: 1, payloadFormat: 0, ppgRateHz: [48, 32, 128, 400], burstPeriodS: 600, burstLenS: 45,
        ledMask: 0b111, ledGreenMa: 60, ledRedMa: 52, ledIrMa: 41, wearPpgDc: 0x0007_FFFF,
        wearMotionThr: 3000, wearProbePeriodMs: 5000
    )
    static let battery = Battery(voltageMv: 4013, charging: 1, percent: 87, avgCurrentUa: [210, 854, 6699, 15758])
}

final class MessagesTests: XCTestCase {
    func testConstants() {
        XCTAssertEqual([MSGInfoRequest, MSGInfoResponse, MSGError, MSGTimeAnchor], [1, 2, 3, 4])
        XCTAssertEqual([MSGConfigSet, MSGConfigState, MSGBattery], [0x20, 0x21, 0x22])
        XCTAssertEqual(
            [CAPPPGRaw, CAPPPGSummary, CAPAccel, CAPSpO2, CAPTemperature, CAPDFUSMP, CAPIBILog, CAPEncryptedOnly],
            [1, 2, 4, 8, 16, 32, 64, 128])
        XCTAssertEqual(GATTServiceUUID, "decdc7df-2ecb-4d75-b44c-992dccdfca5b")
        XCTAssertEqual(GATTInfoUUID, "decdc7e0-2ecb-4d75-b44c-992dccdfca5b")
        XCTAssertEqual(GATTControlUUID, "decdc7e1-2ecb-4d75-b44c-992dccdfca5b")
        XCTAssertEqual(GATTDataUUID, "decdc7e2-2ecb-4d75-b44c-992dccdfca5b")
    }

    func testInfoResponsePayloadLayout() throws {
        let resp = InfoResponse(
            deviceId: [1, 2, 3, 4, 5, 6, 7, 8], hwRev: 0x0100, fwRev: 0x0002, capabilities: 0b100001)
        XCTAssertEqual(try resp.payload(), Data([1, 2, 3, 4, 5, 6, 7, 8, 0x00, 0x01, 0x02, 0x00, 0x21, 0, 0, 0]))
    }

    func testInfoResponseRoundtripAndFrameVariant() throws {
        XCTAssertEqual(try decodeInfoResponse(try Golden.info.payload()), Golden.info)
        let frame = try decodeFrame(try encodeInfoResponseFrame(Golden.info))
        XCTAssertEqual(try decodeInfoResponse(frame), Golden.info)
        let request = try decodeFrame(try encodeInfoRequest())
        XCTAssertThrowsError(try decodeInfoResponse(request)) { error in
            XCTAssertEqual((error as? MessageError)?.code, .unknownMsgType)
        }
    }

    func testDecodeInfoResponseAcceptsSlicesWithNonZeroStartIndex() throws {
        let payload = try Golden.info.payload()
        let slice = (Data([9, 9, 9, 9]) + payload)[4...]
        XCTAssertEqual(slice.startIndex, 4)
        XCTAssertEqual(try decodeInfoResponse(slice), Golden.info)
    }

    func testInfoErrorsThrowInsteadOfTrapping() {
        XCTAssertThrowsError(try InfoResponse(deviceId: [1], hwRev: 0, fwRev: 0, capabilities: 0).payload()) {
            XCTAssertEqual(($0 as? MessageError)?.code, .invalidField)
        }
        for n in [0, 15, 17] {
            XCTAssertThrowsError(try decodeInfoResponse(Data(count: n))) {
                XCTAssertEqual($0 as? MessageError, .badPayloadLength(got: n, want: 16))
            }
        }
    }

    func testErrorMessage() throws {
        XCTAssertEqual(try Golden.error.payload(), Data([0x02, 0x01, 0x20, 0x0C]))
        XCTAssertEqual(Golden.error.known, .invalidField)
        XCTAssertNil(Golden.errorUnknown.known)
        for m in [Golden.error, Golden.errorUnknown] {
            XCTAssertEqual(try decodeErrorMessage(try decodeFrame(try encodeErrorFrame(m))), m)
        }
        XCTAssertThrowsError(try decodeErrorMessage(Data(count: 3)))
    }

    func testTimeAnchor() throws {
        XCTAssertEqual(try Golden.anchorRequest.payload(), Data([0xE6, 0xD5, 0xC4, 0xB3, 0xA2, 0x01, 0, 0]))
        XCTAssertEqual(try Golden.anchorReply.payload(),
                       Data([0xCE, 0xFA, 0xDE, 0xC0, 0xA0, 0xB1, 0xC2, 0xD3, 0xE4, 0, 0, 0]))
        let req = try decodeFrame(try encodeTimeAnchorRequestFrame(Golden.anchorRequest))
        XCTAssertEqual(try decodeTimeAnchorRequest(req), Golden.anchorRequest)
        XCTAssertThrowsError(try decodeTimeAnchorReply(req))
        let rep = try decodeFrame(try encodeTimeAnchorReplyFrame(Golden.anchorReply))
        XCTAssertEqual(try decodeTimeAnchorReply(rep), Golden.anchorReply)
        let big = TimeAnchorRequest(utcMs: UInt64.max)
        XCTAssertEqual(try decodeTimeAnchorRequest(try big.payload()), big)
    }

    func testConfigLayoutAndRoundtrip() throws {
        let payload = try Golden.configSet.payload()
        XCTAssertEqual(payload.count, 26)
        let hex = payload.map { String(format: "%02x", $0) }.joined()
        XCTAssertEqual(hex, "0201" + "1900c800" + "64009001" + "2c01" + "1e00" + "05" + "2a1b21" + "c9b70500" + "f401" + "e803")
        XCTAssertEqual(try decodeConfig(payload), Golden.configSet)
        let frame = try decodeFrame(try encodeConfigSetFrame(Golden.configSet))
        XCTAssertEqual(try decodeConfigSetFrame(frame), Golden.configSet)
        XCTAssertThrowsError(try decodeConfigStateFrame(frame))
    }

    func testConfigInvalidFieldsReportOffsets() throws {
        let base = [UInt8](try Golden.configSet.payload())
        let cases: [(offset: Int, patch: [(Int, UInt8)])] = [
            (0, [(0, 4)]), (1, [(1, 2)]), (2, [(3, 0x91)]), (8, [(9, 0xFF)]), (12, [(12, 0x2D), (13, 0x01)]),
            (14, [(14, 0x08)]),
        ]
        for c in cases {
            var p = base
            for (i, v) in c.patch { p[i] = v }
            XCTAssertThrowsError(try decodeConfig(Data(p)), "offset \(c.offset)") {
                XCTAssertEqual($0 as? MessageError, .invalidField(offset: UInt8(c.offset)))
            }
        }
        XCTAssertThrowsError(try decodeConfig(Data(count: 25))) {
            XCTAssertEqual(($0 as? MessageError)?.code, .badPayloadLength)
        }
    }

    func testConfigEncodeValidates() {
        var cfg = Golden.configSet
        cfg.ledMask = 0x0F
        XCTAssertThrowsError(try cfg.payload())
        cfg = Golden.configSet
        cfg.burstPeriodS = 0
        cfg.burstLenS = 1
        XCTAssertThrowsError(try cfg.payload())
        cfg.burstLenS = 0
        XCTAssertNoThrow(try cfg.payload())
    }

    func testBatteryLayoutAndValidation() throws {
        let payload = try Golden.battery.payload()
        XCTAssertEqual(payload.map { String(format: "%02x", $0) }.joined(), "ad0f0157" + "d2005603" + "2b1a8e3d")
        XCTAssertEqual(try decodeBattery(payload), Golden.battery)
        XCTAssertEqual(try decodeBatteryFrame(try decodeFrame(try encodeBatteryFrame(Golden.battery))), Golden.battery)
        let unknown = Battery(voltageMv: 0, charging: ChargingUnknown, percent: PercentUnknown, avgCurrentUa: [0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF])
        XCTAssertEqual(try decodeBattery(try unknown.payload()), unknown)
        XCTAssertThrowsError(try Battery(voltageMv: 1, charging: 4, percent: 1, avgCurrentUa: [0, 0, 0, 0]).payload())
        XCTAssertThrowsError(try Battery(voltageMv: 1, charging: 1, percent: 101, avgCurrentUa: [0, 0, 0, 0]).payload())
        XCTAssertThrowsError(try decodeBattery(Data(count: 11)))
    }
}
