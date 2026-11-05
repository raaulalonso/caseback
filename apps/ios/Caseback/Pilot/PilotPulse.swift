import Foundation
import SwiftUI

enum PilotPulseResult: Equatable {
  case collecting, stale, interrupted, moving, poorSignal, ambiguous, value(Int)

  var text: String {
    switch self {
    case .collecting: return "Recogiendo 10 s de señal"
    case .stale: return "Sin datos recientes de ambos sensores"
    case .interrupted: return "Esperando un tramo continuo"
    case .moving: return "Mantén la muñeca quieta"
    case .poorSignal: return "Señal óptica insuficiente"
    case .ambiguous: return "Sin un ritmo claro"
    case let .value(bpm): return "\(bpm) lpm"
    }
  }
}

enum PilotRestPulse {
  static let seconds = 10.0
  static let count = 501 // ten seconds at the disc's nominal 50 Hz, including both ends
  typealias Point = PilotLiveSignals.Point

  // scipy.signal.butter(3, [0.5, 8], btype="bandpass", fs=50, output="sos").
  // Same conditioning and peak/IBI criteria as the design notes
  private static let sos = [
    [0.049532996357253174, 0.09906599271450635, 0.049532996357253174, -0.8016302031785859, 0.44959933277646735],
    [1.0, 0.0, -1.0, -1.2799166268639646, 0.3249196962329064],
    [1.0, -2.0, 1.0, -1.9390043038360352, 0.9430300670802169]
  ]

  static func estimate(green: [Point], acceleration: [Point], end: Double) -> PilotPulseResult {
    let observed = green.lazy.filter { $0.uptime >= end - seconds && $0.uptime <= end }
    guard !observed.contains(where: { $0.sample.component(0) <= 2 || $0.sample.component(0) >= 524285 })
    else { return .poorSignal }
    guard let g = resample(green, end: end, axes: 1),
          let xyz = resample(acceleration, end: end, axes: 3) else { return .interrupted }
    let raw = g[0]
    let axes = xyz.map { axis in
      let mean = axis.reduce(0, +) / Double(axis.count)
      return axis.map { $0 - mean }
    }
    let motion = raw.indices.map { i in axes.reduce(0.0) { $0 + $1[i] * $1[i] } }
    guard (motion.max() ?? 1) < 0.15 * 0.15,
          motion.reduce(0, +) / Double(count) < 0.035 * 0.035 else { return .moving }

    let filtered = bandpass(raw)
    let ranked = Array(filtered[25..<(count - 25)]).sorted()
    let spread = ranked[ranked.count * 95 / 100] - ranked[ranked.count * 5 / 100]
    // Conservative bench gates. The unit's real skin/contact transfer is measured on U01.
    guard spread >= max(20, median(raw) * 0.0005) else { return .poorSignal }
    for axis in axes {
      let rms = sqrt(axis.reduce(0) { $0 + $1 * $1 } / Double(axis.count))
      if rms > 0.005 && stride(from: -12, through: 12, by: 3).contains(where: {
        abs(correlation(filtered, axis, lag: $0)) > 0.55
      }) { return .moving }
    }
    let beats = peakTimes(filtered, prominence: 0.3 * spread)
    let intervals = zip(beats.dropFirst(), beats).map { $0.0 - $0.1 }
    guard intervals.count >= 4 else { return .ambiguous }
    let m = median(intervals)
    let clean = intervals.enumerated().compactMap { i, t -> Double? in
      let neighbors = Array(intervals[max(0, i - 2)...min(i + 2, intervals.count - 1)])
      let local = median(neighbors)
      return (0.3...2.0).contains(t) && abs(t - local) <= 0.25 * local ? t : nil
    }
    guard clean.count >= 4, clean.count * 5 >= intervals.count * 4,
          clean.filter({ abs($0 - m) <= 0.12 * m }).count * 5 >= clean.count * 4
    else { return .ambiguous }
    let period = median(clean)
    let lag = Int((period * 50).rounded())
    guard (15...100).contains(lag) else { return .ambiguous }
    let rhythm = correlation(filtered, filtered, lag: lag)
    guard rhythm >= 0.72 else { return .ambiguous }
    // Alternating peaks and competing periods can produce a plausible but wrong median.
    if correlation(filtered, filtered, lag: 2 * lag) > rhythm + 0.12
      || correlation(filtered, filtered, lag: max(1, lag / 2)) >= rhythm - 0.08 {
      return .ambiguous
    }
    for other in 15...100 where Double(abs(other - lag)) > 0.18 * Double(lag) {
      let multiple = Double(other) / Double(lag)
      if abs(multiple - multiple.rounded()) < 0.17 { continue }
      if correlation(filtered, filtered, lag: other) >= max(0.72, rhythm - 0.08) {
        return .ambiguous
      }
    }
    return .value(Int((60 / period).rounded()))
  }

  private static func resample(_ points: [Point], end: Double, axes: Int) -> [[Double]]? {
    let start = end - seconds
    guard points.count >= 2, points[0].uptime <= start + 0.00001,
          points.last!.uptime >= end - 0.00001 else { return nil }
    var out = Array(repeating: [Double](), count: axes), j = 0
    for i in 0..<count {
      let time = start + Double(i) / 50
      while j + 2 < points.count, points[j + 1].uptime < time - 0.00001 { j += 1 }
      let p = points[j], q = points[j + 1], span = q.uptime - p.uptime
      guard span > 0, span <= 0.045, !q.startsSegment else { return nil }
      let f = min(1, max(0, (time - p.uptime) / span))
      for a in 0..<axes {
        let y = p.sample.component(a)
        out[a].append(y + f * (q.sample.component(a) - y))
      }
    }
    return out
  }

  private static func median(_ a: [Double]) -> Double {
    let s = a.sorted()
    return (s[(s.count - 1) / 2] + s[s.count / 2]) / 2
  }

  private static func bandpass(_ values: [Double]) -> [Double] {
    let pad = 21, first = values[0], last = values[values.count - 1]
    let left = (1...pad).reversed().map { 2 * first - values[$0] }
    let right = (1...pad).map { 2 * last - values[values.count - 1 - $0] }
    func filter(_ input: [Double]) -> [Double] {
      var series = input
      for c in sos {
        let x0 = series[0], y0 = x0 * (c[0] + c[1] + c[2]) / (1 + c[3] + c[4])
        var z1 = y0 - c[0] * x0, z2 = c[2] * x0 - c[4] * y0
        for i in series.indices {
          let x = series[i], y = c[0] * x + z1
          z1 = c[1] * x - c[3] * y + z2
          z2 = c[2] * x - c[4] * y
          series[i] = y
        }
      }
      return series
    }
    let forward = filter(left + values + right)
    let back = Array(filter(Array(forward.reversed())).reversed())
    return Array(back[pad..<(pad + values.count)])
  }

  private static func peakTimes(_ x: [Double], prominence: Double) -> [Double] {
    var candidates = [Int]()
    for i in 25..<(x.count - 25) where x[i] > x[i - 1] && x[i] >= x[i + 1] {
      var lowL = x[i], lowR = x[i], j = i - 1
      while j >= 0 && x[j] <= x[i] { lowL = min(lowL, x[j]); j -= 1 }
      j = i + 1
      while j < x.count && x[j] <= x[i] { lowR = min(lowR, x[j]); j += 1 }
      if x[i] - max(lowL, lowR) >= prominence { candidates.append(i) }
    }
    var kept = [Int]()
    for i in candidates.sorted(by: { x[$0] > x[$1] }) {
      if kept.allSatisfy({ abs($0 - i) >= 15 }) { kept.append(i) }
    }
    return kept.sorted().map { i in
      let d = x[i - 1] - 2 * x[i] + x[i + 1]
      let correction = d < 0 ? 0.5 * (x[i - 1] - x[i + 1]) / d : 0
      return (Double(i) + min(1, max(-1, correction))) / 50
    }
  }

  private static func correlation(_ a: [Double], _ b: [Double], lag: Int) -> Double {
    // Drop the half-second filter edges from both series.
    let lo = max(25, 25 - lag), hi = min(a.count - 25, b.count - 25 - lag)
    guard hi - lo >= 100 else { return 0 }
    var xy = 0.0, xx = 0.0, yy = 0.0, x = 0.0, y = 0.0
    for i in lo..<hi {
      let v = a[i], w = b[i + lag]
      x += v; y += w; xx += v * v; yy += w * w; xy += v * w
    }
    let n = Double(hi - lo)
    let variance = (xx - x*x/n) * (yy - y*y/n)
    return variance > 0 ? (xy - x*y/n) / sqrt(variance) : 0
  }
}

struct PilotPulseView: View {
  let signals: PilotLiveSignals
  @State private var measuring = false
  var body: some View {
    VStack(alignment: .leading, spacing: 7) {
      Text("Pulso estimado en reposo").font(.headline)
      if measuring {
        TimelineView(.periodic(from: .now, by: 0.4)) { _ in
          Text(signals.restPulse(at: ProcessInfo.processInfo.systemUptime).text)
            .font(.body.monospacedDigit()).accessibilityIdentifier("pilot.restPulse")
        }
        Text("Demostración en directo").font(.caption).foregroundStyle(.secondary)
        Button("Terminar estimación") { signals.endPulse(); measuring = false }
      } else {
        Text("Con el disco sobre la piel y la muñeca quieta, inicia una medida de demostración.")
          .font(.footnote).foregroundStyle(.secondary)
        Button("Estimar pulso ahora") { signals.beginPulse(); measuring = true }
      }
    }
    .onDisappear { signals.endPulse(); measuring = false }
  }
}
