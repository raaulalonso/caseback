import Foundation

public struct Frame: Equatable {
    public let msgType: UInt8
    public let payload: Data
    public let protoVer: UInt8

    public init(msgType: UInt8, payload: Data, protoVer: UInt8 = CasebackProtoVer) {
        self.msgType = msgType
        self.payload = payload
        self.protoVer = protoVer
    }

    /// Throws `FrameError.payloadTooLong` when the payload exceeds `CasebackMaxPayload`.
    public func encoded() throws -> Data {
        guard payload.count <= CasebackMaxPayload else { throw FrameError.payloadTooLong(payload.count) }
        var body = Data([CasebackMagic, protoVer, msgType])
        let len = UInt16(payload.count)
        body.append(UInt8(len & 0xFF))
        body.append(UInt8(len >> 8))
        body.append(payload)
        let crc = CRC16.ccittFalse(body)
        body.append(UInt8(crc & 0xFF))
        body.append(UInt8(crc >> 8))
        return body
    }
}

/// Checks in order: magic, version, oversize, truncated, length mismatch, CRC (spec/framing.md).
public func decodeFrame(_ data: Data) throws -> Frame {
    let b = [UInt8](data)  // zero-based copy, safe for slices with a non-zero startIndex
    guard b.count >= 1 else { throw FrameError.truncated }
    guard b[0] == CasebackMagic else { throw FrameError.badMagic(b[0]) }
    guard b.count >= 2 else { throw FrameError.truncated }
    guard b[1] == CasebackProtoVer else { throw FrameError.unsupportedVersion(b[1]) }
    guard b.count >= CasebackHeaderLen else { throw FrameError.truncated }
    let payloadLen = Int(b[3]) | (Int(b[4]) << 8)
    guard payloadLen <= CasebackMaxPayload else { throw FrameError.payloadTooLong(payloadLen) }
    let expected = CasebackHeaderLen + payloadLen + CASEBACKCRCLen
    guard b.count >= expected else { throw FrameError.truncated }
    guard b.count == expected else { throw FrameError.lengthMismatch(got: b.count, want: expected) }
    let wire = UInt16(b[expected - 2]) | (UInt16(b[expected - 1]) << 8)
    let calc = CRC16.ccittFalse(Data(b[0..<(expected - CASEBACKCRCLen)]))
    guard wire == calc else { throw FrameError.crcMismatch(wire: wire, calc: calc) }
    return Frame(
        msgType: b[2],
        payload: Data(b[CasebackHeaderLen..<(CasebackHeaderLen + payloadLen)]),
        protoVer: b[1]
    )
}
