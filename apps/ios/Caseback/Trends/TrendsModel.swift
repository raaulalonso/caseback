import Foundation
import Observation

// Trends: what the last 7, 30 or 90 days look like for each metric, against your own median. Everything here is pure so the
// rules (window, median, usual range, extremes, wording of values) are tested; the views only draw.

enum TrendRange: Int, CaseIterable, Identifiable {
    case week = 7, month = 30, quarter = 90

    var id: Int { rawValue }
    var days: Int { rawValue }
}

enum TrendMetric: CaseIterable, Identifiable {
    // The order is the order of the list: first what the signals add up to, then the signals themselves.
    case readiness, sleepScore, steps, sleep, restingHR, hrv, skinTemp, spo2

    var id: Self { self }

    /// What the signals add up to, in plain words: recovery, sleep and movement.
    static let summary: [TrendMetric] = [.readiness, .sleepScore, .steps]
    /// The technical signals behind them.
    static let signals: [TrendMetric] = [.sleep, .restingHR, .hrv, .skinTemp, .spo2]

    /// Scores have zones (low, moderate, high) instead of a usual range.
    var scoreKind: ScoreKind? {
        switch self {
        case .readiness: return .recovery
        case .sleepScore: return .sleep
        default: return nil
        }
    }

    var metric: Metric {
        switch self {
        case .readiness: return .readiness
        case .sleep, .sleepScore: return .sleep
        case .restingHR: return .heartRate
        case .hrv: return .hrv
        case .steps: return .steps
        case .skinTemp: return .skinTemp
        case .spo2: return .spo2
        }
    }

    var destination: TodayDestination {
        switch self {
        case .readiness: return .readiness
        case .sleep, .sleepScore: return .sleep
        case .restingHR: return .restingHR
        case .hrv: return .hrv
        case .steps: return .steps
        case .skinTemp: return .skinTemp
        case .spo2: return .spo2
        }
    }

    var name: String {
        switch self {
        case .readiness: return L("metric.3")
        case .sleepScore: return L("metric.2")
        case .sleep: return L("trends.hours")
        case .restingHR: return L("today.row.rhr")
        case .hrv: return L("metric.1")
        case .steps: return L("trends.movement")
        case .skinTemp: return L("today.tile.temp")
        case .spo2: return L("metric.5")
        }
    }

    /// A change smaller than this, in the metric's unit, is "stable".
    var stableStep: Double {
        switch self {
        case .readiness, .sleepScore: return 3
        case .restingHR: return 1
        case .hrv: return 2
        case .skinTemp: return 0.15
        case .spo2: return 0.5
        case .sleep: return 15
        case .steps: return 400
        }
    }

    /// One bar per day instead of a line: totals, not readings.
    var isBars: Bool { self == .sleep || self == .steps }
    /// The smallest vertical range a chart shows, in the metric's unit, so a few beats of noise are not blown up into a mountain.
    var minimumSpan: Double {
        switch self {
        case .readiness: return 24
        case .restingHR: return 8
        case .hrv: return 16
        case .skinTemp: return 1.2
        case .spo2: return 6
        case .sleep, .steps, .sleepScore: return 0
        }
    }

    /// Values that widen a chart's range to at least `minimumSpan` around what it holds.
    func padding(for values: [Double]) -> [Double] {
        if let kind = scoreKind {
            // From a little under the lowest limit (or the lowest day) up to 100, so the zones stay in view.
            let low = Double(ScoreZone.thresholds(kind).low) - 12
            return [max(0, min((values.min() ?? 100) - 5, low)), 100]
        }
        guard minimumSpan > 0, let lo = values.min(), let hi = values.max(), hi - lo < minimumSpan else { return [] }
        let c = (lo + hi) / 2
        return [c - minimumSpan / 2, c + minimumSpan / 2]
    }

    /// SpO2 and skin temperature are trends only (D13): dashed and named so.
    var trendOnly: Bool { self == .skinTemp || self == .spo2 }
}

/// One value per day, oldest first, the last one being today (or last night). A nil is a day with no value: the line breaks.
struct TrendSeries: Equatable {
    var values: [Double?]
    /// Skin temperature while it builds its baseline: nights recorded so far (< 5), and no values yet.
    var calibratingNights: Int?
    /// Today's value is not final yet (steps): drawn open.
    var lastIsPartial = false
}

struct TrendsSnapshot: Equatable {
    var series: [TrendMetric: TrendSeries]
    /// Nights recorded: under 3 there is nothing to draw.
    var nights: Int
    /// The day of the last value.
    var endDate: Date

    static let minimumNights = 3
}

struct TrendReading: Equatable {
    /// The last `range.days` values (fewer if fewer exist).
    var window: [Double?]
    /// Median and usual range (the middle half) of the last 30 days: "your normal".
    var median: Double?
    var usual: ClosedRange<Double>?
    var latest: Double?
    /// `latest` minus `median`.
    var delta: Double?
    var low: (index: Int, value: Double)?
    var high: (index: Int, value: Double)?

    static func == (a: TrendReading, b: TrendReading) -> Bool {
        a.window == b.window && a.median == b.median && a.usual == b.usual && a.latest == b.latest
            && a.low?.index == b.low?.index && a.high?.index == b.high?.index
    }
}

enum TrendMath {
    static let minimumForNormal = 7

    /// Linear-interpolated quantile of unsorted values, `q` in 0...1.
    static func quantile(_ values: [Double], _ q: Double) -> Double? {
        guard !values.isEmpty else { return nil }
        let s = values.sorted()
        let pos = min(max(q, 0), 1) * Double(s.count - 1)
        let lo = Int(pos.rounded(.down)), hi = Int(pos.rounded(.up))
        return s[lo] + (s[hi] - s[lo]) * (pos - Double(lo))
    }

    /// "Your normal" needs at least seven values behind it; before that there is no median and no band.
    static func reading(_ series: TrendSeries, range: TrendRange) -> TrendReading {
        let window = Array(series.values.suffix(range.days))
        // A day that is not over yet (steps so far) is neither part of "your normal" nor compared with it.
        let closed = series.lastIsPartial ? Array(series.values.dropLast()) : series.values
        let base = closed.suffix(30).compactMap { $0 }
        let median = base.count >= minimumForNormal ? quantile(base, 0.5) : nil
        let usual: ClosedRange<Double>? = {
            guard base.count >= minimumForNormal, let a = quantile(base, 0.25), let b = quantile(base, 0.75) else { return nil }
            return a...b
        }()
        let latest = window.last(where: { $0 != nil }) ?? nil
        var low: (Int, Double)?, high: (Int, Double)?
        for (i, v) in window.enumerated() {
            // The lowest and highest day are over days; today so far is not one of them.
            guard let v, !(series.lastIsPartial && i == window.count - 1) else { continue }
            if low == nil || v < low!.1 { low = (i, v) }
            if high == nil || v > high!.1 { high = (i, v) }
        }
        return TrendReading(
            window: window, median: median, usual: usual, latest: latest,
            delta: series.lastIsPartial ? nil : latest.flatMap { l in median.map { l - $0 } },
            low: low.map { (index: $0.0, value: $0.1) }, high: high.map { (index: $0.0, value: $0.1) })
    }

    /// The date of position `index` in a window of `count` days that ends on `end`.
    static func date(index: Int, count: Int, end: Date) -> Date {
        Calendar.current.date(byAdding: .day, value: index - (count - 1), to: end) ?? end
    }
}

enum TrendFormat {
    private static func minus(_ s: String) -> String { s.replacingOccurrences(of: "-", with: "−") }

    /// The number and its unit, "7 h 12" / "", "58" / "bpm".
    static func parts(_ v: Double, _ m: TrendMetric) -> (value: String, unit: String) {
        switch m {
        case .sleep:
            let d = TodayFormat.duration(minutes: Int(v.rounded()))
            return (d.value, d.unit)
        case .skinTemp: return (minus(String(format: "%+.1f", v)), "°C")
        case .spo2: return ("\(Int(v.rounded()))", "%")
        case .restingHR: return ("\(Int(v.rounded()))", "bpm")
        case .hrv: return ("\(Int(v.rounded()))", "ms")
        case .readiness, .sleepScore: return ("\(Int(v.rounded()))", "")
        case .steps:
            return (NumberFormatter.localizedString(from: NSNumber(value: Int(v.rounded())), number: .decimal), L("trends.steps.unit"))
        }
    }

    static func text(_ v: Double, _ m: TrendMetric) -> String {
        let p = parts(v, m)
        return p.unit.isEmpty ? p.value : "\(p.value) \(p.unit)"
    }

    /// A change, signed with a real minus sign.
    static func delta(_ d: Double, _ m: TrendMetric) -> String {
        switch m {
        case .sleep: return TodayFormat.sleepDelta(minutes: Int(d.rounded()))
        case .skinTemp: return minus(String(format: "%+.1f", d))
        default: return TodayFormat.signed(Int(d.rounded()))
        }
    }

    static func shortDate(_ d: Date) -> String { d.formatted(.dateTime.day().month(.abbreviated)) }
    static func longDate(_ d: Date) -> String { d.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated)) }
}

/// The sentence under the chart: what the period says, in plain words. Scores say how many days fell in each zone; signals say
/// whether they ended higher, lower or the same as they began (the last third of the period against the first).
enum TrendConclusion {
    static func zoneCounts(_ window: [Double?], _ kind: ScoreKind) -> (high: Int, moderate: Int, low: Int) {
        var c = (high: 0, moderate: 0, low: 0)
        for v in window.compactMap({ $0 }) {
            switch ScoreZone.of(Int(v.rounded()), kind) {
            case .high: c.high += 1
            case .moderate: c.moderate += 1
            case .low: c.low += 1
            }
        }
        return c
    }

    /// Change from the first third of the period to the last, by medians; nil with too few values.
    static func change(_ window: [Double?]) -> Double? {
        let values = window.compactMap { $0 }
        guard values.count >= 6 else { return nil }
        let third = max(values.count / 3, 2)
        guard let first = TrendMath.quantile(Array(values.prefix(third)), 0.5),
            let last = TrendMath.quantile(Array(values.suffix(third)), 0.5)
        else { return nil }
        return last - first
    }

    static func text(_ m: TrendMetric, series: TrendSeries, reading: TrendReading) -> String? {
        // A day still in progress is not part of the story yet.
        let window = series.lastIsPartial ? Array(reading.window.dropLast()) : reading.window
        if let kind = m.scoreKind {
            let c = zoneCounts(window, kind)
            let total = c.high + c.moderate + c.low
            guard total > 0 else { return nil }
            return L("trends.concl.zones", c.high, total, c.moderate, c.low)
        }
        guard let d = change(window) else { return nil }
        if abs(d) <= m.stableStep { return L("trends.concl.stable") }
        return L(d > 0 ? "trends.concl.up" : "trends.concl.down", TrendFormat.delta(d, m))
    }
}

@MainActor
@Observable
final class TrendsModel {
    let snapshot: TrendsSnapshot
    var range: TrendRange
    var metric: TrendMetric
    /// The day under the finger on the big chart, as an index into the window.
    var scrub: Int?
    /// The chart whose explanation is showing.
    var info: TrendMetric?

    init(snapshot: TrendsSnapshot, range: TrendRange = .month, metric: TrendMetric = .readiness) {
        self.snapshot = snapshot
        self.range = range
        self.metric = metric
    }

    var hasTrends: Bool { snapshot.nights >= TrendsSnapshot.minimumNights }

    func series(_ m: TrendMetric) -> TrendSeries { snapshot.series[m] ?? TrendSeries(values: []) }
    func reading(_ m: TrendMetric) -> TrendReading { TrendMath.reading(series(m), range: range) }
}
