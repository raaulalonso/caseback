import Foundation
import CasebackProtocol

/// The first conversation with a disc, over any `BLETransport` (spec/gatt.md and messages.md):
/// connect, read INFO (which makes iOS start bonding when the link is not encrypted yet), send TIME_ANCHOR, read BATTERY.
/// Written against the transport protocol so CoreBluetooth, the simulated peripheral and tests share it.
enum Handshake {
    static func run(
        transport: BLETransport,
        utcNow: () -> UInt64 = { UInt64(Date().timeIntervalSince1970 * 1000) },
        reply timeout: Duration = .seconds(3),
        progress: @escaping (PairingPhase) -> Void = { _ in }
    ) async throws -> PairedDisc {
        progress(.connecting)
        do {
            try await transport.connect()
        } catch {
            throw PairingFailure.link("connect")
        }

        // Subscribe before writing so no reply is missed.
        let frames = FrameInbox()
        await frames.start(transport.notifications())

        progress(.securing)
        progress(.readingInfo)
        let info: InfoResponse
        do {
            let raw = try await transport.readInfo()
            let frame = try decodeFrame(raw)
            info = try decodeInfoResponse(frame)
        } catch let e as FrameError {
            if e.code == .unsupportedVersion { throw PairingFailure.needsNewerApp }
            throw PairingFailure.link("info: \(e.code)")
        } catch {
            throw PairingFailure.link("info")
        }

        progress(.settingClock)
        try await transport.writeControl(try encodeTimeAnchorRequestFrame(TimeAnchorRequest(utcMs: utcNow())))
        let anchorFrame = try await frames.next(MSGTimeAnchor, within: timeout)
        let anchor = try decodeTimeAnchorReply(anchorFrame)

        progress(.readingBattery)
        try await transport.writeControl(try encodeBatteryQueryFrame())
        let batteryFrame = try await frames.next(MSGBattery, within: timeout)
        let battery = try decodeBatteryFrame(batteryFrame)

        let suffix = info.deviceId.suffix(2).map { String(format: "%02X", $0) }.joined()
        return PairedDisc(
            name: "Caseback-\(suffix)", deviceId: info.deviceId, hwRev: info.hwRev, fwRev: info.fwRev,
            capabilities: info.capabilities,
            batteryPercent: battery.percent == 0xFF ? nil : Int(battery.percent),
            charging: battery.charging, bootId: anchor.bootId)
    }
}

/// Collects DATA notifications and hands out the next frame of a given type, ignoring others and any frame that fails
/// to decode (those are counted, and shown in Diagnostics later, 04 section 3).
actor FrameInbox {
    private var frames: [Frame] = []
    private var failure: PairingFailure?
    private var pump: Task<Void, Never>?
    private(set) var dropped = 0

    func start(_ stream: AsyncStream<Data>) {
        pump = Task { [weak self] in
            for await data in stream {
                guard let self else { return }
                await self.ingest(data)
            }
        }
    }

    deinit { pump?.cancel() }

    private func ingest(_ data: Data) {
        guard let frame = try? decodeFrame(data) else { dropped += 1; return }
        frames.append(frame)
    }

    func next(_ type: UInt8, within timeout: Duration) async throws -> Frame {
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: timeout)
        while clock.now < deadline {
            if let i = frames.firstIndex(where: { $0.msgType == type }) { return frames.remove(at: i) }
            if let i = frames.firstIndex(where: { $0.msgType == MSGError }),
                let e = try? decodeErrorMessage(frames[i]), e.msgType == type
            {
                frames.remove(at: i)
                throw PairingFailure.link("error \(e.code)")
            }
            try await Task.sleep(for: .milliseconds(5))
        }
        throw PairingFailure.timedOut("message 0x\(String(type, radix: 16))")
    }
}
