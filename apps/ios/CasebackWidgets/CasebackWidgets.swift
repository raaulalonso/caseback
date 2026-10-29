import AppIntents
import SwiftUI
import WidgetKit

// The widget extension. One kind, "Hoy", in five families (the design notes): a small one for any metric, a medium one
// with the three scores, and the three Lock Screen accessories. It only reads the snapshot the app stored.

/// The metric a small widget (and the circular Lock Screen one) shows, chosen when it is added.
enum WidgetMetricOption: String, AppEnum {
    case readiness, sleep, steps, pulse, restingHR, hrv, skinTemp, spo2

    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "widget.config.metric")

    static var caseDisplayRepresentations: [WidgetMetricOption: DisplayRepresentation] = [
        .readiness: DisplayRepresentation(title: "metric.3"),
        .sleep: DisplayRepresentation(title: "metric.2"),
        .steps: DisplayRepresentation(title: "trends.movement"),
        .pulse: DisplayRepresentation(title: "metric.0"),
        .restingHR: DisplayRepresentation(title: "today.row.rhr"),
        .hrv: DisplayRepresentation(title: "metric.1"),
        .skinTemp: DisplayRepresentation(title: "today.tile.temp"),
        .spo2: DisplayRepresentation(title: "metric.5"),
    ]

    var kind: WidgetMetricKind { WidgetMetricKind(rawValue: rawValue) ?? .readiness }
}

struct MetricIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "widget.config.metric"
    static var description = IntentDescription("widget.config.desc")

    @Parameter(title: "widget.config.metric", default: .readiness)
    var metric: WidgetMetricOption
}

struct TodayEntry: TimelineEntry {
    var date: Date
    var snapshot: WidgetSnapshot
    var kind: WidgetMetricKind
}

struct TodayProvider: AppIntentTimelineProvider {
    /// What the widget gallery shows before the first real snapshot: invented numbers (the same fixtures as the app in the Simulator).
    private static func sample(_ now: Date) -> WidgetSnapshot {
        .make(from: TodayFixtures.snapshot(.normal), syncedAt: now.addingTimeInterval(-12 * 60))
    }

    /// Nothing stored yet (the app has not run): the widget asks to open the app.
    private static func current(_ now: Date) -> WidgetSnapshot {
        if let s = WidgetStore.read() { return s }
        #if DEBUG
            return sample(now)
        #else
            return WidgetSnapshot(updatedAt: now, paired: false)
        #endif
    }

    func placeholder(in context: Context) -> TodayEntry {
        TodayEntry(date: .now, snapshot: Self.sample(.now), kind: .readiness)
    }

    func snapshot(for configuration: MetricIntent, in context: Context) async -> TodayEntry {
        let now = Date()
        return TodayEntry(date: now, snapshot: context.isPreview ? Self.sample(now) : Self.current(now), kind: configuration.metric.kind)
    }

    func timeline(for configuration: MetricIntent, in context: Context) async -> Timeline<TodayEntry> {
        let now = Date()
        let s = Self.current(now)
        let kind = configuration.metric.kind
        // One entry now and one at each moment the picture changes (six hours, midnight, three days), so the age text and the dimming
        // follow the clock without asking the system for more reloads.
        let dates = [now] + WidgetFreshness.changeDates(updatedAt: s.updatedAt, after: now)
        let entries = dates.map { TodayEntry(date: $0, snapshot: s, kind: kind) }
        return Timeline(entries: entries, policy: .after(now.addingTimeInterval(6 * 3600)))
    }
}

struct TodayWidgetEntryView: View {
    @Environment(\.widgetFamily) private var family
    var entry: TodayEntry

    var body: some View {
        let s = entry.snapshot
        Group {
            switch family {
            case .systemMedium:
                MediumWidgetView(snapshot: s, now: entry.date)
            case .accessoryCircular:
                CircularWidgetView(snapshot: s, kind: entry.kind, now: entry.date).widgetURL(link(.metric(entry.kind.destination)))
            case .accessoryRectangular:
                RectangularWidgetView(snapshot: s, now: entry.date).widgetURL(link(.metric(.readiness)))
            case .accessoryInline:
                InlineWidgetView(snapshot: s, now: entry.date).widgetURL(link(.today))
            default:
                SmallWidgetView(snapshot: s, kind: entry.kind, now: entry.date).widgetURL(link(.metric(entry.kind.destination)))
            }
        }
        .containerBackground(for: .widget) { isAccessory ? Color.clear : Palette.ground }
    }

    private var isAccessory: Bool {
        family == .accessoryCircular || family == .accessoryRectangular || family == .accessoryInline
    }

    /// Without a disc every tap goes to setup.
    private func link(_ l: WidgetLink) -> URL { entry.snapshot.paired ? l.url : WidgetLink.setup.url }
}

struct TodayWidget: Widget {
    let kind = "io.caseback.widget.today"

    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: kind, intent: MetricIntent.self, provider: TodayProvider()) { entry in
            TodayWidgetEntryView(entry: entry)
        }
        .configurationDisplayName(L("widget.name"))
        .description(L("widget.desc"))
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

@main
struct CasebackWidgetBundle: WidgetBundle {
    var body: some Widget { TodayWidget() }
}
