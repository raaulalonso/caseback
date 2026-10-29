import SwiftUI

// Line charts for Today. Lines are 3.5 pt with round caps and a smooth curve, a soft flat area sits under them, bars are
// capsules. Only the charts move: they draw once when `play` turns true. Under Reduce Motion they are simply there.

private let stroke: CGFloat = 3.5

enum ChartMotion {
    static func draw(_ delay: Double) -> Animation { .timingCurve(0.2, 0, 0, 1, duration: 1.0).delay(delay) }
    static func grow(_ delay: Double) -> Animation { .timingCurve(0.2, 0, 0, 1, duration: 0.8).delay(delay) }
}

/// Maps a series into a rectangle.
struct ChartGeometry {
    var size: CGSize
    var series: [Double?]
    var baseline: Double?
    var inset: CGFloat
    private var lo: Double
    private var hi: Double

    /// `include` widens the vertical range (a band that must stay in view); `fromZero` starts it at 0, for bars.
    init(size: CGSize, series: [Double?], baseline: Double?, inset: CGFloat, include: [Double] = [], fromZero: Bool = false) {
        self.size = size
        self.series = series
        self.baseline = baseline
        self.inset = inset
        let values = series.compactMap { $0 } + [baseline].compactMap { $0 } + include
        var l = values.min() ?? 0, h = values.max() ?? 1
        if fromZero { l = min(l, 0) }
        if h - l < 1e-6 { l -= 1; h += 1 }
        let pad = (h - l) * 0.1
        lo = fromZero ? l : l - pad
        hi = h + pad
    }

    func y(_ v: Double) -> CGFloat { size.height - inset - CGFloat((v - lo) / (hi - lo)) * (size.height - 2 * inset) }

    func point(_ i: Int, _ v: Double) -> CGPoint {
        let n = max(series.count - 1, 1)
        return CGPoint(x: inset + CGFloat(i) / CGFloat(n) * (size.width - 2 * inset), y: y(v))
    }

    var last: CGPoint? {
        guard let i = series.lastIndex(where: { $0 != nil }), let v = series[i] else { return nil }
        return point(i, v)
    }
}


extension ChartGeometry {
    /// Contiguous stretches of the series; a gap in the data breaks the line.
    var runs: [[CGPoint]] {
        var out: [[CGPoint]] = []
        var cur: [CGPoint] = []
        for (i, v) in series.enumerated() {
            if let v { cur.append(point(i, v)) } else if !cur.isEmpty { out.append(cur); cur = [] }
        }
        if !cur.isEmpty { out.append(cur) }
        return out
    }
}

/// A smooth curve through the points that never overshoots them (monotone cubic), so a curve never invents a peak.
private func addCurve(_ pts: [CGPoint], to path: inout Path) {
    guard let first = pts.first else { return }
    path.move(to: first)
    let n = pts.count
    if n == 1 { path.addLine(to: first); return }
    if n == 2 { path.addLine(to: pts[1]); return }
    var dx = [CGFloat](), m = [CGFloat]()
    for i in 0..<n - 1 {
        dx.append(max(pts[i + 1].x - pts[i].x, 0.001))
        m.append((pts[i + 1].y - pts[i].y) / dx[i])
    }
    var t = [CGFloat](repeating: 0, count: n)
    t[0] = m[0]
    t[n - 1] = m[n - 2]
    for i in 1..<n - 1 { t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2 }
    for i in 0..<n - 1 {
        if m[i] == 0 { t[i] = 0; t[i + 1] = 0; continue }
        let a = t[i] / m[i], b = t[i + 1] / m[i]
        let s = a * a + b * b
        if s > 9 { let k = 3 / s.squareRoot(); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i] }
    }
    for i in 0..<n - 1 {
        let h = dx[i] / 3
        path.addCurve(
            to: pts[i + 1], control1: CGPoint(x: pts[i].x + h, y: pts[i].y + t[i] * h),
            control2: CGPoint(x: pts[i + 1].x - h, y: pts[i + 1].y - t[i + 1] * h))
    }
}

struct SeriesLine: Shape {
    var geo: ChartGeometry

    func path(in rect: CGRect) -> Path {
        var path = Path()
        for run in geo.runs { addCurve(run, to: &path) }
        return path
    }
}

/// The soft flat area under the line, down to the chart's floor.
struct SeriesArea: Shape {
    var geo: ChartGeometry

    func path(in rect: CGRect) -> Path {
        var path = Path()
        for run in geo.runs where run.count > 1 {
            addCurve(run, to: &path)
            path.addLine(to: CGPoint(x: run[run.count - 1].x, y: rect.maxY))
            path.addLine(to: CGPoint(x: run[0].x, y: rect.maxY))
            path.closeSubpath()
        }
        return path
    }
}

/// A line of nights (or quarter hours) ending in a dot. A gap breaks the line; the dotted rule is "your normal".
struct ThickLine: View {
    var series: [Double?]
    var metric: Metric
    var baseline: Double?
    /// Trend-only metrics (D13) are drawn dashed.
    var dashed = false
    var play: Bool
    var dot: CGFloat = 10
    var delay = 0.2
    /// Draw a soft flat area under the line (off by default: the bare line reads better).
    var area = false

    var body: some View {
        GeometryReader { g in
            let geo = ChartGeometry(size: g.size, series: series, baseline: baseline, inset: dot / 2 + 3)
            ZStack {
                if let b = baseline {
                    Path { p in
                        p.move(to: CGPoint(x: 0, y: geo.y(b)))
                        p.addLine(to: CGPoint(x: g.size.width, y: geo.y(b)))
                    }
                    .stroke(Palette.text3.opacity(0.8), style: StrokeStyle(lineWidth: 1.5, lineCap: .round, dash: [0.1, 5]))
                }
                if area, !dashed {
                    SeriesArea(geo: geo).fill(metric.color.opacity(0.13)).modifier(DrawIn(play: play, delay: delay))
                }
                SeriesLine(geo: geo)
                    .stroke(
                        metric.color,
                        style: StrokeStyle(lineWidth: stroke, lineCap: .round, lineJoin: .round, dash: dashed ? [9, 8] : []))
                    .modifier(DrawIn(play: play, delay: delay))
                if let p = geo.last {
                    Circle().fill(metric.color).frame(width: dot, height: dot)
                        .scaleEffect(play ? 1 : 0.01)
                        .position(p)
                        .motion(.easeOut(duration: 0.35).delay(delay + 0.85), value: play)
                }
            }
        }
        .accessibilityHidden(true)
    }
}

/// Reveals a drawing from left to right.
struct DrawIn: ViewModifier {
    var play: Bool
    var delay: Double

    func body(content: Content) -> some View {
        content
            .mask(alignment: .leading) { Rectangle().scaleEffect(x: play ? 1 : 0.001, anchor: .leading) }
            .motion(ChartMotion.draw(delay), value: play)
    }
}

/// Capsules, one per bin. A bin that has not happened yet is an open dot.
struct ThickBars: View {
    var values: [Int?]
    var metric: Metric
    var play: Bool

    var body: some View {
        GeometryReader { g in
            let n = max(values.count, 1)
            let gap: CGFloat = 8
            let w = min((g.size.width - gap * CGFloat(n - 1)) / CGFloat(n), 14)
            let top = Double(values.compactMap { $0 }.max() ?? 1)
            HStack(alignment: .bottom, spacing: (g.size.width - w * CGFloat(n)) / CGFloat(max(n - 1, 1))) {
                ForEach(values.indices, id: \.self) { i in
                    if let v = values[i] {
                        let h = max(w, CGFloat(Double(v) / max(top, 1)) * g.size.height)
                        Capsule(style: .continuous)
                            .fill(metric.color)
                            .frame(width: w, height: play ? h : w)
                            .motion(ChartMotion.grow(0.15 + Double(i) * 0.05), value: play)
                    } else {
                        Circle().strokeBorder(Palette.text3, lineWidth: 2).frame(width: w * 0.55, height: w * 0.55)
                            .frame(width: w)
                    }
                }
            }
            .frame(width: g.size.width, height: g.size.height, alignment: .bottom)
        }
        .accessibilityHidden(true)
    }
}

/// What moved readiness: one capsule per component, to the right of the centre line when it helps and to the left when it
/// lowers, as long as it weighs. The centre line is "your normal". A missing signal is a dotted stub.
struct ContributionBars: View {
    var components: ReadinessComponents
    var play: Bool

    private func label(_ c: ReadinessComponent) -> String {
        switch c {
        case .sleep: return L("today.label.sleep")
        case .hrv: return L("today.label.hrv")
        case .rhr: return L("today.label.rhr")
        case .temp: return L("today.label.temp")
        }
    }

    var body: some View {
        GeometryReader { g in
            let rows = ReadinessComponent.allCases
            let n = CGFloat(rows.count)
            let gap: CGFloat = 4
            let rowH = (g.size.height - gap * (n - 1)) / n
            let bar: CGFloat = 8
            let left: CGFloat = 78
            let centre = left + (g.size.width - left) / 2
            let half = (g.size.width - left) / 2
            ZStack(alignment: .topLeading) {
                Rectangle().fill(Palette.text3).frame(width: 1.5, height: g.size.height).position(x: centre, y: g.size.height / 2)
                ForEach(Array(rows.enumerated()), id: \.offset) { i, c in
                    let y = CGFloat(i) * (rowH + gap) + rowH / 2
                    Text(label(c))
                        .font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3).lineLimit(1)
                        .frame(width: left - 8, alignment: .leading)
                        .position(x: (left - 8) / 2, y: y)
                    if let z = components[c] {
                        let len = max(CGFloat(min(abs(z), 2) / 2) * (half - 6), bar)
                        let dir: CGFloat = z >= 0 ? 1 : -1
                        let now = play ? len : bar
                        Capsule(style: .continuous)
                            .fill(c.metric.color)
                            .frame(width: now, height: bar)
                            .position(x: centre + dir * (now / 2 - (abs(z) < 0.05 ? bar / 2 : 0)), y: y)
                            .motion(ChartMotion.grow(0.2 + Double(i) * 0.07), value: play)
                    } else {
                        Capsule(style: .continuous)
                            .strokeBorder(Palette.text3, style: StrokeStyle(lineWidth: 1.5, dash: [3, 4]))
                            .frame(width: 30, height: bar)
                            .position(x: centre, y: y)
                            .opacity(play ? 1 : 0)
                            .motion(.easeOut(duration: 0.4).delay(0.5), value: play)
                    }
                }
            }
        }
        .accessibilityHidden(true)
    }
}

/// The recovery scale: a track split by the two thresholds into low, moderate and high (named under it), the part up to the
/// score in the recovery colour and a knob at its end. It fills once, smoothly, and stops.
struct ReadinessGauge: View {
    var score: Int?
    var play: Bool

    var body: some View {
        GeometryReader { g in
            let knob: CGFloat = 18
            let pad = knob / 2
            let track: CGFloat = 6
            let width = g.size.width - 2 * pad
            let at: (Double) -> CGFloat = { pad + CGFloat(min(max($0, 0), 100) / 100) * width }
            let x = at(Double(score ?? 50))
            let t = ScoreZone.thresholds(.recovery)
            let barY: CGFloat = knob / 2
            ZStack(alignment: .topLeading) {
                Capsule(style: .continuous).fill(Palette.hairline).frame(height: track)
                    .position(x: g.size.width / 2, y: barY).frame(width: g.size.width, height: g.size.height, alignment: .topLeading)
                ForEach([t.low, t.high], id: \.self) { v in
                    Rectangle().fill(Palette.text3).frame(width: 1.5, height: 14).position(x: at(Double(v)), y: barY)
                }
                if score != nil {
                    Capsule(style: .continuous).fill(Metric.readiness.color)
                        .frame(width: play ? x : track, height: track)
                        .position(x: (play ? x : track) / 2, y: barY)
                        .motion(ChartMotion.draw(0.2), value: play)
                    Circle().fill(Metric.readiness.color).frame(width: knob, height: knob)
                        .position(x: play ? x : pad, y: barY)
                        .motion(ChartMotion.draw(0.2), value: play)
                }
                // The three zones, named where they are.
                ForEach(0..<3, id: \.self) { i in
                    let lo = i == 0 ? 0 : (i == 1 ? t.low : t.high), hi = i == 0 ? t.low : (i == 1 ? t.high : 100)
                    Text(ScoreZone.allCases[i].word(.recovery))
                        .font(.monoFixed(.regular, 10)).foregroundStyle(Palette.text3)
                        .position(x: at(Double(lo + hi) / 2), y: g.size.height - 6)
                }
            }
        }
        .accessibilityHidden(true)
    }
}

/// A night as a step line: wake at the top, deep at the bottom. Draws left to right.
struct Hypnogram: View {
    /// Width reserved on the left for the row names, so the times beneath can line up with the plot.
    static let gutter: CGFloat = 62

    var block: SleepBlock
    var play: Bool
    /// Name each row (awake, REM, light, deep) in a column to the left of the plot.
    var labels = false

    var body: some View {
        GeometryReader { g in
            let rows = SleepStage.allCases
            let pad: CGFloat = 5
            let rowH = (g.size.height - 2 * pad) / CGFloat(rows.count - 1)
            let total = CGFloat(max(block.minutes, 1))
            let gutter = labels ? Self.gutter : 0
            let x: (Int) -> CGFloat = { gutter + CGFloat($0) / total * (g.size.width - gutter) }
            let y: (SleepStage) -> CGFloat = { pad + CGFloat(rows.firstIndex(of: $0) ?? 0) * rowH }
            ZStack {
                if labels {
                    ForEach(rows, id: \.self) { stage in
                        Text(name(stage))
                            .font(.monoFixed(.regular, 10)).foregroundStyle(Palette.text3)
                            .lineLimit(1).minimumScaleFactor(0.8)
                            .frame(width: gutter - 8, alignment: .leading)
                            .position(x: (gutter - 8) / 2, y: y(stage))
                    }
                }
                ForEach(0..<(block.segments.count - 1), id: \.self) { i in
                    let a = block.segments[i], b = block.segments[i + 1]
                    Path { p in
                        p.move(to: CGPoint(x: x(a.end), y: y(a.stage)))
                        p.addLine(to: CGPoint(x: x(a.end), y: y(b.stage)))
                    }
                    .stroke(Palette.text3.opacity(0.7), style: StrokeStyle(lineWidth: 2, lineCap: .round))
                }
                ForEach(block.segments.indices, id: \.self) { i in
                    let s = block.segments[i]
                    let len = max(x(s.end) - x(s.start), 10)
                    if s.stage == .wake {
                        Capsule().strokeBorder(Palette.text2, lineWidth: 2).frame(width: len, height: 9)
                            .position(x: x(s.start) + len / 2, y: y(s.stage))
                    } else {
                        Capsule().fill(color(s.stage)).frame(width: len, height: 9).position(x: x(s.start) + len / 2, y: y(s.stage))
                    }
                }
            }
            .modifier(DrawIn(play: play, delay: 0.2))
        }
        .accessibilityHidden(true)
    }

    private func name(_ s: SleepStage) -> String {
        switch s {
        case .wake: return L("today.stage.wake")
        case .rem: return L("today.stage.rem")
        case .light: return L("today.stage.light")
        case .deep: return L("today.stage.deep")
        }
    }

    private func color(_ s: SleepStage) -> Color {
        switch s {
        case .deep: return Palette.stageDeep
        case .light: return Palette.stageLight
        case .rem: return Palette.stageRem
        case .wake: return Palette.text2
        }
    }
}

/// The day laid flat over 24 hours: heart rate as one capsule per hour (its range, with 60 and 120 marked at the right), sleep
/// as a capsule beneath, a rule at "now". An hour with no reading is simply empty.
struct DayTapeChart: View {
    var tape: DayTape
    var play: Bool
    private let low = 40.0, high = 125.0

    var body: some View {
        GeometryReader { g in
            let top: CGFloat = 14
            let lane = g.size.height - 34 - top
            let slot = g.size.width / 24
            let w = min(slot * 0.5, 8)
            let hourly = tape.hourly
            let yOf: (Double) -> CGFloat = { lane - CGFloat(($0 - low) / (high - low)) * (lane - 10) - 5 }
            let nowX = CGFloat(tape.nowMinute) / 1440 * g.size.width
            ZStack(alignment: .topLeading) {
                ZStack(alignment: .topLeading) {
                    ForEach([60.0, 120.0], id: \.self) { v in
                        Path { p in
                            p.move(to: CGPoint(x: 0, y: yOf(v)))
                            p.addLine(to: CGPoint(x: g.size.width - 26, y: yOf(v)))
                        }
                        .stroke(Palette.text3.opacity(0.5), style: StrokeStyle(lineWidth: 1, lineCap: .round, dash: [0.1, 4]))
                        Text("\(Int(v))").font(.monoFixed(.regular, 10)).foregroundStyle(Palette.text3)
                            .position(x: g.size.width - 10, y: yOf(v))
                    }
                    ForEach(0..<24, id: \.self) { h in
                        if let r = hourly[h] {
                            let yHi = yOf(Double(r.upperBound)), yLo = yOf(Double(r.lowerBound))
                            Capsule(style: .continuous)
                                .fill(Metric.heartRate.color)
                                .frame(width: w, height: play ? max(yLo - yHi, w) : w)
                                .position(x: slot * (CGFloat(h) + 0.5), y: play ? (yHi + yLo) / 2 : yLo)
                                .motion(ChartMotion.grow(0.1 + Double(h) * 0.02), value: play)
                        }
                    }
                    ForEach(tape.sleep.indices, id: \.self) { i in
                        let r = tape.sleep[i]
                        let x0 = CGFloat(r.lowerBound) / 1440 * g.size.width, x1 = CGFloat(r.upperBound) / 1440 * g.size.width
                        Capsule(style: .continuous).fill(Metric.sleep.color)
                            .frame(width: play ? x1 - x0 : 8, height: 8)
                            .position(x: x0 + (play ? (x1 - x0) / 2 : 4), y: lane + 10)
                            .motion(ChartMotion.draw(0.4), value: play)
                    }
                    Capsule().fill(Palette.text1).frame(width: 2, height: lane + 14)
                        .position(x: nowX, y: (lane + 14) / 2 - 2)
                        .opacity(play ? 1 : 0)
                        .motion(.easeOut(duration: 0.3).delay(1.0), value: play)
                }
                .offset(y: top)
                Text(L("today.tape.now")).font(.monoFixed(.regular, 10)).foregroundStyle(Palette.text1)
                    .position(x: min(max(nowX, 16), g.size.width - 40), y: 5)
                    .opacity(play ? 1 : 0)
                    .motion(.easeOut(duration: 0.3).delay(1.0), value: play)
                ForEach([0, 6, 12, 18, 24], id: \.self) { h in
                    Text(String(format: "%02d", h))
                        .font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3)
                        .position(x: min(max(slot * CGFloat(h), 8), g.size.width - 8), y: g.size.height - 6)
                }
            }
        }
        .accessibilityHidden(true)
    }
}

/// A row of dots that fill up while the baseline is being built.
struct Dots: View {
    var done: Int
    var total: Int
    var color: Color
    var size: CGFloat = 14
    var play: Bool

    var body: some View {
        HStack(spacing: 0) {
            ForEach(0..<total, id: \.self) { i in
                Circle()
                    .fill(i < done ? color : Color.clear)
                    .overlay(Circle().strokeBorder(i < done ? color : Palette.text3, lineWidth: 2))
                    .frame(width: size, height: size)
                    .scaleEffect(play ? 1 : 0.2)
                    .opacity(play ? 1 : 0)
                    .motion(ChartMotion.grow(0.15 + Double(i) * 0.06), value: play)
                    .frame(maxWidth: .infinity)
            }
        }
    }
}
