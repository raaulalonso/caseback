import CasebackProtocol
import XCTest

@testable import Caseback

final class PilotBatchTests: XCTestCase {
  func testFactoryCredentialAndArmingRequireExactBytes() {
    XCTAssertEqual(PilotFactory.credential("00112233445566778899aAbBcCdDeEfF"), Data(stride(from: 0, through: 255, by: 17).map(UInt8.init)))
    for invalid in ["", String(repeating: "A", count: 31), String(repeating: "Z", count: 32),
                    String(repeating: "Ｆ", count: 32), String(repeating: "A", count: 32) + " "] {
      XCTAssertNil(PilotFactory.credential(invalid))
    }
    XCTAssertTrue(PilotFactory.armed(Data([1])))
    for other in [nil, Data(), Data([0]), Data([2]), Data([1, 0])] {
      XCTAssertFalse(PilotFactory.armed(other))
    }
  }

  private var header: [UInt8] {
    [0xfe, 0xff, 9, 0, 0, 0, 25, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 0xf4, 1, 2]
  }
  func testCapturedGreenAndAxisEncoding() throws {
    let p = try PilotBatch(
      Frame(msgType: MSGStreamData, payload: Data(header + [0, 0, 1, 255, 255, 7])))
    XCTAssertEqual(p.seq, 65534)
    XCTAssertEqual(p.rate, 500)
    XCTAssertTrue(p.gap)
    XCTAssertEqual(p.rows, ["65536,,,", "524287,,,"])
    var h = header
    h[14] = 2
    h[19] = 1
    let a = try PilotBatch(
      Frame(msgType: MSGStreamData, payload: Data(h + [0, 128, 0, 32, 255, 255])))
    XCTAssertEqual(a.rows, [",-32768,8192,-1"])
  }
  func testRejectsMalformedBatches() {
    let valid = header + [0, 0, 0, 0, 0, 0]
    for i in 0..<valid.count {
      XCTAssertThrowsError(
        try PilotBatch(Frame(msgType: MSGStreamData, payload: Data(valid.prefix(i)))))
    }
    for (i, v) in [(14, 9), (15, 3), (16, 1), (19, 0)] {
      var bad = valid
      bad[i] = UInt8(v)
      XCTAssertThrowsError(try PilotBatch(Frame(msgType: MSGStreamData, payload: Data(bad))))
    }
  }
}

extension PilotBatchTests {
  private func signal(_ id: UInt8 = 1, time: UInt64, gap: Bool = false, boot: UInt32 = 9) throws -> PilotBatch {
    var h = header
    for i in 0..<4 { h[2 + i] = UInt8(truncatingIfNeeded: boot >> (8 * i)) }
    for i in 0..<8 { h[6 + i] = UInt8(truncatingIfNeeded: time >> (8 * i)) }
    h[14] = id
    h[16] = gap ? 2 : 0
    h[19] = 1
    let sample: [UInt8] = id == 1 ? [0x45, 0x23, 1] : [0, 224, 0, 0, 0, 32]
    return try PilotBatch(Frame(msgType: MSGStreamData, payload: Data(h + sample)))
  }

  func testLivePlotOnlyUsesCurrentDeviceBootAndConnection() throws {
    let store = PilotLiveSignals()
    let source = PilotLiveSignals.Source(unit: "U1", session: "first", boot: 9)
    let next = PilotLiveSignals.Source(unit: "U2", session: "second", boot: 9)
    let reconnect = PilotLiveSignals.Source(unit: "U1", session: "third", boot: 9)
    let b = try signal(time: 100)
    store.bind(source)
    store.receive(b, from: source, missing: false, at: 1)
    XCTAssertEqual(store.window(1, at: 1)?.points.last?.sample.component(0), 74565)
    store.bind(source)  // a refreshed clock anchor preserves the current trace
    XCTAssertEqual(store.window(1, at: 1)?.points.count, 1)
    store.bind(nil)
    store.receive(b, from: source, missing: false, at: 1.1)
    XCTAssertNil(store.window(1, at: 1.1))
    store.bind(next)
    store.receive(b, from: source, missing: false, at: 2)
    store.receive(try signal(time: 140, boot: 10), from: next, missing: false, at: 2)
    XCTAssertNil(store.window(1, at: 2))
    store.bind(reconnect)
    store.receive(b, from: source, missing: false, at: 3)
    XCTAssertNil(store.window(1, at: 3))
    store.receive(b, from: reconnect, missing: false, at: 3)
    XCTAssertEqual(store.window(1, at: 3)?.points.count, 1)
    store.stop(1)
    XCTAssertNil(store.window(1, at: 3))
  }

  func testLivePlotBreaksLinesAcrossLostFramesAndExpiresOnSilence() throws {
    let store = PilotLiveSignals()
    let source = PilotLiveSignals.Source(unit: "U1", session: "first", boot: 9)
    store.bind(source)
    for id: UInt8 in [1, 2] {
      store.receive(try signal(id, time: 1000), from: source, missing: false, at: 10)
      store.receive(try signal(id, time: 1020), from: source, missing: false, at: 10.02)
    }
    store.receive(try signal(time: 1040), from: source, missing: true, at: 10.04)
    store.receive(try signal(2, time: 1040), from: source, missing: false, at: 10.04)
    for id: UInt8 in [1, 2] {
      XCTAssertEqual(store.window(id, at: 10.04)?.points.map(\.startsSegment), [true, false, true])
    }
    let motion = try XCTUnwrap(store.window(2, at: 10.04)?.points.last?.sample)
    XCTAssertEqual(motion.component(0), -1)
    XCTAssertEqual(motion.component(2), 1)
    store.receive(try signal(time: 1060, gap: true), from: source, missing: false, at: 10.06)
    store.receive(try signal(time: 1260), from: source, missing: false, at: 10.26)
    XCTAssertEqual(store.window(1, at: 10.26)?.points.map(\.startsSegment),
                   [true, false, true, true, true])
    XCTAssertEqual(store.window(1, at: 11.3)?.stale, true)
    XCTAssertNil(store.window(1, at: 18.27))
    XCTAssertNil(store.window(2, at: 18.27))
  }
}
