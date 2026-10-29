import Foundation

// What the widgets know. The app writes one small snapshot after every sync into a store shared with the widget extension; the widgets
// only read it. Nothing here touches Bluetooth, HealthKit or the network (the design notes). Everything is stored as
// numbers and codes, never as sentences, so the widget can say it in the language of the moment.

/// The eight metrics a small widget can show, in the order of the picker.
enum WidgetMetricKind: String, Codable, CaseIterable, Identifiable {
    case readiness, sleep, steps, pulse, restingHR, hrv, skinTemp, spo2

    var id: String { rawValue }

    var metric: Metric {
        switch self {
        case .readiness: return .readiness
        case .sleep: return .sleep
        case .steps: return .steps
        case .pulse, .restingHR: return .heartRate
        case .hrv: return .hrv
        case .skinTemp: return .skinTemp
        case .spo2: return .spo2
        }
    }

    var destination: TodayDestination {
        switch self {
        case .readiness: return .readiness
        case .sleep: return .sleep
        case .steps: return .steps
        case .pulse: return .pulse
        case .restingHR: return .restingHR
        case .hrv: return .hrv
        case .skinTemp: return .skinTemp
        case .spo2: return .spo2
        }
    }

    var name: String {
        switch self {
        case .readiness: return L("metric.3")
        case .sleep: return L("metric.2")
        case .steps: return L("trends.movement")
        case .pulse: return L("metric.0")
        case .restingHR: return L("today.row.rhr")
        case .hrv: return L("metric.1")
        case .skinTemp: return L("today.tile.temp")
        case .spo2: return L("metric.5")
        }
    }

    /// SpO2 and skin temperature are trends only (D13): dashed, and named so.
    var trendOnly: Bool { self == .skinTemp || self == .spo2 }
}

/// The only thing that ever interrupts a widget, as on Today: something is wrong and the owner has to act.
enum WidgetAlert: Codable, Equatable {
    case bondLost
    case batteryCritical(Int)
}

/// A signal with a median to compare against: resting heart rate, HRV.
struct WidgetSignal: Codable, Equatable {
    var value: Int
    /// Today against your 30-day median, in whole units.
    var delta: Int
    /// Seven nights, oldest first.
    var series: [Double?]
    var baseline: Double?
}

/// A trend-only reading (D13).
struct WidgetTrend: Codable, Equatable {
    var value: String?
    var series: [Double?]
    /// Nights recorded so far while there are fewer than five.
    var calibratingNights: Int?
}

struct WidgetSnapshot: Codable, Equatable {
    /// When the disc was last synced: the moment the numbers are as fresh as.
    var updatedAt: Date
    var paired = true
    var alert: WidgetAlert?
    /// "Sleep and HRV above your usual." in the language of the app when it wrote this; nil without a score.
    var headline: String?

    var recoveryScore: Int?
    /// Day 1 to 6 while recovery builds its baseline; nil once calibrated.
    var recoveryCalibratingDay: Int?
    var sleepScore: Int?
    var sleepMinutes: Int?
    var sleepDelta: Int?
    var steps: Int?
    var stepBins: [Int?] = []
    var pulseBPM: Int?
    /// Minutes between that reading and `updatedAt`.
    var pulseAgeMinutes: Int?
    var pulseRecent: [Double?] = []
    var restingHR: WidgetSignal?
    var hrv: WidgetSignal?
    var skinTemp: WidgetTrend?
    var spo2: WidgetTrend?

    /// True when there is a disc and at least one number to show.
    var hasAnyData: Bool {
        recoveryScore != nil || sleepScore != nil || steps != nil || pulseBPM != nil || restingHR != nil || hrv != nil
    }
}

// MARK: from Today

extension WidgetSnapshot {
    /// The snapshot of what Today shows, ready to be stored.
    static func make(from s: TodaySnapshot, syncedAt: Date) -> WidgetSnapshot {
        var w = WidgetSnapshot(updatedAt: syncedAt, paired: s.paired)
        switch s.alert {
        case .bondLost?: w.alert = .bondLost
        case .batteryCritical(let p)?: w.alert = .batteryCritical(p)
        case .bluetoothOff?, nil: break  // a phone-side state the widget cannot know about and the owner already sees
        }
        switch s.readiness {
        case .score(let v, _):
            w.recoveryScore = v
            w.headline = TodayInsights.headline(s)
        case .calibrating(let day): w.recoveryCalibratingDay = day
        case .noData: break
        }
        if let b = s.sleep {
            w.sleepScore = b.score
            w.sleepMinutes = b.minutes
            w.sleepDelta = b.deltaMinutes
        }
        if let st = s.steps {
            w.steps = st.total
            w.stepBins = st.bins
        }
        if let p = s.pulse {
            w.pulseBPM = p.bpm
            w.pulseAgeMinutes = p.ageMinutes
            w.pulseRecent = p.recent
        }
        func signal(_ b: SeriesBlock?) -> WidgetSignal? {
            guard let b, let v = b.value.flatMap({ Int($0) }) else { return nil }
            return WidgetSignal(value: v, delta: b.deltaValue ?? 0, series: b.series, baseline: b.baseline)
        }
        w.restingHR = signal(s.restingHR)
        w.hrv = signal(s.hrv)
        func trend(_ t: TrendBlock?) -> WidgetTrend? {
            guard let t else { return nil }
            return WidgetTrend(value: t.value, series: t.series, calibratingNights: t.calibratingNights)
        }
        w.skinTemp = trend(s.skinTemp)
        w.spo2 = trend(s.spo2)
        return w
    }
}
