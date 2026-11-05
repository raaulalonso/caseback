import SwiftUI
import WidgetKit

@main
struct CasebackApp: App {
    private var previewRequested: Bool {
#if DEBUG && targetEnvironment(simulator)
        let args = ProcessInfo.processInfo.arguments
        let options = ["-caseback-preview", "-onboarding-", "-caseback-sim", "-widget-", "-today-", "-device-", "-trends-", "-detail-", "-tab"]
        return !args.contains("-bench-radio") && args.contains { arg in options.contains { arg.hasPrefix($0) } }
#else
        return false
#endif
    }
    var body: some Scene {
        WindowGroup {
            Group {
                if previewRequested { RootView() }
                else { PilotView(onUnitReady: { _ in
                    WidgetStore.write(WidgetSnapshot(updatedAt: .now, paired: true))
                    WidgetCenter.shared.reloadAllTimelines()
                }) }
            }.preferredColorScheme(.dark)
        }
    }
}
