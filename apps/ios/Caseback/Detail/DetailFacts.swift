import Foundation

// What the metric screens say beyond the chart: facts computed from the same data as Today and Trends. Pure, so the rules are
// tested. None of it gives advice; each line is a number and what it is compared with.

/// The night in the figures a person asks about: how long in bed, how long asleep, how much of the time in bed was sleep.
struct SleepFacts: Equatable {
    var inBedMinutes: Int
    var asleepMinutes: Int
    /// Asleep over in bed, 0 to 1.
    var efficiency: Double
    var from: String
    var to: String

    static func make(_ b: SleepBlock) -> SleepFacts? {
        guard let first = b.segments.first, let last = b.segments.last else { return nil }
        let inBed = last.end - first.start
        let awake = b.segments.filter { $0.stage == .wake }.reduce(0) { $0 + $1.end - $1.start }
        guard inBed > 0, inBed > awake else { return nil }
        return SleepFacts(
            inBedMinutes: inBed, asleepMinutes: inBed - awake, efficiency: Double(inBed - awake) / Double(inBed), from: b.from, to: b.to)
    }
}

/// This week's steps against your normal: the average of the last seven finished days and the median of the last thirty.
struct StepsWeek: Equatable {
    var average: Double
    var normal: Double

    static func make(_ series: TrendSeries) -> StepsWeek? {
        // Today is not over: it is neither in the average nor in the normal.
        let closed = series.lastIsPartial ? Array(series.values.dropLast()) : series.values
        let week = closed.suffix(7).compactMap { $0 }
        let month = closed.suffix(30).compactMap { $0 }
        guard week.count >= 4, month.count >= TrendMath.minimumForNormal, let normal = TrendMath.quantile(month, 0.5) else { return nil }
        return StepsWeek(average: week.reduce(0, +) / Double(week.count), normal: normal)
    }
}

/// The heart over the day so far: the lowest and highest hourly reading and the resting value of last night.
struct PulseFacts: Equatable {
    var lowest: Int?
    var highest: Int?
    var resting: Int?
    var hoursRead: Int
    var hoursElapsed: Int

    static func make(_ s: TodaySnapshot) -> PulseFacts? {
        guard let day = TodayInsights.daySummary(s) else { return nil }
        return PulseFacts(
            lowest: day.heartRate?.lowerBound, highest: day.heartRate?.upperBound, resting: s.restingHR?.value.flatMap { Int($0) },
            hoursRead: day.hoursRead, hoursElapsed: day.hoursElapsed)
    }
}

enum DetailCopy {
    /// Up to three things that can move a metric, in the soft voice of the app ("can", "usually"; never "means").
    static func affects(_ d: TodayDestination) -> [String] {
        let stem = d == .day ? "pulse" : d.infoKey
        return (1...3).map { L("detail.affects.\(stem).\($0)") }
    }

    /// "58–60", a single value when both ends are the same, and "−0,1 a +0,1" for signed deviations so two signs never touch.
    static func rangeText(_ r: ClosedRange<Double>, _ m: TrendMetric) -> String {
        let lo = TrendFormat.parts(r.lowerBound, m).value, hi = TrendFormat.parts(r.upperBound, m).value
        if lo == hi { return lo }
        return m == .skinTemp ? L("detail.normal.to", lo, hi) : "\(lo)–\(hi)"
    }

    /// What the "i" adds at the very end, small: how far to trust the metric, and that this is not a medical device. It is kept out
    /// of the screen on purpose: honest, but one level down.
    static func caveat(_ d: TodayDestination) -> String {
        let stem = d == .day ? "pulse" : d.infoKey
        return L("detail.caveat.\(stem)") + " " + L("detail.footer")
    }
}
