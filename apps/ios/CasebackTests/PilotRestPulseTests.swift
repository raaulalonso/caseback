import CasebackProtocol
import XCTest
@testable import Caseback

final class PilotRestPulseTests: XCTestCase {
  typealias Point = PilotLiveSignals.Point
  private func wave(_ t: Double, _ bpm: Double) -> Double {
    let p = t * 2 * .pi * bpm / 60
    return sin(p) + 0.18 * sin(2 * p + 0.4)
  }
  private func make(optical: (Double) -> Double,
                    motion: (Double) -> Double = { _ in 0 },
                    jitter: Bool = false) -> ([Point], [Point]) {
    var green = [Point](), acc = [Point]()
    for i in 0...510 {
      let t = Double(i) * 0.02 + (jitter ? 0.003 * sin(Double(i)) : 0)
      let v = UInt32(min(524287, max(0, optical(t))).rounded())
      green.append(Point(uptime: t, sample: .green(v), startsSegment: i == 0))
      acc.append(Point(uptime: t, sample: .acceleration(Int16((8192*motion(t)).rounded()), 0, 8192),
                       startsSegment: i == 0))
    }
    return (green, acc)
  }
  private func estimate(_ p: ([Point], [Point])) -> PilotPulseResult {
    PilotRestPulse.estimate(green: p.0, acceleration: p.1, end: 10.1)
  }
  func testKnownRestingCadencesFromGreenCountsWithJitterAndBaselineDrift() {
    for bpm in [54.0, 72, 108] {
      let p = make(optical: { 110000 + 40*$0 + 1100*self.wave($0,bpm) }, jitter: true)
      guard case let .value(v) = estimate(p) else { XCTFail("missing synthetic cadence \(bpm)"); continue }
      XCTAssertEqual(Double(v), bpm, accuracy: 1)
    }
  }
  func testRejectsFlatWeakClippedAndAmbiguousRhythms() {
    XCTAssertEqual(estimate(make(optical: { _ in 110000 })), .poorSignal)
    XCTAssertEqual(estimate(make(optical: { 110000 + self.wave($0,72) })), .poorSignal)
    var clipped = make(optical: { 110000 + 700*self.wave($0,72) }, jitter: true)
    clipped.0[245] = Point(uptime: clipped.0[245].uptime, sample: .green(524287), startsSegment: false)
    XCTAssertEqual(estimate(clipped), .poorSignal)
    let harmonic = make(optical: { t in
      let f = 2 * Double.pi * 1.2 * t
      return 110000 + 450 * sin(f) + 1100 * sin(2*f)
    })
    XCTAssertEqual(estimate(harmonic), .ambiguous)
    var seed: UInt64 = 31
    let noise = make(optical: { _ in
      seed = seed &* 6364136223846793005 &+ 1
      return 100000 + Double((seed >> 32) % 3500)
    })
    XCTAssertEqual(estimate(noise), .ambiguous)
    let competing = make(optical: { 110000 + 800*self.wave($0,66) + 850*self.wave($0,95) })
    XCTAssertEqual(estimate(competing), .ambiguous)
  }
  func testRejectsLargeMotionPeriodicSmallMotionAndTimingInterruptions() {
    let optical: (Double) -> Double = { 110000 + 1000*self.wave($0,72) }
    XCTAssertEqual(estimate(make(optical: optical, motion: { 0.1*sin($0*9) })), .moving)
    XCTAssertEqual(estimate(make(optical: optical, motion: { 0.015*self.wave($0,72) })), .moving)
    var gap = make(optical: optical)
    gap.1.removeSubrange(200..<208)
    XCTAssertEqual(estimate(gap), .interrupted)
    var opticalGap = make(optical: optical)
    let p = opticalGap.0[150]
    opticalGap.0[150] = Point(uptime: p.uptime, sample: p.sample, startsSegment: true)
    XCTAssertEqual(estimate(opticalGap), .interrupted)
  }

  private func frame(_ id: UInt8, first: Int, number: Int = 20, gap: Bool = false,
                     rate: Int = 500) throws -> PilotBatch {
    var data = [UInt8]()
    func put(_ value: Int, _ n: Int) {
      for i in 0..<n { data.append(UInt8(truncatingIfNeeded: value >> (8*i))) }
    }
    put(first,2); put(9,4); put(first*20,8); data.append(contentsOf: [id,1,gap ? 2 : 0])
    put(rate,2); put(number,1)
    for i in first..<(first+number) {
      if id == 1 { put(Int(110000+1000*wave(Double(i)/50,72)),3) }
      else { put(0,2); put(0,2); put(8192,2) }
    }
    return try PilotBatch(Frame(msgType: MSGStreamData, payload: Data(data)))
  }
  func testLiveModeRequiresExplicitFreshPairedStreamsAndInvalidatesOldResult() throws {
    let store = PilotLiveSignals()
    let s = PilotLiveSignals.Source(unit: "U01", session: "link1", boot: 9)
    store.bind(s)
    func feed(_ first: Int, id: UInt8, gap: Bool = false, rate: Int = 500) throws {
      try store.receive(frame(id, first: first, gap: gap, rate: rate), from: s, missing: false,
                        at: Double(first+19)/50)
    }
    for i in stride(from: 0, to: 520, by: 20) { try feed(i,id:1); try feed(i,id:2) }
    XCTAssertEqual(store.restPulse(at: 10.39), .collecting)
    store.beginPulse()
    XCTAssertEqual(store.restPulse(at: 10.39), .collecting)
    for i in stride(from: 520, to: 1040, by: 20) { try feed(i,id:1); try feed(i,id:2) }
    XCTAssertEqual(store.restPulse(at: 20.78), .value(72))
    XCTAssertEqual(store.restPulse(at: 21.5), .stale)
    try feed(1040,id:1,gap:true)
    try feed(1040,id:2)
    XCTAssertEqual(store.restPulse(at: 21.18), .interrupted)
    store.stop(1)
    XCTAssertEqual(store.restPulse(at: 21.18), .collecting)
    store.bind(.init(unit: "U02", session: "link2", boot: 4))
    store.beginPulse()
    try feed(1060,id:1); try feed(1060,id:2)
    XCTAssertEqual(store.restPulse(at: 21.58), .collecting)
  }
}
