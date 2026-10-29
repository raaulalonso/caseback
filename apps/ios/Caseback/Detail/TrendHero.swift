import SwiftUI

/// The top of a metric screen: the period, the number (the latest, or the day under the finger), the chart you can scrub, the
/// sentence that says what the period shows, and the lowest and highest day. The same chart as Trends, with its own period.
struct TrendHero: View {
    var metric: TrendMetric
    var series: TrendSeries
    var endDate: Date
    @Binding var range: TrendRange
    @Binding var scrub: Int?
    var play: Bool
    /// Extra control at the left of the period picker (the sleep screen swaps score and hours here).
    var chartHeight: CGFloat = 230

    var body: some View {
        let r = TrendMath.reading(series, range: range)
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text(L("trends.range.title", range.days)).font(.system(size: 14, weight: .medium)).foregroundStyle(Palette.text3)
                Spacer(minLength: 0)
                WordPicker(
                    options: TrendRange.allCases, selection: $range, label: { "\($0.days)" },
                    accessibility: { L("trends.range.title", $0.days) }, mono: true)
            }
            .frame(height: 34)
            readout(r).padding(.top, 6)
            if let nights = series.calibratingNights, series.values.isEmpty {
                calibrating(nights)
            } else {
                TrendChart(
                    metric: metric, reading: r, partialLast: series.lastIsPartial, endDate: endDate, play: play, scrub: scrub,
                    onScrub: { scrub = $0 }
                )
                .frame(height: chartHeight)
                .padding(.top, 10)
                .accessibilityElement()
                .accessibilityLabel(a11y(r))
                .accessibilityAdjustableAction { dir in step(dir, count: r.window.count) }
                if let c = TrendConclusion.text(metric, series: series, reading: r) {
                    Text(c).font(.system(size: 14)).foregroundStyle(Palette.text2)
                        .fixedSize(horizontal: false, vertical: true).padding(.top, 10)
                }
                if metric.scoreKind == nil { extremes(r).padding(.top, 8) }
            }
        }
        .padding(.bottom, Space.s16)
    }

    // MARK: readout

    @ViewBuilder private func readout(_ r: TrendReading) -> some View {
        if let nights = series.calibratingNights, series.values.isEmpty {
            ValueRow(value: "\(nights)/5", unit: L("today.temp.nights"), note: L("today.temp.trend"), size: 56)
        } else if let s = scrub, s < r.window.count {
            let date = TrendMath.date(index: s, count: r.window.count, end: endDate)
            if let v = r.window[s] {
                let p = TrendFormat.parts(v, metric)
                let partial = series.lastIsPartial && s == r.window.count - 1
                ValueRow(
                    value: p.value, unit: p.unit,
                    note: (metric.scoreKind.map { ScoreZone.of(Int(v.rounded()), $0).word($0) + " · " } ?? "")
                        + TrendFormat.longDate(date) + (partial ? " · " + L("trends.partial") : ""),
                    size: 56,
                    color: metric.scoreKind == nil ? Palette.text1 : metric.metric.color)
            } else {
                ValueRow(value: "—", note: TrendFormat.longDate(date) + " · " + L("trends.noData"), size: 56, dim: true)
            }
        } else if let v = r.latest {
            let p = TrendFormat.parts(v, metric)
            ValueRow(
                value: p.value, unit: p.unit, note: note(v, r), size: 56,
                color: metric.scoreKind == nil ? Palette.text1 : metric.metric.color)
        } else {
            ValueRow(value: "—", size: 56, dim: true)
        }
    }

    /// Under a score its zone and how it compares; under a signal how it compares with your median.
    private func note(_ v: Double, _ r: TrendReading) -> String {
        if series.lastIsPartial { return L("trends.partial") }
        if let kind = metric.scoreKind {
            let word = ScoreZone.of(Int(v.rounded()), kind).word(kind)
            guard let d = r.delta else { return word }
            return word + " · " + TrendFormat.delta(d, metric) + " " + L("today.vsMedian")
        }
        return r.delta.map { TrendFormat.delta($0, metric) + " " + L("today.vsMedian") } ?? L("trends.noBand")
    }

    private func calibrating(_ nights: Int) -> some View {
        VStack(spacing: 12) {
            Dots(done: nights, total: 5, color: metric.metric.color, size: 14, play: play)
            Text(L("today.temp.calibratingWord")).font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3)
        }
        .frame(maxWidth: .infinity).frame(height: chartHeight)
    }

    private func extremes(_ r: TrendReading) -> some View {
        let n = r.window.count
        func text(_ key: String, _ e: (index: Int, value: Double)?) -> String {
            guard let e else { return "" }
            return L(key, TrendFormat.text(e.value, metric), TrendFormat.shortDate(TrendMath.date(index: e.index, count: n, end: endDate)))
        }
        return HStack {
            Text(text("trends.low", r.low)); Spacer()
            Text(text("trends.high", r.high))
        }
        .font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3)
        .lineLimit(1).minimumScaleFactor(0.7)
    }

    private func step(_ dir: AccessibilityAdjustmentDirection, count: Int) {
        guard count > 0 else { return }
        let cur = scrub ?? count - 1
        switch dir {
        case .increment: scrub = min(cur + 1, count - 1)
        case .decrement: scrub = max(cur - 1, 0)
        @unknown default: break
        }
    }

    private func a11y(_ r: TrendReading) -> String {
        var parts = [metric.name, L("trends.range.title", range.days)]
        if let v = r.latest { parts.append(TrendFormat.text(v, metric)) }
        if let med = r.median { parts.append(L("today.signal.median", TrendFormat.text(med, metric))) }
        return parts.joined(separator: ", ")
    }
}
