import Foundation

/// Manual clock: the simulated device's uptime only moves when the test advances it.
public final class SimClock {
    public private(set) var uptimeMs: UInt64

    public init(uptimeMs: UInt64 = 0) { self.uptimeMs = uptimeMs }

    public func advance(ms: UInt64) { uptimeMs += ms }
}

/// SplitMix64: small, seedable and stable across platforms and Swift versions.
public struct SeededGenerator: RandomNumberGenerator {
    private var state: UInt64

    public init(seed: UInt64) { state = seed }

    public mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }
}

/// Faults applied to device-to-phone notifications; rates are probabilities in 0...1.
public struct FaultPlan: Equatable {
    public var dropRate = 0.0
    public var duplicateRate = 0.0
    /// A reordered frame is held back and delivered after the next one.
    public var reorderRate = 0.0
    public var corruptCRCRate = 0.0
    /// Disconnects after this many delivered notifications.
    public var disconnectAfterNotifications: Int?
    /// Drops phone-to-device writes silently.
    public var dropWriteRate = 0.0

    public init() {}
}

/// In-memory device that speaks the Caseback protocol over the `BLETransport` seam. It answers
/// INFO_REQUEST, TIME_ANCHOR, CONFIG_SET and the CONFIG/BATTERY queries, emits BATTERY on demand
/// and replies ERROR to anything it rejects. Deterministic: the clock is manual and the fault
/// injection draws from a seeded generator. Not thread-safe beyond an internal lock.
public final class SimulatedPeripheral: BLETransport, @unchecked Sendable {
    public let clock: SimClock
    public var bootId: UInt32
    public var info: InfoResponse
    public private(set) var config: Config
    public var battery: Battery
    public var faults = FaultPlan()
    /// ATT MTU; a write longer than `attMTU - 3` is refused like CoreBluetooth would.
    public var attMTU = 185
    /// Last `utc_ms` received in a TIME_ANCHOR request.
    public private(set) var lastAnchorUtcMs: UInt64?
    /// Every frame written to CONTROL, including dropped ones.
    public private(set) var controlLog: [Data] = []

    private let lock = NSLock()
    private var rng: SeededGenerator
    private var continuation: AsyncStream<Data>.Continuation?
    private var stream: AsyncStream<Data>?
    private var connected = false
    private var held: Data?
    private var delivered = 0

    public static let defaultInfo = InfoResponse(
        deviceId: [0x8B, 0x9C, 0xAD, 0xBE, 0xCF, 0xD0, 0xE1, 0xF2],
        hwRev: 0x0100,
        fwRev: 0x0002,
        capabilities: CAPPPGRaw | CAPPPGSummary | CAPIBILog | CAPEncryptedOnly
    )

    public static let defaultConfig = Config(
        mode: ModeNight, payloadFormat: PayloadFormatSummary, ppgRateHz: [25, 32, 100, 100],
        burstPeriodS: 300, burstLenS: 30, ledMask: LEDGreen, ledGreenMa: 20, ledRedMa: 0,
        ledIrMa: 0, wearPpgDc: 20_000, wearMotionThr: 500, wearProbePeriodMs: 1000
    )

    public init(
        seed: UInt64 = 1, clock: SimClock = SimClock(), bootId: UInt32 = 0xC0DE_FACE,
        info: InfoResponse = SimulatedPeripheral.defaultInfo,
        config: Config = SimulatedPeripheral.defaultConfig,
        battery: Battery = Battery(
            voltageMv: 4013, charging: ChargingNotCharging, percent: 87,
            avgCurrentUa: [210, 854, 6699, 15758])
    ) {
        self.rng = SeededGenerator(seed: seed)
        self.clock = clock
        self.bootId = bootId
        self.info = info
        self.config = config
        self.battery = battery
    }

    // MARK: BLETransport

    public var isConnected: Bool { locked { connected } }

    public func connect() async throws {
        try locked {
            guard !connected else { throw TransportError.alreadyConnected }
            let made = AsyncStream<Data>.makeStream()
            stream = made.stream
            continuation = made.continuation
            connected = true
            held = nil
            delivered = 0
        }
    }

    public func disconnect() async {
        locked { disconnectLocked() }
    }

    public func readInfo() async throws -> Data {
        try locked {
            guard connected else { throw TransportError.notConnected }
            return try encodeInfoResponseFrame(info)
        }
    }

    public func writeControl(_ frame: Data) async throws {
        try locked {
            guard connected else { throw TransportError.notConnected }
            guard frame.count <= attMTU - 3 else { throw TransportError.frameTooLarge(frame.count) }
            controlLog.append(frame)
            if chance(faults.dropWriteRate) { return }
            handleLocked(frame)
        }
    }

    public func notifications() -> AsyncStream<Data> {
        locked {
            if let stream { return stream }
            return AsyncStream { $0.finish() }
        }
    }

    // MARK: device-side actions

    /// Pushes an unsolicited BATTERY message, as the device does on a charging-state change.
    public func emitBattery() {
        locked {
            guard connected else { return }
            if let frame = try? encodeBatteryFrame(battery) { emitLocked(frame) }
        }
    }

    /// Delivers a frame that was held back by a reorder fault, if any.
    public func flush() {
        locked {
            if let h = held {
                held = nil
                yieldLocked(h)
            }
        }
    }

    // MARK: internals

    private func locked<T>(_ body: () throws -> T) rethrows -> T {
        lock.lock()
        defer { lock.unlock() }
        return try body()
    }

    private func chance(_ p: Double) -> Bool {
        if p <= 0 { return false }
        if p >= 1 { return true }
        return Double.random(in: 0..<1, using: &rng) < p
    }

    private func disconnectLocked() {
        connected = false
        held = nil
        continuation?.finish()
        continuation = nil
        stream = nil
    }

    private func reply(_ build: () throws -> Data) {
        if let frame = try? build() { emitLocked(frame) }
    }

    private func replyError(_ code: ErrorCode, _ type: UInt8, _ detail: UInt8 = 0) {
        reply { try encodeErrorFrame(ErrorMessage(code, msgType: type, detail: detail)) }
    }

    private func handleLocked(_ data: Data) {
        let frame: Frame
        do {
            frame = try decodeFrame(data)
        } catch let error as FrameError {
            replyError(error.code, 0)
            return
        } catch {
            replyError(.internalError, 0)
            return
        }
        let empty = frame.payload.isEmpty
        switch frame.msgType {
        case MSGInfoRequest:
            guard empty else { return replyError(.badPayloadLength, frame.msgType, 0) }
            reply { try encodeInfoResponseFrame(info) }
        case MSGTimeAnchor:
            do {
                lastAnchorUtcMs = try decodeTimeAnchorRequest(frame).utcMs
            } catch let error as MessageError {
                return replyError(error.code, frame.msgType, error.detail)
            } catch {
                return replyError(.internalError, frame.msgType)
            }
            reply {
                try encodeTimeAnchorReplyFrame(TimeAnchorReply(bootId: bootId, uptimeMs: clock.uptimeMs))
            }
        case MSGConfigSet:
            do {
                config = try decodeConfigSetFrame(frame)
            } catch let error as MessageError {
                return replyError(error.code, frame.msgType, error.detail)
            } catch {
                return replyError(.internalError, frame.msgType)
            }
            reply { try encodeConfigStateFrame(config) }
        case MSGConfigState:
            guard empty else { return replyError(.wrongDirection, frame.msgType) }
            reply { try encodeConfigStateFrame(config) }
        case MSGBattery:
            guard empty else { return replyError(.wrongDirection, frame.msgType) }
            reply { try encodeBatteryFrame(battery) }
        case MSGError, MSGInfoResponse:
            replyError(.wrongDirection, frame.msgType)
        default:
            replyError(.unknownMsgType, frame.msgType)
        }
    }

    /// Applies the fault plan to one outgoing notification.
    private func emitLocked(_ frame: Data) {
        if chance(faults.dropRate) { return }
        var out = frame
        if chance(faults.corruptCRCRate), !out.isEmpty {
            out[out.count - 1] ^= 0xFF
        }
        let copies = chance(faults.duplicateRate) ? 2 : 1
        for _ in 0..<copies {
            if held == nil, chance(faults.reorderRate) {
                held = out
                continue
            }
            yieldLocked(out)
            if let h = held {
                held = nil
                yieldLocked(h)
            }
        }
    }

    private func yieldLocked(_ frame: Data) {
        guard connected else { return }
        continuation?.yield(frame)
        delivered += 1
        if let limit = faults.disconnectAfterNotifications, delivered >= limit {
            disconnectLocked()
        }
    }
}
