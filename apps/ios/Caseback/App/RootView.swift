import CasebackProtocol
import SwiftUI

/// Debug launch arguments (Simulator and screenshots only):
///   -onboarding-reset YES   forget that onboarding finished
///   -onboarding-step N      start at step N (0 welcome ... 6 done)
///   -caseback-sim <scenario>   happy, noDisc, twoDiscs, bondMismatch, newerApp, weakContact
///   -caseback-fast YES         instant timings
///   -onboarding-done YES    skip onboarding (opens Today)
///   -today-page N           0 now, 1 last night
///   -tab trends|device      open that tab
///   -trends-state <name>    normal, full, young, empty (invented fixtures, see TrendsFixtures)
///   -trends-metric <name>   readiness, sleepScore, steps, sleep, restingHR, hrv, skinTemp, spo2
///   -trends-range N         7, 30 or 90
///   -device-state <name>    connected, charging, lowBattery, syncing, outOfRange, bluetoothOff, bondLost, updateAvailable,
///                           updateLowBattery, updating, updateFailing, patchyContact, unpaired (invented, see DeviceFixtures)
///   -device-sheet <name>    open that sheet: mode, update, health, data, experimental, forget, about
///   -device-autostart YES   start the (simulated) firmware update when the update sheet opens
///   -today-open <name>      open that metric's screen: readiness, sleep, steps, restingHR, hrv, pulse, skinTemp, spo2, day
///   -detail-scroll <name>   scroll that screen to its section a, b or affects (screenshots)
///   -detail-info YES        open the "i" of the metric screen (screenshots)
///   -widget-gallery <name>  show the widgets at their real size instead of the app: YES for all, or small, states, medium, lock (screenshots)
///   -widget-age-hours N     store what the widgets show as if the disc had last synced N hours ago (screenshots of the widgets on a Home Screen)
///   -today-state <name>     normal, high, low, partial, calibrating, noData, outOfRange, backfilling, bondLost,
///                           lowBattery, bluetoothOff, unpaired (invented fixtures, see TodayFixtures)
/// Debug arguments that open something (a sheet, a screen) act once per launch. The screens are rebuilt every time you come back
/// to their tab, so reading the argument there would bring the sheet back each time.
enum LaunchOnce {
    private static var taken: Set<String> = []
    static func take(_ key: String) -> String? {
        guard !taken.contains(key), let v = UserDefaults.standard.string(forKey: key) else { return nil }
        taken.insert(key)
        return v
    }
}

enum LaunchOptions {
    static var reset: Bool { UserDefaults.standard.bool(forKey: "onboarding-reset") }
    static var step: OnboardingStep? {
        guard UserDefaults.standard.object(forKey: "onboarding-step") != nil else { return nil }
        return OnboardingStep(rawValue: UserDefaults.standard.integer(forKey: "onboarding-step"))
    }
    static var fast: Bool { UserDefaults.standard.bool(forKey: "caseback-fast") }
    static var todayPage: Int { UserDefaults.standard.integer(forKey: "today-page") }
    static var skipOnboarding: Bool { UserDefaults.standard.bool(forKey: "onboarding-done") }
    static var tab: AppTab {
        switch UserDefaults.standard.string(forKey: "tab") {
        case "trends": return .trends
        case "device": return .device
        default: return .today
        }
    }
    static var trendsScenario: TrendsScenario { TrendsScenario(launchValue: UserDefaults.standard.string(forKey: "trends-state")) ?? .normal }
    static var trendsMetric: TrendMetric {
        let name = UserDefaults.standard.string(forKey: "trends-metric")
        return TrendMetric.allCases.first { String(describing: $0) == name } ?? .readiness
    }
    static var trendsRange: TrendRange { TrendRange(rawValue: UserDefaults.standard.integer(forKey: "trends-range")) ?? .month }
    static var widgetGallery: String? { UserDefaults.standard.string(forKey: "widget-gallery") }
    static var widgetAgeHours: Double? { UserDefaults.standard.string(forKey: "widget-age-hours").flatMap(Double.init) }
    static var deviceSheet: DeviceSheet? { UserDefaults.standard.string(forKey: "device-sheet").flatMap(DeviceSheet.init(rawValue:)) }
    static var deviceScenario: DeviceScenario { DeviceScenario(launchValue: UserDefaults.standard.string(forKey: "device-state")) ?? .connected }
    static var todayScenario: TodayScenario { TodayScenario(launchValue: UserDefaults.standard.string(forKey: "today-state")) ?? .normal }
}

struct RootView: View {
    @State private var store = OnboardingStore()
    @State private var showOnboarding: Bool
    @State private var trends = TrendsModel(
        snapshot: TrendsFixtures.snapshot(LaunchOptions.trendsScenario), range: LaunchOptions.trendsRange, metric: LaunchOptions.trendsMetric)
    @State private var device = DeviceModel(
        snapshot: DeviceFixtures.snapshot(LaunchOptions.deviceScenario),
        failTransfer: LaunchOptions.deviceScenario == .updateFailing, fast: LaunchOptions.fast,
        sheet: LaunchOptions.tab == .device ? LaunchOptions.deviceSheet : nil,
        autoStart: UserDefaults.standard.bool(forKey: "device-autostart"))
    @State private var today = TodayModel(snapshot: TodayFixtures.snapshot(LaunchOptions.todayScenario), page: LaunchOptions.todayPage)

    init() {
        let store = OnboardingStore()
        if LaunchOptions.reset { store.reset() }
        if LaunchOptions.skipOnboarding { store.markCompleted(disc: nil) }
        _showOnboarding = State(initialValue: !store.isCompleted)
    }

    var body: some View {
        ZStack {
            Palette.ground.ignoresSafeArea()
            if let section = LaunchOptions.widgetGallery {
                WidgetGallery(only: section.lowercased() == "yes" ? "all" : section)
            } else if showOnboarding {
                OnboardingView(model: makeModel()) {
                    withAnimation(Motion.standard(0.5)) { showOnboarding = false }
                }
                .transition(.opacity)
            } else {
                MainView(today: today, trends: trends, device: device, onSetup: { store.reset(); withAnimation(Motion.standard(0.5)) { showOnboarding = true } })
                    .transition(.opacity)
            }
        }
        // Until there is a real source, the widgets show what Today shows: invented numbers, as if the disc had synced 12 minutes ago.
        .task { WidgetPublisher.publish(today.snapshot, syncedAt: Date().addingTimeInterval(-(LaunchOptions.widgetAgeHours ?? 0.2) * 3600)) }
    }

    @MainActor
    private func makeModel() -> OnboardingModel {
        let fast = LaunchOptions.fast
        let setup = SimulatedDiscSetup(timing: fast ? .instant : .realistic)
        // The disc is simulated until the CoreBluetooth transport exists; the permissions are the real ones.
        return OnboardingModel(
            setup: setup, bluetooth: CoreBluetoothPermission(), health: AppleHealthPermission(),
            store: store, timing: fast ? .instant : .realistic, startAt: LaunchOptions.step ?? .welcome)
    }
}
