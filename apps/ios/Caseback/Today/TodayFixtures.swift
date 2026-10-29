import Foundation

/// Scenarios for Today, chosen with `-today-state <name>` in the Simulator. **These numbers are invented fixtures** for
/// layout and states: nothing here is a measurement, and the app must never ship them as data (A13). They stand in for
/// the SwiftData store until the history sync exists.
enum TodayScenario: String, CaseIterable {
    case normal, high, low, partial, calibrating, noData, outOfRange, backfilling, bondLost, lowBattery, bluetoothOff, unpaired

    init?(launchValue: String?) {
        guard let v = launchValue else { return nil }
        self.init(rawValue: v)
    }
}

enum TodayFixtures {
    static let nowMinute = 9 * 60 + 41

    static func snapshot(_ scenario: TodayScenario) -> TodaySnapshot {
        var s = TodaySnapshot()
        s.readiness = .score(67, ReadinessComponents(sleep: 1.0, hrv: 1.1, rhr: -0.6, temp: 0))
        s.sleep = sleep(minutes: 432)
        s.restingHR = SeriesBlock(
            value: "58", unit: "bpm", delta: TodayFormat.signed(-4), series: [62, 60, 63, 59, 61, 60, 58], baseline: 62)
        s.hrv = SeriesBlock(
            value: "41", unit: "ms", delta: TodayFormat.signed(6), series: [34, 36, 33, 38, 35, 37, 41], baseline: 35)
        s.tape = tape(until: nowMinute, sleepEnd: 382, arrivedUntil: nil)
        s.pulse = PulseBlock(bpm: 72, ageMinutes: 9, recent: s.tape.recentHeartRate(count: 16))
        s.steps = StepsBlock(total: 4210, bins: [0, 0, 380, 1_950, 1_880, nil, nil, nil])
        s.skinTemp = TrendBlock(value: nil, unit: "°C", series: [], calibratingNights: 3)
        s.spo2 = TrendBlock(value: "96", unit: "%", series: [95, 96, 95, 97, 96, 95, 96], calibratingNights: nil)

        switch scenario {
        case .normal: break
        case .high:
            s.readiness = .score(86, ReadinessComponents(sleep: 1.2, hrv: 1.4, rhr: 1.0, temp: 0))
        case .low:
            s.readiness = .score(24, ReadinessComponents(sleep: -1.1, hrv: -1.3, rhr: -0.9, temp: -0.8))
            s.sleep = sleep(minutes: 331)
        case .partial:
            s.readiness = .score(58, ReadinessComponents(sleep: 0.6, hrv: 0.4, rhr: 0.3, temp: nil))
        case .calibrating:
            s.readiness = .calibrating(day: 3)
        case .noData:
            s.readiness = .noData
            s.sleep = nil
            s.restingHR = SeriesBlock(value: nil, unit: "bpm", delta: nil, series: [], baseline: nil)
            s.hrv = SeriesBlock(value: nil, unit: "ms", delta: nil, series: [], baseline: nil)
        case .outOfRange:
            s.pulse = PulseBlock(bpm: 72, ageMinutes: 3 * 60 + 12, recent: s.pulse?.recent ?? [])
        case .backfilling:
            s.tape = tape(until: nowMinute, sleepEnd: 382, arrivedUntil: 3 * 60)
            s.pulse = PulseBlock(bpm: 72, ageMinutes: 9, recent: s.tape.recentHeartRate(count: 16))
        case .bondLost: s.alert = .bondLost
        case .lowBattery: s.alert = .batteryCritical(4)
        case .bluetoothOff: s.alert = .bluetoothOff
        case .unpaired:
            s = TodaySnapshot()
            s.paired = false
        }
        return s
    }

    // MARK: sleep

    /// A night in stages, scaled to the requested length. Invented.
    static func sleep(minutes: Int) -> SleepBlock {
        let plan: [(SleepStage, Double)] = [
            (.light, 0.06), (.deep, 0.14), (.light, 0.10), (.rem, 0.05), (.light, 0.12), (.deep, 0.08), (.light, 0.06),
            (.wake, 0.02), (.rem, 0.08), (.light, 0.12), (.rem, 0.10), (.wake, 0.01), (.light, 0.06),
        ]
        var t = 0.0
        var segments: [SleepSegment] = []
        for (stage, share) in plan {
            let start = Int((t * Double(minutes)).rounded())
            t += share
            segments.append(SleepSegment(start: start, end: Int((t * Double(minutes)).rounded()), stage: stage))
        }
        if let last = segments.indices.last { segments[last].end = minutes }
        return SleepBlock(
            minutes: minutes, deltaMinutes: minutes - 407, segments: segments, from: "23:10", to: clock(23 * 60 + 10 + minutes),
            nights: [400, 455, 390, 470, 415, 407, Double(minutes)], baseline: 407, score: SleepScore.make(segments: segments))
    }

    private static func clock(_ minute: Int) -> String {
        let m = minute % 1440
        return String(format: "%02d:%02d", m / 60, m % 60)
    }

    // MARK: tape

    /// A deterministic day: continuous heart rate while asleep, bursts by day with holes where the wrist was moving.
    static func tape(until now: Int, sleepEnd: Int, arrivedUntil: Int?) -> DayTape {
        var columns: [TapeColumn] = []
        for i in 0..<96 {
            let minute = i * 15
            guard minute < now else { columns.append(TapeColumn()); continue }
            if let a = arrivedUntil, minute >= a { columns.append(TapeColumn()); continue }
            let h = hash(i)
            if minute < sleepEnd {
                let base = 50 + Int(h % 6)
                columns.append(TapeColumn(hrMin: base - 3, hrMax: base + 5 + Int((h / 7) % 4)))
            } else if h % 5 == 0 {
                columns.append(TapeColumn())  // a hole: moving too much to read
            } else {
                let base = 62 + Int(h % 14) + (minute > 8 * 60 ? 8 : 0)
                columns.append(TapeColumn(hrMin: base, hrMax: base + 6 + Int((h / 5) % 22)))
            }
        }
        return DayTape(columns: columns, sleep: sleepEnd > 0 ? [0..<sleepEnd] : [], nowMinute: now)
    }

    private static func hash(_ i: Int) -> UInt64 {
        var x = UInt64(i) &* 0x9E37_79B9_7F4A_7C15
        x ^= x >> 29
        x = x &* 0xBF58_476D_1CE4_E5B9
        return x >> 8
    }
}
