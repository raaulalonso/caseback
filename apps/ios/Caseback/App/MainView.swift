import SwiftUI

enum AppTab: CaseIterable {
    case today, trends, device

    var title: String {
        switch self {
        case .today: return L("tab.today")
        case .trends: return L("tab.trends")
        case .device: return L("tab.device")
        }
    }
}

/// Three tabs, text only (02 section 5): the label is the interface.
struct MainView: View {
    let today: TodayModel
    let trends: TrendsModel
    let device: DeviceModel
    var onSetup: () -> Void
    @State private var tab: AppTab = LaunchOptions.tab
    @State private var drawer = DrawerController()

    var body: some View {
        ZStack {
            ZStack {
                switch tab {
                case .today:
                    TodayScreen(model: today, drawer: drawer, onAlert: { tab = .device }, onSetup: onSetup)
                        .transition(.opacity.combined(with: .scale(scale: 0.97)))
                case .trends:
                    TrendsScreen(model: trends, onOpen: today.open)
                        .transition(.opacity.combined(with: .scale(scale: 0.97)))
                case .device:
                    DeviceScreen(model: device, onSetup: onSetup)
                        .transition(.opacity.combined(with: .scale(scale: 0.97)))
                }
            }
            // While a metric screen is open (or being dragged away) what is under it steps back a little and comes forward again.
            .scaleEffect(1 - 0.05 * today.coverage)
            .opacity(1 - 0.55 * today.coverage)
            .safeAreaInset(edge: .bottom, spacing: 0) { TextTabBar(selection: $tab) }
            TodayDetailOverlay(model: today, trends: trends)
        }
        // A tap on a widget: the metric's screen, Today, or setup when there is no disc.
        .onOpenURL { url in
            guard let link = WidgetLink(url: url) else { return }
            switch link {
            case .today: tab = .today
            case .setup: onSetup()
            case .metric(let d):
                tab = .today
                DispatchQueue.main.async { today.open(d, from: CGRect(x: 20, y: 150, width: 353, height: 260)) }
            }
        }
    }
}

/// The bar's press: the label sinks a little under the finger and springs back.
private struct TabPress: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.9 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.6), value: configuration.isPressed)
    }
}

struct TextTabBar: View {
    @Binding var selection: AppTab
    @Namespace private var indicator
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 0) {
            ForEach(AppTab.allCases, id: \.self) { tab in
                let selected = tab == selection
                Button {
                    guard !selected else { return }
                    Haptics.tick()
                    withAnimation(reduceMotion ? nil : .spring(response: 0.42, dampingFraction: 0.72)) { selection = tab }
                } label: {
                    VStack(spacing: 0) {
                        // The line under the selected label slides to the next one and stretches on the way.
                        ZStack {
                            Color.clear.frame(height: 3)
                            if selected {
                                Capsule(style: .continuous).fill(Palette.text1).frame(height: 3)
                                    .matchedGeometryEffect(id: "indicator", in: indicator)
                            }
                        }
                        Text(tab.title)
                            .font(.mono(.medium, 13, relativeTo: .footnote))
                            .foregroundStyle(selected ? Palette.text1 : Palette.text3)
                            .scaleEffect(selected ? 1.08 : 1)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                            .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                            .frame(maxWidth: .infinity, minHeight: 46)
                            .animation(.spring(response: 0.35, dampingFraction: 0.7), value: selected)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(TabPress())
                .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
            }
        }
        .background(Palette.ground)
        .overlay(alignment: .top) { Rectangle().fill(Palette.hairline).frame(height: 1 / UIScreen.main.scale) }
    }
}
