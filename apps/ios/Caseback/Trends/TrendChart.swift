import SwiftUI

// The charts of Trends: the big one you can scrub with a finger, and the small one of every row. Same language as Today: a
// thin smooth line (or capsule bars), your usual range as a faint band with the median dotted, gaps left empty, trend-only
// metrics dashed. Only the charts move.

struct TrendChart: View {
    var metric: TrendMetric
    var reading: TrendReading
    var partialLast: Bool
    var endDate: Date
    var play: Bool
    /// The day under the finger, as an index into the window.
    var scrub: Int?
    var onScrub: (Int?) -> Void

    private let inset: CGFloat = 10
    private let labelHeight: CGFloat = 18

    var body: some View {
        GeometryReader { g in
            let n = reading.window.count
            // Scores keep a gutter at the right where their zones are named, so no word ever sits on the line.
            let gutter: CGFloat = metric.scoreKind == nil ? 0 : 56
            let plot = CGSize(width: g.size.width - gutter, height: max(g.size.height - labelHeight, 1))
            let band = (metric.scoreKind == nil ? [reading.usual?.lowerBound, reading.usual?.upperBound, reading.median] : []).compactMap { $0 }
                + metric.padding(for: reading.window.compactMap { $0 })
            let geo = ChartGeometry(
                size: plot, series: reading.window, baseline: reading.median, inset: inset, include: band, fromZero: metric.isBars)
            ZStack(alignment: .topLeading) {
                if let kind = metric.scoreKind {
                    zones(kind, geo: geo, plot: plot, total: g.size.width)
                } else if let u = reading.usual {
                    let top = geo.y(u.upperBound), bottom = geo.y(u.lowerBound)
                    Rectangle().fill(Palette.text3.opacity(0.14))
                        .frame(width: plot.width, height: max(bottom - top, 2))
                        .position(x: plot.width / 2, y: (top + bottom) / 2)
                        .opacity(play ? 1 : 0)
                        .motion(.easeOut(duration: 0.5), value: play)
                }
                if metric.scoreKind == nil, let m = reading.median {
                    Path { p in
                        p.move(to: CGPoint(x: 0, y: geo.y(m)))
                        p.addLine(to: CGPoint(x: plot.width, y: geo.y(m)))
                    }
                    .stroke(Palette.text3.opacity(0.9), style: StrokeStyle(lineWidth: 1.5, lineCap: .round, dash: [0.1, 5]))
                }
                if metric.isBars { bars(geo: geo, plot: plot, n: n) } else { line(geo: geo, n: n) }
                if let s = scrub, s < n { cursor(s, geo: geo, plot: plot, n: n) }
                axis(CGSize(width: plot.width, height: g.size.height), n: n)
            }
            .contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { v in
                        guard n > 0 else { return }
                        let step = (plot.width - 2 * inset) / CGFloat(max(n - 1, 1))
                        let i = min(max(Int(((v.location.x - inset) / max(step, 0.001)).rounded()), 0), n - 1)
                        if i != scrub { Haptics.tick(); onScrub(i) }
                    }
                    .onEnded { _ in onScrub(nil) })
        }
    }

    /// The limits between low, moderate and high as dotted lines across the chart, each zone named in the gutter on the right.
    private func zones(_ kind: ScoreKind, geo: ChartGeometry, plot: CGSize, total: CGFloat) -> some View {
        let t = ScoreZone.thresholds(kind)
        let spans: [(ScoreZone, Double)] = [
            (.high, Double(t.high + 100) / 2), (.moderate, Double(t.low + t.high) / 2), (.low, Double(t.low) / 2),
        ]
        return ZStack {
            ForEach([t.low, t.high], id: \.self) { limit in
                Path { p in
                    p.move(to: CGPoint(x: 0, y: geo.y(Double(limit))))
                    p.addLine(to: CGPoint(x: total, y: geo.y(Double(limit))))
                }
                .stroke(Palette.text3.opacity(0.9), style: StrokeStyle(lineWidth: 1.5, lineCap: .round, dash: [0.1, 5]))
            }
            ForEach(spans, id: \.1) { zone, mid in
                // The lowest zone may reach below the chart: its name sits between its limit and the floor.
                let y = zone == .low ? (geo.y(Double(t.low)) + plot.height) / 2 : geo.y(mid)
                Text(zone.word(kind)).font(.monoFixed(.regular, 10)).foregroundStyle(Palette.text3)
                    .position(x: (plot.width + total) / 2 + 2, y: y)
            }
        }
        .opacity(play ? 1 : 0)
        .motion(.easeOut(duration: 0.5), value: play)
    }

    private func lineWidth(_ n: Int) -> CGFloat { n <= 8 ? 3.5 : (n <= 31 ? 3 : 2.25) }

    private func line(geo: ChartGeometry, n: Int) -> some View {
        ZStack {
            SeriesLine(geo: geo)
                .stroke(
                    metric.metric.color,
                    style: StrokeStyle(lineWidth: lineWidth(n), lineCap: .round, lineJoin: .round, dash: metric.trendOnly ? [9, 8] : []))
                .modifier(DrawIn(play: play, delay: 0.1))
            if let p = geo.last {
                Circle().fill(metric.metric.color).frame(width: 10, height: 10)
                    .scaleEffect(play ? 1 : 0.01)
                    .position(p)
                    .motion(.easeOut(duration: 0.35).delay(0.95), value: play)
            }
        }
    }

    private func bars(geo: ChartGeometry, plot: CGSize, n: Int) -> some View {
        let step = (plot.width - 2 * inset) / CGFloat(max(n - 1, 1))
        let w = min(max(step * 0.6, 2), 14)
        let floorY = geo.y(0)
        return ZStack {
            ForEach(reading.window.indices, id: \.self) { i in
                if let v = reading.window[i] {
                    let h = max(floorY - geo.y(v), w)
                    let open = partialLast && i == n - 1
                    let dim = scrub != nil && scrub != i
                    Capsule(style: .continuous)
                        .fill(open ? Color.clear : metric.metric.color.opacity(dim ? 0.3 : 1))
                        .overlay(Capsule(style: .continuous).strokeBorder(open ? metric.metric.color : .clear, lineWidth: 1.5))
                        .frame(width: w, height: play ? h : w)
                        .position(x: geo.point(i, 0).x, y: floorY - (play ? h : w) / 2)
                        .motion(ChartMotion.grow(0.1 + min(Double(i) * 0.008, 0.6)), value: play)
                }
            }
        }
    }

    private func cursor(_ i: Int, geo: ChartGeometry, plot: CGSize, n: Int) -> some View {
        let x = geo.point(i, 0).x
        return ZStack {
            Rectangle().fill(Palette.text1.opacity(0.85)).frame(width: 1.5, height: plot.height).position(x: x, y: plot.height / 2)
            if !metric.isBars, let v = reading.window[i] {
                Circle().fill(metric.metric.color).frame(width: 14, height: 14)
                    .overlay(Circle().strokeBorder(Palette.ground, lineWidth: 3))
                    .position(geo.point(i, v))
            }
        }
    }

    /// The first, middle and last date of the window.
    private func axis(_ size: CGSize, n: Int) -> some View {
        let dates = [0, (n - 1) / 2, n - 1].map { TrendFormat.shortDate(TrendMath.date(index: $0, count: n, end: endDate)) }
        return HStack {
            Text(dates[0]); Spacer(); if n > 6 { Text(dates[1]); Spacer() }; Text(dates[2])
        }
        .font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3)
        .frame(width: size.width)
        .position(x: size.width / 2, y: size.height - 7)
    }
}

/// A small line for a row of the list: no band, no axis, just the shape of the range.
struct Sparkline: View {
    var series: [Double?]
    var metric: TrendMetric
    var play: Bool

    var body: some View {
        GeometryReader { g in
            let geo = ChartGeometry(
                size: g.size, series: series, baseline: nil, inset: 5, include: metric.padding(for: series.compactMap { $0 }))
            ZStack {
                SeriesLine(geo: geo)
                    .stroke(
                        metric.metric.color,
                        style: StrokeStyle(lineWidth: 2.25, lineCap: .round, lineJoin: .round, dash: metric.trendOnly ? [6, 6] : []))
                    .modifier(DrawIn(play: play, delay: 0.05))
                if let p = geo.last {
                    Circle().fill(metric.metric.color).frame(width: 6, height: 6)
                        .scaleEffect(play ? 1 : 0.01)
                        .position(p)
                        .motion(.easeOut(duration: 0.3).delay(0.8), value: play)
                }
            }
        }
        .accessibilityHidden(true)
    }
}
