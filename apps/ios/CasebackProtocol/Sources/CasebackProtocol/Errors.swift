import Foundation

/// Error taxonomy shared by framing, message decoding and the ERROR message (spec/messages.md).
public enum ErrorCode: UInt16, CaseIterable {
    case noError = 0x0000
    case truncated = 0x0001
    case badMagic = 0x0002
    case unsupportedVersion = 0x0003
    case payloadTooLong = 0x0004
    case lengthMismatch = 0x0005
    case badCRC = 0x0006
    case unknownMsgType = 0x0100
    case badPayloadLength = 0x0101
    case invalidField = 0x0102
    case unsupported = 0x0103
    case wrongDirection = 0x0104
    case linkNotEncrypted = 0x0200
    case busy = 0x0201
    case badState = 0x0202
    case noSuchStream = 0x0203
    case cursorOutOfRange = 0x0204
    case internalError = 0x0300
    /// local only, never sent on the wire
    case bufferTooSmall = 0xF001
    case nullArgument = 0xF002
}

public enum FrameError: Error, Equatable {
    case truncated
    case badMagic(UInt8)
    case unsupportedVersion(UInt8)
    case payloadTooLong(Int)
    case lengthMismatch(got: Int, want: Int)
    case crcMismatch(wire: UInt16, calc: UInt16)

    public var code: ErrorCode {
        switch self {
        case .truncated: return .truncated
        case .badMagic: return .badMagic
        case .unsupportedVersion: return .unsupportedVersion
        case .payloadTooLong: return .payloadTooLong
        case .lengthMismatch: return .lengthMismatch
        case .crcMismatch: return .badCRC
        }
    }
}

public enum MessageError: Error, Equatable {
    case wrongMessageType(UInt8)
    case badPayloadLength(got: Int, want: Int)
    /// `offset` is the payload offset of the first invalid field.
    case invalidField(offset: UInt8)

    public var code: ErrorCode {
        switch self {
        case .wrongMessageType: return .unknownMsgType
        case .badPayloadLength: return .badPayloadLength
        case .invalidField: return .invalidField
        }
    }

    /// The `detail` byte an ERROR message would carry for this error.
    public var detail: UInt8 {
        switch self {
        case .wrongMessageType: return 0
        case .badPayloadLength(_, let want): return UInt8(min(want, 255))
        case .invalidField(let offset): return offset
        }
    }
}
