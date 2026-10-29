import Foundation
import Observation

// What Today shows and the rules that turn it into words. Pure data and pure functions so it can be tested; the views only
// draw it. Sources of every field: the design notes section B.

/// The four inputs of the readiness score, as the algorithm names them (`algorithms/wellness/caseback_wellness/readiness.py`).
enum ReadinessComponent: CaseIterable {
    case sleep, hrv, rhr, temp

    var metric: Metric {
        switch self {
        case .sleep: return .sleep
        case .hrv: return .hrv
        case .rhr: return .heartRate
        case .temp: return .skinTemp
        }
    }
}

/// z-scores against the personal baseline, positive = better than usual. A nil is a signal that was not available.
struct ReadinessComponents: Equatable {
    var sleep: Double?
    var hrv: Double?
    var rhr: Double?
    var temp: Double?

    subscript(c: ReadinessComponent) -> Double? {
        switch c {
        case .sleep: return sleep
        case .hrv: return hrv
        case .rhr: return rhr
        case .temp: return temp
        }
    }

    var present: [(ReadinessComponent, Double)] { ReadinessComponent.allCases.compactMap { c in self[c].map { (c, $0) } } }
}

enum ReadinessState: Equatable {
    case score(Int, ReadinessComponents)
    /// Fewer than seven days of baseline.
    case calibrating(day: Int)
    case noData
}

/// The only thing that ever interrupts the panel: something is wrong and the owner has to act. Nothing is shown when
/// everything is fine (no "connected", no battery, no sync time; those live in Device).
enum TodayAlert: Equatable {
    case bondLost
    case bluetoothOff
    /// Percent, 5 or less (S11).
    case batteryCritical(Int)

    var text: String {
        switch self {
        case .bondLost: return L("status.bondLost")
        case .bluetoothOff: return L("status.bluetoothOff")
        case .batteryCritical(let p): return L("today.alert.battery", p)
        }
    }
}

/// A night of seven values with its change against the 30-day median.
struct SeriesBlock: Equatable {
    var value: String?
    var unit: String
    /// Signed text, "−4".
    var delta: String?
    /// Seven nights, oldest first; nil is a night with no value (the line breaks there).
    var series: [Double?]
    /// The 30-day median, drawn as the dotted "your normal" line.
    var baseline: Double?

    /// Last night against the median, in whole units; nil without both.
    var deltaValue: Int? {
        guard let last = series.last(where: { $0 != nil }) ?? nil, let b = baseline else { return nil }
        return Int((last - b).rounded())
    }
}

enum SleepStage: CaseIterable {
    /// Top to bottom on the hypnogram.
    case wake, rem, light, deep
}

struct SleepSegment: Equatable {
    /// Minutes since falling asleep.
    var start: Int
    var end: Int
    var stage: SleepStage
}

struct SleepBlock: Equatable {
    var minutes: Int
    var deltaMinutes: Int
    var segments: [SleepSegment]
    /// "23:10", "06:22".
    var from: String
    var to: String
    /// Seven nights of duration in minutes, oldest first, and the 30-day median.
    var nights: [Double?] = []
    var baseline: Double?
    /// 0 to 100 (`SleepScore`), nil without stages.
    var score: Int?
}

struct PulseBlock: Equatable {
    var bpm: Int?
    var ageMinutes: Int
    /// Last four hours in quarter hours; nil is a hole.
    var recent: [Double?]
}

struct StepsBlock: Equatable {
    var total: Int
    /// Eight three-hour bins from midnight; nil for the part of the day that has not happened.
    var bins: [Int?]
}

/// SpO2 and skin temperature are trends (D13): drawn dashed with open marks and always named as such.
struct TrendBlock: Equatable {
    var value: String?
    var unit: String
    var series: [Double?]
    /// Nights recorded so far while there are fewer than five, nil once calibrated.
    var calibratingNights: Int?
}

/// A quarter of an hour of the day tape. Heart rate range over the bursts in it, nil for a hole.
struct TapeColumn: Equatable {
    var hrMin: Int?
    var hrMax: Int?
}

struct DayTape: Equatable {
    /// 96 columns, 00:00 to 24:00.
    var columns: [TapeColumn]
    /// Sleep that falls inside today, in minutes since midnight.
    var sleep: [Range<Int>]
    var nowMinute: Int

    /// 24 hourly ranges, nil where the hour has no reading (a hole, never interpolated).
    var hourly: [ClosedRange<Int>?] {
        (0..<24).map { h in
            let cols = columns[(h * 4)..<(h * 4 + 4)]
            let lows = cols.compactMap(\.hrMin), highs = cols.compactMap(\.hrMax)
            guard let lo = lows.min(), let hi = highs.max() else { return nil }
            return lo...hi
        }
    }

    /// Mean heart rate of the last `count` quarter hours up to now; nil where there is no reading.
    func recentHeartRate(count: Int) -> [Double?] {
        let end = min(nowMinute / 15, columns.count)
        let start = max(end - count, 0)
        return columns[start..<end].map { c in
            guard let lo = c.hrMin, let hi = c.hrMax else { return nil }
            return Double(lo + hi) / 2
        }
    }
}

struct TodaySnapshot: Equatable {
    var paired = true
    var alert: TodayAlert?
    var readiness: ReadinessState = .noData
    var sleep: SleepBlock?
    var restingHR: SeriesBlock?
    var hrv: SeriesBlock?
    var pulse: PulseBlock?
    var steps: StepsBlock?
    var skinTemp: TrendBlock?
    var spo2: TrendBlock?
    var tape = DayTape(columns: Array(repeating: TapeColumn(), count: 96), sleep: [], nowMinute: 0)
}

/// Where a tap goes. The destination screens are not designed yet; each opens a placeholder.
enum TodayDestination: Hashable, Identifiable {
    case readiness, sleep, restingHR, hrv, pulse, steps, skinTemp, spo2, day

    var metric: Metric {
        switch self {
        case .readiness: return .readiness
        case .sleep: return .sleep
        case .restingHR, .pulse, .day: return .heartRate
        case .hrv: return .hrv
        case .steps: return .steps
        case .skinTemp: return .skinTemp
        case .spo2: return .spo2
        }
    }

    var id: Self { self }

    static let allKnown: [TodayDestination] = [.readiness, .sleep, .restingHR, .hrv, .pulse, .steps, .skinTemp, .spo2, .day]

    /// The key stem of its explanation, "today.info.<stem>.what" and ".read".
    var infoKey: String {
        switch self {
        case .readiness: return "readiness"
        case .sleep: return "sleep"
        case .restingHR: return "restingHR"
        case .hrv: return "hrv"
        case .pulse: return "pulse"
        case .steps: return "steps"
        case .skinTemp: return "skinTemp"
        case .spo2: return "spo2"
        case .day: return "day"
        }
    }

    var title: String {
        switch self {
        case .readiness: return L("metric.3")
        case .sleep: return L("metric.2")
        case .restingHR: return L("today.row.rhr")
        case .hrv: return L("metric.1")
        case .pulse: return L("metric.0")
        case .steps: return L("metric.4")
        case .skinTemp: return L("metric.6")
        case .spo2: return L("metric.5")
        case .day: return L("today.today")
        }
    }
}

// MARK: words

enum ReadinessSentence {
    enum Level { case above, near, below }

    static func level(_ z: Double) -> Level { z >= 0.5 ? .above : (z <= -0.5 ? .below : .near) }

    /// Rule (04 §5): the two components with the largest |z| among those present, in reading order, joined with "and".
    /// The full version also adds a third within ±0.5 as "near usual" and "From N of 4 signals" when one is missing;
    /// the panel uses the short one, because the chart next to it already shows what is missing.
    static func make(_ c: ReadinessComponents, compact: Bool = false) -> String {
        let present = c.present
        guard !present.isEmpty else { return "" }
        // Skin temperature only counts when it is off; a near-usual temperature is never mentioned.
        let candidates = present.filter { $0.0 != .temp || level($0.1) == .below }
        let top = candidates.sorted { abs($0.1) > abs($1.1) }.prefix(2).map { $0 }
        let ordered = ReadinessComponent.allCases.compactMap { c in top.first { $0.0 == c } }
        var clauses = ordered.map { phrase($0.0, level($0.1)) }
        var text: String
        if ordered.count == 2, ordered.allSatisfy({ $0.0 == .sleep || $0.0 == .hrv }),
            level(ordered[0].1) == level(ordered[1].1)
        {
            // "Sleep and HRV above your usual": one predicate for both.
            let key = level(ordered[0].1) == .above ? "today.merge.above" : (level(ordered[0].1) == .below ? "today.merge.below" : "today.merge.near")
            text = L(key, capitalized(name(ordered[0].0)), name(ordered[1].0))
        } else if clauses.count >= 2 {
            text = L("today.sentence.and", capitalized(clauses.removeFirst()), clauses.removeFirst())
        } else if let only = clauses.first {
            text = capitalized(only) + "."
        } else {
            text = ""
        }
        if !compact {
            if let third = present.first(where: { c in !top.contains { $0.0 == c.0 } && c.0 != .temp && level(c.1) == .near }) {
                text += " " + L("today.sentence.near", capitalized(name(third.0)))
            }
            if present.count < ReadinessComponent.allCases.count {
                text += " " + L("today.sentence.signals", present.count, ReadinessComponent.allCases.count)
            }
        }
        return text.trimmingCharacters(in: .whitespaces)
    }

    static func phrase(_ c: ReadinessComponent, _ l: Level) -> String {
        let key: String
        switch (c, l) {
        case (.sleep, .above): key = "today.phrase.sleep.above"
        case (.sleep, .near): key = "today.phrase.sleep.near"
        case (.sleep, .below): key = "today.phrase.sleep.below"
        case (.hrv, .above): key = "today.phrase.hrv.above"
        case (.hrv, .near): key = "today.phrase.hrv.near"
        case (.hrv, .below): key = "today.phrase.hrv.below"
        // Resting HR: a positive z means a lower heart rate, so the words follow the heart rate, not the sign.
        case (.rhr, .above): key = "today.phrase.rhr.above"
        case (.rhr, .near): key = "today.phrase.rhr.near"
        case (.rhr, .below): key = "today.phrase.rhr.below"
        case (.temp, _): key = "today.phrase.temp.below"
        }
        return L(key)
    }

    static func name(_ c: ReadinessComponent) -> String { L("today.name.\(c)") }

    private static func capitalized(_ s: String) -> String { s.prefix(1).uppercased() + s.dropFirst() }
}

enum TodayFormat {
    /// "7 h 12", "45 min".
    static func duration(minutes: Int) -> (value: String, unit: String) {
        guard minutes >= 60 else { return ("\(minutes)", "min") }
        return (String(format: "%d h %02d", minutes / 60, minutes % 60), "")
    }

    /// Signed with a real minus sign, "+0" shown as "0".
    static func signed(_ v: Int) -> String { v == 0 ? "0" : (v > 0 ? "+\(v)" : "−\(abs(v))") }

    static func sleepDelta(minutes: Int) -> String {
        let sign = minutes < 0 ? "−" : (minutes > 0 ? "+" : "")
        let m = abs(minutes)
        return m >= 60 ? String(format: "%@%d h %02d", sign, m / 60, m % 60) : "\(sign)\(m) min"
    }

    static func age(minutes: Int) -> String {
        minutes < 60 ? L("today.age.min", minutes) : L("today.age.hour", minutes / 60)
    }

    /// "9 min", "3 h": the age without the "ago", for tight places.
    static func ageShort(minutes: Int) -> String { minutes < 60 ? "\(minutes) min" : "\(minutes / 60) h" }
}

// MARK: model

@MainActor
@Observable
final class TodayModel {
    private(set) var snapshot: TodaySnapshot
    /// 0 = now, 1 = last night.
    var page = 0
    /// The block that was tapped and the screen rectangle it occupied, for the expanding transition.
    private(set) var selected: TodayDestination?
    /// The chart whose explanation is showing.
    var info: TodayDestination?
    private(set) var origin: CGRect = .zero
    /// How much a metric screen covers Today, 0 to 1: Today steps back (smaller, dimmer) as the screen arrives and comes forward as it leaves.
    var coverage: CGFloat = 0

    init(snapshot: TodaySnapshot, page: Int = 0) {
        self.snapshot = snapshot
        self.page = page
    }

    func open(_ destination: TodayDestination, from frame: CGRect) {
        origin = frame
        selected = destination
    }

    /// Go from one metric screen to another (a signal behind a score): the screen stays, its content changes.
    func navigate(_ destination: TodayDestination) { selected = destination }

    func close() { selected = nil }
}
