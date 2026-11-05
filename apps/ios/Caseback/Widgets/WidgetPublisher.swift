import WidgetKit

/// The app's side: after every sync (and at launch) it stores what Today shows and asks the widgets to draw it again. Reloading from
/// the app is free of the widget's daily budget while the app is in the foreground.
enum WidgetPublisher {
    static func publish(_ today: TodaySnapshot, syncedAt: Date) {
        WidgetStore.write(.make(from: today, syncedAt: syncedAt))
        WidgetCenter.shared.reloadAllTimelines()
    }
}
