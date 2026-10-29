import Foundation

/// Scenarios for Trends, chosen with `-trends-state <name>`. **These numbers are invented fixtures** for layout and states: they
/// are generated from a fixed seed, nothing here is a measurement and the app must never ship them as data (A13).
enum TrendsScenario: String, CaseIterable {
    /// 90 nights; skin temperature still calibrating, like Today's fixtures.
    case normal
    /// As normal, with skin temperature calibrated.
    case full
    /// Five nights only.
    case young
    /// Fewer than three nights: nothing to draw yet.
    case empty

    init?(launchValue: String?) {
        guard let v = launchValue else { return nil }
        self.init(rawValue: v)
    }
}

enum TrendsFixtures {
    /// A small deterministic generator, so screenshots and tests are repeatable.
    private struct Seeded {
        var state: UInt64
        mutating func next() -> Double {
            state = state &* 6364136223846793005 &+ 1442695040888963407
            return Double(state >> 33) / Double(1 << 31)
        }
        /// Roughly bell shaped, in -1...1.
        mutating func noise() -> Double { (next() + next() + next()) / 1.5 - 1 }
    }

    static func snapshot(_ scenario: TrendsScenario, today: Date = Calendar.current.startOfDay(for: .now)) -> TrendsSnapshot {
        let n: Int
        switch scenario {
        case .normal, .full: n = 90
        case .young: n = 5
        case .empty: n = 2
        }
        var rng = Seeded(state: 20260930)
        func make(_ base: Double, drift: Double = 0, spread: Double, weekly: Double = 0, gaps: Set<Int> = [], digits: Int = 0) -> [Double?] {
            // A slow wander (each day remembers the last) plus a little day-to-day noise: real series are smooth, not sawtooth.
            var slow = 0.0
            return (0..<n).map { i in
                // `i` counts from the oldest; day 0 of the week pattern is arbitrary.
                let dayFromEnd = n - 1 - i
                slow = 0.88 * slow + 0.5 * spread * rng.noise()
                let jitter = 0.25 * spread * rng.noise()
                if gaps.contains(dayFromEnd) { return nil }
                let v = base + drift * Double(i) / Double(max(n - 1, 1)) + slow + jitter + weekly * sin(Double(i) * 2 * .pi / 7)
                let f = pow(10, Double(digits))
                return (v * f).rounded() / f
            }
        }
        func pin(_ values: [Double?], last: Double) -> [Double?] { Array(values.dropLast()) + [last] }

        var series: [TrendMetric: TrendSeries] = [:]
        // The last value of each is Today's own fixture (TodayFixtures) so the two screens agree.
        series[.readiness] = TrendSeries(values: pin(make(64, drift: 3, spread: 12, weekly: 3, gaps: [40, 41]), last: 67))
        let todaysSleepScore = Double(TodayFixtures.sleep(minutes: 432).score ?? 80)
        series[.sleepScore] = TrendSeries(
            values: pin(make(78, spread: 9, weekly: 3, gaps: [12]).map { $0.map { min(max($0, 20), 99) } }, last: todaysSleepScore))
        series[.sleep] = TrendSeries(values: pin(make(415, spread: 38, weekly: 18, gaps: [12]), last: 432))
        series[.restingHR] = TrendSeries(values: pin(make(62, drift: -3.5, spread: 3.2, gaps: [30], digits: 1), last: 58))
        series[.hrv] = TrendSeries(values: pin(make(35, drift: 5, spread: 6, gaps: [20, 21, 22], digits: 1), last: 41))
        series[.steps] = TrendSeries(values: pin(make(7600, spread: 2600, weekly: 900), last: 4210), calibratingNights: nil, lastIsPartial: true)
        series[.spo2] = TrendSeries(values: pin(make(96, spread: 1.0, gaps: [8, 9, 55]), last: 96))
        if scenario == .normal || scenario == .young {
            series[.skinTemp] = TrendSeries(values: [], calibratingNights: 3)
        } else {
            series[.skinTemp] = TrendSeries(values: pin(make(0, spread: 0.35, digits: 1), last: 0.2))
        }
        return TrendsSnapshot(series: series, nights: n, endDate: today)
    }
}
