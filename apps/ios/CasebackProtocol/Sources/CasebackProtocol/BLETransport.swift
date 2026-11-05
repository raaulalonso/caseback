import Foundation

// Transport seam for the app (M2 prep). The package stays pure: no CoreBluetooth import, so it builds
// and tests on macOS. The app target supplies a CoreBluetooth-backed implementation; tests and the
// iOS Simulator (which cannot run CoreBluetooth) use `SimulatedPeripheral`.
//
// Deployment targets: this package stays at iOS 16 / macOS 13. The app target needs iOS 17 because
// SwiftData (decision D17) requires it.

public enum TransportError: Error, Equatable {
    case notConnected
    case alreadyConnected
    /// The frame does not fit in one ATT value (`ATT_MTU - 3`).
    case frameTooLarge(Int)
}

/// The GATT transport of spec/gatt.md: INFO (read), CONTROL (write without response, phone to
/// device) and DATA (notify, device to phone). One ATT value is exactly one frame.
public protocol BLETransport: AnyObject {
    var isConnected: Bool { get }
    func connect() async throws
    func disconnect() async
    /// Reads the INFO characteristic: one INFO_RESPONSE frame.
    func readInfo() async throws -> Data
    /// Writes one frame to CONTROL.
    func writeControl(_ frame: Data) async throws
    /// DATA notifications of the current connection; the stream finishes on disconnect. Call after
    /// `connect()`; before that it returns a stream that is already finished.
    func notifications() -> AsyncStream<Data>
}
