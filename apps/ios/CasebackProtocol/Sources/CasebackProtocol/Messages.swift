import Foundation

// Message codecs (proto_ver 0x01, spec v0.2).
// Implemented: INFO, ERROR, TIME_ANCHOR, CONFIG_SET/CONFIG_STATE, BATTERY.
// STREAM_DATA, STREAM_CONTROL, HISTORY_QUERY and HISTORY_ACK are specified only.

public let CasebackDeviceIdLen = 8
public let CasebackInfoPayloadLen = 16
public let CasebackErrorPayloadLen = 4
public let CasebackTimeAnchorRequestLen = 8
public let CasebackTimeAnchorReplyLen = 12
public let CasebackConfigPayloadLen = 26
public let CasebackBatteryPayloadLen = 12

// MARK: little-endian helpers

private struct Writer {
    var data = Data()
    mutating func u8(_ v: UInt8) { data.append(v) }
    mutating func le<T: FixedWidthInteger>(_ v: T) {
        var x = v.littleEndian
        withUnsafeBytes(of: &x) { data.append(contentsOf: $0) }
    }
}

private struct Reader {
    let b: [UInt8]
    var pos = 0
    init(_ payload: Data, expecting want: Int) throws {
        guard payload.count == want else {
            throw MessageError.badPayloadLength(got: payload.count, want: want)
        }
        b = [UInt8](payload)  // zero-based copy: safe for Data slices
    }
    mutating func u8() -> UInt8 {
        defer { pos += 1 }
        return b[pos]
    }
    mutating func le<T: FixedWidthInteger>(_ type: T.Type) -> T {
        var v: T = 0
        for i in 0..<MemoryLayout<T>.size { v |= T(b[pos + i]) << (8 * i) }
        pos += MemoryLayout<T>.size
        return v
    }
}

private func requireType(_ frame: Frame, _ type: UInt8) throws {
    guard frame.msgType == type else { throw MessageError.wrongMessageType(frame.msgType) }
}

// MARK: INFO

public struct InfoResponse: Equatable {
    public let deviceId: [UInt8]
    public let hwRev: UInt16
    public let fwRev: UInt16
    public let capabilities: UInt32

    public init(deviceId: [UInt8], hwRev: UInt16, fwRev: UInt16, capabilities: UInt32) {
        self.deviceId = deviceId
        self.hwRev = hwRev
        self.fwRev = fwRev
        self.capabilities = capabilities
    }

    public func payload() throws -> Data {
        guard deviceId.count == CasebackDeviceIdLen else { throw MessageError.invalidField(offset: 0) }
        var w = Writer()
        deviceId.forEach { w.u8($0) }
        w.le(hwRev)
        w.le(fwRev)
        w.le(capabilities)
        return w.data
    }
}

public func decodeInfoResponse(_ payload: Data) throws -> InfoResponse {
    var r = try Reader(payload, expecting: CasebackInfoPayloadLen)
    let deviceId = (0..<CasebackDeviceIdLen).map { _ in r.u8() }
    return InfoResponse(
        deviceId: deviceId,
        hwRev: r.le(UInt16.self),
        fwRev: r.le(UInt16.self),
        capabilities: r.le(UInt32.self)
    )
}

public func decodeInfoResponse(_ frame: Frame) throws -> InfoResponse {
    try requireType(frame, MSGInfoResponse)
    return try decodeInfoResponse(frame.payload)
}

public func encodeInfoRequest() throws -> Data {
    try Frame(msgType: MSGInfoRequest, payload: Data()).encoded()
}

public func encodeInfoResponseFrame(_ info: InfoResponse) throws -> Data {
    try Frame(msgType: MSGInfoResponse, payload: info.payload()).encoded()
}

// MARK: ERROR

public struct ErrorMessage: Equatable {
    /// An `ErrorCode` raw value, or any u16 from a newer peer.
    public let code: UInt16
    public let msgType: UInt8
    public let detail: UInt8

    public init(code: UInt16, msgType: UInt8, detail: UInt8 = 0) {
        self.code = code
        self.msgType = msgType
        self.detail = detail
    }

    public init(_ code: ErrorCode, msgType: UInt8, detail: UInt8 = 0) {
        self.init(code: code.rawValue, msgType: msgType, detail: detail)
    }

    public var known: ErrorCode? { ErrorCode(rawValue: code) }

    public func payload() throws -> Data {
        var w = Writer()
        w.le(code)
        w.u8(msgType)
        w.u8(detail)
        return w.data
    }
}

public func decodeErrorMessage(_ payload: Data) throws -> ErrorMessage {
    var r = try Reader(payload, expecting: CasebackErrorPayloadLen)
    return ErrorMessage(code: r.le(UInt16.self), msgType: r.u8(), detail: r.u8())
}

public func decodeErrorMessage(_ frame: Frame) throws -> ErrorMessage {
    try requireType(frame, MSGError)
    return try decodeErrorMessage(frame.payload)
}

public func encodeErrorFrame(_ msg: ErrorMessage) throws -> Data {
    try Frame(msgType: MSGError, payload: msg.payload()).encoded()
}

// MARK: TIME_ANCHOR

public struct TimeAnchorRequest: Equatable {
    public let utcMs: UInt64
    public init(utcMs: UInt64) { self.utcMs = utcMs }

    public func payload() throws -> Data {
        var w = Writer()
        w.le(utcMs)
        return w.data
    }
}

public struct TimeAnchorReply: Equatable {
    public let bootId: UInt32
    public let uptimeMs: UInt64
    public init(bootId: UInt32, uptimeMs: UInt64) {
        self.bootId = bootId
        self.uptimeMs = uptimeMs
    }

    public func payload() throws -> Data {
        var w = Writer()
        w.le(bootId)
        w.le(uptimeMs)
        return w.data
    }
}

public func decodeTimeAnchorRequest(_ payload: Data) throws -> TimeAnchorRequest {
    var r = try Reader(payload, expecting: CasebackTimeAnchorRequestLen)
    return TimeAnchorRequest(utcMs: r.le(UInt64.self))
}

public func decodeTimeAnchorRequest(_ frame: Frame) throws -> TimeAnchorRequest {
    try requireType(frame, MSGTimeAnchor)
    return try decodeTimeAnchorRequest(frame.payload)
}

public func decodeTimeAnchorReply(_ payload: Data) throws -> TimeAnchorReply {
    var r = try Reader(payload, expecting: CasebackTimeAnchorReplyLen)
    return TimeAnchorReply(bootId: r.le(UInt32.self), uptimeMs: r.le(UInt64.self))
}

public func decodeTimeAnchorReply(_ frame: Frame) throws -> TimeAnchorReply {
    try requireType(frame, MSGTimeAnchor)
    return try decodeTimeAnchorReply(frame.payload)
}

public func encodeTimeAnchorRequestFrame(_ req: TimeAnchorRequest) throws -> Data {
    try Frame(msgType: MSGTimeAnchor, payload: req.payload()).encoded()
}

public func encodeTimeAnchorReplyFrame(_ rep: TimeAnchorReply) throws -> Data {
    try Frame(msgType: MSGTimeAnchor, payload: rep.payload()).encoded()
}

// MARK: CONFIG_SET / CONFIG_STATE

public struct Config: Equatable {
    public var mode: UInt8
    public var payloadFormat: UInt8
    /// night, day, workout, raw
    public var ppgRateHz: [UInt16]
    public var burstPeriodS: UInt16
    public var burstLenS: UInt16
    public var ledMask: UInt8
    public var ledGreenMa: UInt8
    public var ledRedMa: UInt8
    public var ledIrMa: UInt8
    public var wearPpgDc: UInt32
    public var wearMotionThr: UInt16
    public var wearProbePeriodMs: UInt16

    public init(
        mode: UInt8, payloadFormat: UInt8, ppgRateHz: [UInt16], burstPeriodS: UInt16,
        burstLenS: UInt16, ledMask: UInt8, ledGreenMa: UInt8, ledRedMa: UInt8, ledIrMa: UInt8,
        wearPpgDc: UInt32, wearMotionThr: UInt16, wearProbePeriodMs: UInt16
    ) {
        self.mode = mode
        self.payloadFormat = payloadFormat
        self.ppgRateHz = ppgRateHz
        self.burstPeriodS = burstPeriodS
        self.burstLenS = burstLenS
        self.ledMask = ledMask
        self.ledGreenMa = ledGreenMa
        self.ledRedMa = ledRedMa
        self.ledIrMa = ledIrMa
        self.wearPpgDc = wearPpgDc
        self.wearMotionThr = wearMotionThr
        self.wearProbePeriodMs = wearProbePeriodMs
    }

    /// Throws `MessageError.invalidField` with the payload offset of the first bad field.
    public func validate() throws {
        guard mode <= ModeRaw else { throw MessageError.invalidField(offset: 0) }
        guard payloadFormat <= PayloadFormatStreamRaw else { throw MessageError.invalidField(offset: 1) }
        guard ppgRateHz.count == 4 else { throw MessageError.invalidField(offset: 2) }
        for (i, rate) in ppgRateHz.enumerated() where rate > MaxPPGRateHz {
            throw MessageError.invalidField(offset: UInt8(2 + 2 * i))
        }
        guard burstLenS <= burstPeriodS else { throw MessageError.invalidField(offset: 12) }
        guard ledMask <= 0x07 else { throw MessageError.invalidField(offset: 14) }
    }

    public func payload() throws -> Data {
        try validate()
        var w = Writer()
        w.u8(mode)
        w.u8(payloadFormat)
        ppgRateHz.forEach { w.le($0) }
        w.le(burstPeriodS)
        w.le(burstLenS)
        w.u8(ledMask)
        w.u8(ledGreenMa)
        w.u8(ledRedMa)
        w.u8(ledIrMa)
        w.le(wearPpgDc)
        w.le(wearMotionThr)
        w.le(wearProbePeriodMs)
        return w.data
    }
}

public func decodeConfig(_ payload: Data) throws -> Config {
    var r = try Reader(payload, expecting: CasebackConfigPayloadLen)
    let cfg = Config(
        mode: r.u8(),
        payloadFormat: r.u8(),
        ppgRateHz: (0..<4).map { _ in r.le(UInt16.self) },
        burstPeriodS: r.le(UInt16.self),
        burstLenS: r.le(UInt16.self),
        ledMask: r.u8(),
        ledGreenMa: r.u8(),
        ledRedMa: r.u8(),
        ledIrMa: r.u8(),
        wearPpgDc: r.le(UInt32.self),
        wearMotionThr: r.le(UInt16.self),
        wearProbePeriodMs: r.le(UInt16.self)
    )
    try cfg.validate()
    return cfg
}

public func decodeConfigSetFrame(_ frame: Frame) throws -> Config {
    try requireType(frame, MSGConfigSet)
    return try decodeConfig(frame.payload)
}

public func decodeConfigStateFrame(_ frame: Frame) throws -> Config {
    try requireType(frame, MSGConfigState)
    return try decodeConfig(frame.payload)
}

public func encodeConfigSetFrame(_ cfg: Config) throws -> Data {
    try Frame(msgType: MSGConfigSet, payload: cfg.payload()).encoded()
}

public func encodeConfigStateFrame(_ cfg: Config) throws -> Data {
    try Frame(msgType: MSGConfigState, payload: cfg.payload()).encoded()
}

/// CONFIG_STATE with an empty payload from the phone asks for the current state.
public func encodeConfigQueryFrame() throws -> Data {
    try Frame(msgType: MSGConfigState, payload: Data()).encoded()
}

// MARK: BATTERY

public struct Battery: Equatable {
    public var voltageMv: UInt16
    public var charging: UInt8
    public var percent: UInt8
    /// night, day, workout, raw
    public var avgCurrentUa: [UInt16]

    public init(voltageMv: UInt16, charging: UInt8, percent: UInt8, avgCurrentUa: [UInt16]) {
        self.voltageMv = voltageMv
        self.charging = charging
        self.percent = percent
        self.avgCurrentUa = avgCurrentUa
    }

    public func validate() throws {
        guard charging <= ChargingFault || charging == ChargingUnknown else {
            throw MessageError.invalidField(offset: 2)
        }
        guard percent <= 100 || percent == PercentUnknown else { throw MessageError.invalidField(offset: 3) }
        guard avgCurrentUa.count == 4 else { throw MessageError.invalidField(offset: 4) }
    }

    public func payload() throws -> Data {
        try validate()
        var w = Writer()
        w.le(voltageMv)
        w.u8(charging)
        w.u8(percent)
        avgCurrentUa.forEach { w.le($0) }
        return w.data
    }
}

public func decodeBattery(_ payload: Data) throws -> Battery {
    var r = try Reader(payload, expecting: CasebackBatteryPayloadLen)
    let bat = Battery(
        voltageMv: r.le(UInt16.self),
        charging: r.u8(),
        percent: r.u8(),
        avgCurrentUa: (0..<4).map { _ in r.le(UInt16.self) }
    )
    try bat.validate()
    return bat
}

public func decodeBatteryFrame(_ frame: Frame) throws -> Battery {
    try requireType(frame, MSGBattery)
    return try decodeBattery(frame.payload)
}

public func encodeBatteryFrame(_ bat: Battery) throws -> Data {
    try Frame(msgType: MSGBattery, payload: bat.payload()).encoded()
}

public func encodeBatteryQueryFrame() throws -> Data {
    try Frame(msgType: MSGBattery, payload: Data()).encoded()
}
