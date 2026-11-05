import Foundation

// What the conclusions sheet says. Modelled on what WHOOP and Fitbit show under their daily score, cut down to the data a
// disc really has: the signals behind the score against your own median, last night's sleep by stage, and what the day has
// looked like so far. Pure, so the wording rules are tested. Every line is a number and what it is compared with; none gives
// advice (voice rules, README section 3).

/// How today's value sits against the personal median.
enum SignalStatus: Equatable {
    case above, near, below
    /// For resting heart rate, where "above" would read as good news.
    case lower, higher
    case calibrating(night: Int)
    /// A trend with no baseline yet (D13).
    case trend
    case missing

    /// "higher", "lower" or "usual": only which way it went, never whether that is good.
    static func direction(delta: Double, baseline: Double) -> String {
        if abs(delta) <= max(abs(baseline) * 0.05, 0.5) { return L("today.short.usual") }
        return delta > 0 ? L("today.short.higher") : L("today.short.lower")
    }

    var text: String {
        switch self {
        case .above: return L("today.status.above")
        case .near: return L("today.status.near")
        case .below: return L("today.status.below")
        case .lower: return L("today.status.lower")
        case .higher: return L("today.status.higher")
        case .calibrating: return L("today.status.calibrating")
        case .trend: return L("today.status.trend")
        case .missing: return L("today.status.missing")
        }
    }
}

/// One signal behind the score: its value, how it compares, and the line of the last nights it sits on.
struct Signal: Identifiable, Equatable {
    var id: String
    var metric: Metric
    var name: String
    var value: String?
    var status: SignalStatus
    /// Last nights, oldest first; the last one is today's value.
    var series: [Double?] = []
    var baseline: Double?
    /// "−4 bpm · your median 62".
    var detail: String
    var destination: TodayDestination
}

struct StageMinutes: Equatable {
    var stage: SleepStage
    var minutes: Int
}

struct SleepSummary: Equatable {
    var sentence: String
    var stages: [StageMinutes]
    var nights: [Double?]
    var baseline: Double?
}

struct DaySummary: Equatable {
    var heartRate: ClosedRange<Int>?
    var steps: Int?
    var hoursRead: Int
    var hoursElapsed: Int
}

enum TodayInsights {
    /// The headline of the sheet: why readiness is what it is, or why there is none.
    static func headline(_ s: TodaySnapshot) -> String {
        switch s.readiness {
        case .score(let score, let c):
            let zone = ScoreZone.of(score, .recovery).word(.recovery).lowercased()
            return L("today.headline.zone", zone) + " " + ReadinessSentence.make(c)
        case .calibrating(let day): return L("today.calibrating", day)
        case .noData: return L("today.noNight")
        }
    }

    /// One line shown in the peek under the grabber, so the sheet announces its content.
    static func peek(_ s: TodaySnapshot) -> String {
        s.sleep.map(sleepSentence) ?? headline(s)
    }

    // MARK: signals

    /// Within five per cent of the median (at least half a unit) is "near your usual"; the number is always shown next to the word.
    static func status(delta: Double, baseline: Double, inverse: Bool) -> SignalStatus {
        if abs(delta) <= max(abs(baseline) * 0.05, 0.5) { return .near }
        if inverse { return delta < 0 ? .lower : .higher }
        return delta > 0 ? .above : .below
    }

    /// In the order the score weighs them: HRV, resting heart rate, sleep, skin temperature.
    static func signals(_ s: TodaySnapshot) -> [Signal] {
        var out: [Signal] = []
        if let h = s.hrv, let v = h.value, let d = h.deltaValue, let b = h.baseline {
            out.append(Signal(
                id: "hrv", metric: .hrv, name: L("metric.1"), value: "\(v) \(h.unit)",
                status: status(delta: Double(d), baseline: b, inverse: false), series: h.series, baseline: b,
                detail: detail("\(TodayFormat.signed(d)) \(h.unit)", median: "\(Int(b.rounded()))"), destination: .hrv))
        }
        if let r = s.restingHR, let v = r.value, let d = r.deltaValue, let b = r.baseline {
            out.append(Signal(
                id: "rhr", metric: .heartRate, name: L("today.row.rhr"), value: "\(v) \(r.unit)",
                status: status(delta: Double(d), baseline: b, inverse: true), series: r.series, baseline: b,
                detail: detail("\(TodayFormat.signed(d)) \(r.unit)", median: "\(Int(b.rounded()))"), destination: .restingHR))
        }
        if let b = s.sleep, let base = b.baseline {
            let delta = b.minutes - Int(base.rounded())
            out.append(Signal(
                id: "sleep", metric: .sleep, name: L("metric.2"), value: durationText(b.minutes),
                status: status(delta: Double(delta), baseline: base, inverse: false), series: b.nights, baseline: base,
                detail: detail(TodayFormat.sleepDelta(minutes: delta), median: durationText(Int(base.rounded()))),
                destination: .sleep))
        }
        if let t = s.skinTemp {
            if let n = t.calibratingNights {
                out.append(Signal(
                    id: "temp", metric: .skinTemp, name: L("today.tile.temp"), value: nil, status: .calibrating(night: n),
                    detail: L("today.signal.temp.calibrating", n), destination: .skinTemp))
            } else if let v = t.value {
                out.append(Signal(
                    id: "temp", metric: .skinTemp, name: L("today.tile.temp"), value: "\(v) \(t.unit)", status: .trend,
                    series: t.series, detail: L("today.status.trend"), destination: .skinTemp))
            }
        }
        // A signal the score wanted and did not get.
        if case .score(_, let c) = s.readiness {
            for a in ReadinessComponent.allCases where c[a] == nil && !out.contains(where: { $0.metric == a.metric }) {
                out.append(Signal(
                    id: "missing-\(a)", metric: a.metric, name: ReadinessSentence.name(a).capitalizedFirst, value: nil,
                    status: .missing, detail: L("today.signal.missing"), destination: .readiness))
            }
        }
        return out
    }

    private static func detail(_ change: String, median: String) -> String {
        "\(change) · \(L("today.signal.median", median))"
    }

    private static func durationText(_ minutes: Int) -> String {
        let d = TodayFormat.duration(minutes: minutes)
        return d.unit.isEmpty ? d.value : "\(d.value) \(d.unit)"
    }

    // MARK: sleep

    static func sleepSentence(_ b: SleepBlock) -> String {
        let dur = durationText(b.minutes)
        let diff = TodayFormat.sleepDelta(minutes: abs(b.deltaMinutes)).replacingOccurrences(of: "+", with: "")
        let key = b.deltaMinutes > 0 ? "today.insight.sleep.more" : (b.deltaMinutes < 0 ? "today.insight.sleep.less" : "today.insight.sleep.same")
        return b.deltaMinutes == 0 ? L(key, dur) : L(key, dur, diff)
    }

    /// Deep, REM, light and awake minutes of the night, in that order.
    static func sleepSummary(_ s: TodaySnapshot) -> SleepSummary? {
        guard let b = s.sleep else { return nil }
        let order: [SleepStage] = [.deep, .rem, .light, .wake]
        let stages = order.map { st in
            StageMinutes(stage: st, minutes: b.segments.filter { $0.stage == st }.reduce(0) { $0 + $1.end - $1.start })
        }
        return SleepSummary(sentence: sleepSentence(b), stages: stages, nights: b.nights, baseline: b.baseline)
    }

    // MARK: day

    static func daySummary(_ s: TodaySnapshot) -> DaySummary? {
        guard s.tape.nowMinute > 0 else { return nil }
        let ranges = s.tape.hourly
        let lows = ranges.compactMap { $0?.lowerBound }, highs = ranges.compactMap { $0?.upperBound }
        let range: ClosedRange<Int>? = {
            guard let lo = lows.min(), let hi = highs.max() else { return nil }
            return lo...hi
        }()
        let elapsed = max(s.tape.nowMinute / 60, 1)
        return DaySummary(
            heartRate: range, steps: s.steps?.total, hoursRead: ranges.prefix(elapsed).compactMap { $0 }.count,
            hoursElapsed: elapsed)
    }
}

extension String {
    var capitalizedFirst: String { prefix(1).uppercased() + dropFirst() }
}
