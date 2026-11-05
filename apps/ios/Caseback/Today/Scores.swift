import Foundation

// The scores the app speaks in: plain words for what the technical signals add up to. Recovery and sleep are 0 to 100 and each
// sits in a zone with a word; the zones are design choices, not validated thresholds (the bands of recovery are those of
// `readiness.py`). Pure, so the rules are tested.

enum ScoreKind { case recovery, sleep }

enum ScoreZone: Equatable, CaseIterable {
    case low, moderate, high

    /// Recovery: 67 and above high, 33 to 66 moderate (as `readiness.py`). Sleep: 80 and above, 60 to 79 (a design choice:
    /// sleep scores sit higher, so its zones do too).
    static func of(_ score: Int, _ kind: ScoreKind) -> ScoreZone {
        let t = thresholds(kind)
        return score >= t.high ? .high : (score >= t.low ? .moderate : .low)
    }

    static func thresholds(_ kind: ScoreKind) -> (low: Int, high: Int) {
        kind == .recovery ? (33, 67) : (60, 80)
    }

    /// "High", "Moderate", "Low" for recovery; "Good", "Fair", "Poor" for sleep.
    func word(_ kind: ScoreKind) -> String {
        let k = kind == .recovery ? "recovery" : "sleep"
        let z = self == .high ? "high" : (self == .moderate ? "moderate" : "low")
        return L("score.\(k).\(z)")
    }
}

/// The sleep score of `sleep.py` (`sleep_score`), ported: 45 % duration against a need, 25 % efficiency, 15 % deep share and 15 %
/// REM share. A design score, not validated.
enum SleepScore {
    /// How much of its full marks each part earned, 0 to 1.
    struct Parts: Equatable {
        var duration: Double
        var efficiency: Double
        var deep: Double
        var rem: Double

        static let weights = (duration: 0.45, efficiency: 0.25, deep: 0.15, rem: 0.15)

        var score: Int {
            let w = Self.weights
            return Int((100 * (w.duration * duration + w.efficiency * efficiency + w.deep * deep + w.rem * rem)).rounded())
        }
    }

    static func parts(segments: [SleepSegment], needMinutes: Double = 480) -> Parts? {
        guard let first = segments.first, let last = segments.last else { return nil }
        let inBed = Double(last.end - first.start)
        func minutes(_ stage: SleepStage) -> Double {
            Double(segments.filter { $0.stage == stage }.reduce(0) { $0 + $1.end - $1.start })
        }
        let asleep = inBed - minutes(.wake)
        guard inBed > 0, asleep > 0 else { return nil }
        return Parts(
            duration: min(asleep / needMinutes, 1),
            efficiency: min(max((asleep / inBed - 0.6) / 0.3, 0), 1),
            deep: min(minutes(.deep) / asleep / 0.15, 1),
            rem: min(minutes(.rem) / asleep / 0.20, 1))
    }

    static func make(segments: [SleepSegment], needMinutes: Double = 480) -> Int? {
        parts(segments: segments, needMinutes: needMinutes)?.score
    }
}
