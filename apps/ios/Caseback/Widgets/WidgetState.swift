import Foundation

// How old the numbers are and what the widget says about it. A widget that goes stale and looks live is the first complaint about
// every app-fed widget (research 2026-10-03), so age is part of the data, never hidden and never a blank widget.

enum WidgetFreshness: Equatable {
    /// Synced in the last six hours: nothing is said.
    case fresh
    /// Synced earlier today: "hace 9 h".
    case aging(hours: Int)
    /// Synced on a day before today: dimmed, "ayer" or "hace 3 días".
    case stale(days: Int)
    /// More than three days: no numbers, only when it last synced.
    case expired

    static let freshHours = 6
    static let expiredHours = 72

    static func of(updatedAt: Date, now: Date, calendar: Calendar = .current) -> WidgetFreshness {
        let age = max(now.timeIntervalSince(updatedAt), 0)
        if age > Double(expiredHours) * 3600 { return .expired }
        let days = calendar.dateComponents([.day], from: calendar.startOfDay(for: updatedAt), to: calendar.startOfDay(for: now)).day ?? 0
        if days >= 1 { return .stale(days: days) }
        if age < Double(freshHours) * 3600 { return .fresh }
        return .aging(hours: Int(age / 3600))
    }

    /// Numbers are shown dimmed once they are from a previous day.
    var isDim: Bool {
        if case .stale = self { return true }
        return self == .expired
    }

    var showsNumbers: Bool { self != .expired }

    /// The age in words, nil when fresh.
    func text(updatedAt: Date, calendar: Calendar = .current) -> String? {
        switch self {
        case .fresh: return nil
        case .aging(let h): return L("today.age.hour", h)
        case .stale(let d): return d == 1 ? L("widget.age.yesterday") : L("widget.age.days", d)
        case .expired: return L("widget.expired", updatedAt.formatted(.dateTime.weekday(.wide)))
        }
    }

    /// The moments after `updatedAt` at which the picture changes, so the timeline can change it without the app: six hours, the next
    /// midnight (the numbers become yesterday's) and three days.
    static func changeDates(updatedAt: Date, after now: Date, calendar: Calendar = .current) -> [Date] {
        let midnight = calendar.nextDate(after: updatedAt, matching: DateComponents(hour: 0, minute: 0), matchingPolicy: .nextTime)
        let candidates = [
            updatedAt.addingTimeInterval(Double(freshHours) * 3600), midnight,
            updatedAt.addingTimeInterval(Double(expiredHours) * 3600 + 60),
        ].compactMap { $0 }
        return candidates.filter { $0 > now }.sorted()
    }
}

/// What a widget family shows when it cannot show its numbers.
enum WidgetPlaceholder: Equatable {
    /// No disc yet: one prompt, linking to setup.
    case unpaired
    /// Recovery is still building its baseline: "Día 3 de 7".
    case calibrating(day: Int)
    /// A disc, but nothing to show yet.
    case noData
    case expired
}

extension WidgetSnapshot {
    /// The state of a score widget (recovery), before any age is applied.
    func placeholder(for kind: WidgetMetricKind, freshness: WidgetFreshness) -> WidgetPlaceholder? {
        guard paired else { return .unpaired }
        if freshness == .expired { return .expired }
        switch kind {
        case .readiness:
            if recoveryScore != nil { return nil }
            if let d = recoveryCalibratingDay { return .calibrating(day: d) }
            return .noData
        case .sleep: return sleepScore == nil ? .noData : nil
        case .steps: return steps == nil ? .noData : nil
        case .pulse: return pulseBPM == nil ? .noData : nil
        case .restingHR: return restingHR == nil ? .noData : nil
        case .hrv: return hrv == nil ? .noData : nil
        case .skinTemp: return skinTemp == nil ? .noData : nil
        case .spo2: return spo2 == nil ? .noData : nil
        }
    }

    /// The one line a widget may add under its numbers: the alert if there is one (as on Today), otherwise nothing.
    func alertText() -> String? {
        switch alert {
        case .bondLost?: return L("widget.alert.bond")
        case .batteryCritical(let p)?: return L("today.alert.battery", p)
        case nil: return nil
        }
    }
}

// MARK: links

/// Where a tap goes. One link per widget (several are undefined behaviour); the medium widget uses one per column.
enum WidgetLink: Equatable {
    case metric(TodayDestination)
    case today
    case setup

    static let scheme = "caseback"

    var url: URL {
        switch self {
        case .metric(let d): return URL(string: "\(Self.scheme)://metric/\(d.infoKey)")!
        case .today: return URL(string: "\(Self.scheme)://today")!
        case .setup: return URL(string: "\(Self.scheme)://setup")!
        }
    }

    init?(url: URL) {
        guard url.scheme == Self.scheme else { return nil }
        switch url.host {
        case "today": self = .today
        case "setup": self = .setup
        case "metric":
            let key = url.pathComponents.dropFirst().first
            guard let d = TodayDestination.allKnown.first(where: { $0.infoKey == key }) else { return nil }
            self = .metric(d)
        default: return nil
        }
    }
}
