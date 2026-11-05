import Foundation
import SwiftUI

enum PilotSample {
  case green(UInt32)
  case acceleration(Int16, Int16, Int16)

  var csv: String {
    switch self {
    case let .green(v): return "\(v),,,"
    case let .acceleration(x, y, z): return ",\(x),\(y),\(z)"
    }
  }

  func component(_ axis: Int) -> Double {
    switch self {
    case let .green(v): return Double(v)
    case let .acceleration(x, y, z):
      switch axis {
      case 0: return Double(x) / 8192
      case 1: return Double(y) / 8192
      default: return Double(z) / 8192
      }
    }
  }
}

/// The display buffer is separate from the durable archive and accepts live frames only.
final class PilotLiveSignals {
  static let seconds: Double = 8
  struct Point {
    let uptime: Double
    let sample: PilotSample
    let startsSegment: Bool
  }
  private struct Trace {
    var points: [Point] = []
    var received: TimeInterval = 0
    var needsBreak = false
  }
  struct Source: Equatable {
    let unit: String, session: String, boot: UInt32
  }
  struct Window {
    let end: Double
    let points: ArraySlice<Point>
    let stale: Bool
  }
  private var estimating = false
  private var pulseAfter = -Double.infinity
  private var pulseReason = PilotPulseResult.interrupted
  private var pulseChecked = -Double.infinity
  private var lastPulse = PilotPulseResult.collecting
  private var source: Source?
  private var traces: [UInt8: Trace] = [:]

  func bind(_ newSource: Source?) {
    guard newSource != source else { return }
    source = newSource
    endPulse()
    traces.removeAll()
  }
  func stop(_ id: UInt8) { traces.removeValue(forKey: id); endPulse() }

  func beginPulse() {
    guard source != nil else { return }
    estimating = true
    pulseAfter = -Double.infinity
    pulseChecked = -Double.infinity
    lastPulse = .collecting
    traces.removeAll()
  }
  func endPulse() { estimating = false; lastPulse = .collecting; pulseChecked = -Double.infinity }

  func restPulse(at now: TimeInterval) -> PilotPulseResult {
    guard estimating, let g = traces[1], let a = traces[2],
          let lastG = g.points.last, let lastA = a.points.last else { return .collecting }
    guard now - g.received < 0.6, now - a.received < 0.6,
          abs(lastG.uptime - lastA.uptime) <= 0.2 else { return .stale }
    let end = min(lastG.uptime, lastA.uptime), start = end - PilotRestPulse.seconds
    guard start >= pulseAfter else { return pulseReason }
    guard let firstG = g.points.first, let firstA = a.points.first,
          firstG.uptime <= start, firstA.uptime <= start else { return .collecting }
    if now - pulseChecked >= 1 {
      lastPulse = PilotRestPulse.estimate(green: g.points, acceleration: a.points, end: end)
      pulseChecked = now
    }
    return lastPulse
  }

  func receive(_ batch: PilotBatch, from sender: Source, missing: Bool, at now: TimeInterval) {
    guard source == sender, batch.boot == sender.boot else { return }
    if estimating && (missing || batch.gap || batch.rate != 500) {
      pulseReason = .interrupted
      pulseAfter = max(pulseAfter, Double(batch.uptime + batch.offsetMs(batch.values.count - 1)) / 1000)
      pulseChecked = -Double.infinity
    }
    if missing {
      // The shared sequence cannot identify which live channel lost a notification.
      for id: UInt8 in [1, 2] { traces[id]?.needsBreak = true }
    }
    var trace = traces.removeValue(forKey: batch.id) ?? Trace()
    let period = 10 / Double(batch.rate)
    for (i, sample) in batch.values.enumerated() {
      let t = Double(batch.uptime + batch.offsetMs(i)) / 1000
      // Late packets are kept by the archive; they cannot move a live line backwards.
      if let last = trace.points.last, t <= last.uptime {
        trace.needsBreak = true
        if estimating { pulseAfter = max(pulseAfter, last.uptime); pulseReason = .interrupted; pulseChecked = -Double.infinity }
        continue
      }
      let delayed = trace.points.last.map { t - $0.uptime > 2.5 * period } ?? true
      if estimating, trace.points.last != nil, delayed || trace.needsBreak {
        pulseAfter = max(pulseAfter, t)
        pulseReason = .interrupted
        pulseChecked = -Double.infinity
      }
      if estimating, case let .green(code) = sample, code <= 2 || code >= 524285 {
        pulseAfter = max(pulseAfter, t)
        pulseReason = .poorSignal
        pulseChecked = -Double.infinity
      }
      trace.points.append(Point(uptime: t, sample: sample,
                                startsSegment: trace.needsBreak || (i == 0 && batch.gap) || delayed))
      trace.needsBreak = false
      trace.received = now
    }
    if let last = trace.points.last {
      let cutoff = last.uptime - (estimating ? PilotRestPulse.seconds + 0.5 : Self.seconds)
      if let first = trace.points.firstIndex(where: { $0.uptime >= cutoff }), first > 0 {
        trace.points.removeFirst(first)
      }
      if trace.points.count > 3200 { trace.points.removeFirst(trace.points.count - 3200) }
    }
    traces[batch.id] = trace
  }

  func window(_ id: UInt8, at now: TimeInterval) -> Window? {
    guard let trace = traces[id], let last = trace.points.last else { return nil }
    let age = max(0, now - trace.received)
    guard age < Self.seconds else { return nil }
    let end = last.uptime + age
    return Window(end: end, points: trace.points.drop(while: { $0.uptime < end - Self.seconds }),
                  stale: age >= 1)
  }
}

struct PilotSignalChart: View {
  let signals: PilotLiveSignals
  let id: UInt8
  private var green: Bool { id == 1 }
  var body: some View {
    TimelineView(.periodic(from: .now, by: 0.12)) { _ in
      if let w = signals.window(id, at: ProcessInfo.processInfo.systemUptime),
        let latest = w.points.last
      {
        let range = verticalRange(w.points)
        VStack(alignment: .leading, spacing: 4) {
          if green {
            HStack {
              Text("\(Int(latest.sample.component(0))) cuentas ADC")
              if w.points.contains(where: {
                $0.sample.component(0) <= 0 || $0.sample.component(0) >= 524287
              }) {
                Text("Límite del ADC").foregroundStyle(.orange)
              }
            }
          } else {
            HStack(spacing: 12) {
              ForEach(0..<3, id: \.self) { a in
                Text("\(["X", "Y", "Z"][a]) \(latest.sample.component(a), specifier: "%.2f") g")
                  .foregroundStyle(color(a))
              }
            }
          }
          HStack(spacing: 6) {
            VStack(alignment: .trailing) {
              Text(axisLabel(range.upperBound))
              Spacer()
              Text(axisLabel(range.lowerBound))
            }.font(.caption2).foregroundStyle(.secondary)
            Canvas { ctx, size in
              var grid = Path()
              for t in [0.0, 0.5, 1.0] {
                grid.move(to: CGPoint(x: 0, y: size.height * t))
                grid.addLine(to: CGPoint(x: size.width, y: size.height * t))
              }
              ctx.stroke(grid, with: .color(.secondary.opacity(0.25)), lineWidth: 0.5)
              for axis in 0..<(green ? 1 : 3) {
                var line = Path()
                for (i, p) in w.points.enumerated() {
                  let x = size.width * (1 + (p.uptime - w.end) / PilotLiveSignals.seconds)
                  let y = size.height * (range.upperBound - p.sample.component(axis)) /
                    (range.upperBound - range.lowerBound)
                  let at = CGPoint(x: x, y: y)
                  if i == 0 || p.startsSegment {
                    line.move(to: at)
                    ctx.fill(Path(ellipseIn: CGRect(x: x - 1, y: y - 1, width: 2, height: 2)),
                             with: .color(color(axis)))
                  } else { line.addLine(to: at) }
                }
                ctx.stroke(line, with: .color(color(axis)), lineWidth: 1.5)
              }
            }.clipped()
          }.frame(height: 76)
          HStack {
            Text("−8 s")
            Spacer()
            Text(w.stale ? "Sin muestras recientes" : "Ahora")
          }.font(.caption2).foregroundStyle(.secondary)
        }
        .font(.caption.monospacedDigit())
        .accessibilityElement(children: .combine)
      } else {
        Text("Esperando muestras del disco").font(.caption).foregroundStyle(.secondary)
      }
    }
  }

  private func color(_ axis: Int) -> Color {
    if green { return .green }
    return [.cyan, .orange, .purple][axis]
  }
  private func axisLabel(_ v: Double) -> String {
    green ? String(Int(v)) : String(format: "%+.0f g", v)
  }
  private func verticalRange(_ points: ArraySlice<PilotLiveSignals.Point>) -> ClosedRange<Double> {
    guard green else { return -4...4 }
    let values = points.map { $0.sample.component(0) }
    let low = values.min() ?? 0
    let high = values.max() ?? low
    let margin = max(1, ((high - low) * 0.06).rounded(.up))
    return max(0, low - margin)...(high + margin)
  }
}
