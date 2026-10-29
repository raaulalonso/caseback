import SwiftUI

/// The conclusions sheet. Closed, only its top shows above the tab bar: a grabber that nudges now and then and the first
/// conclusion in one line, so it is clear something lives below. Pulled up (see `DrawerController`) it
/// rises over the panel, which sinks and dims behind it.
struct InsightsDrawer: View {
    let controller: DrawerController
    let snapshot: TodaySnapshot
    var height: CGFloat
    var peekHeight: CGFloat
    var topInset: CGFloat
    var onOpen: (TodayDestination, CGRect) -> Void

    @State private var play = false
    @State private var nudge = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let p = controller.progress
        let content = smooth((p - 0.25) / 0.6)
        ZStack(alignment: .top) {
            UnevenRoundedRectangle(topLeadingRadius: Radius.hero, topTrailingRadius: Radius.hero, style: .continuous)
                .fill(Palette.tile)
            VStack(spacing: 0) {
                grabber
                ZStack(alignment: .top) {
                    peek.opacity(1 - smooth(p / 0.35))
                    sheet.opacity(content).allowsHitTesting(p > 0.9)
                }
            }
        }
        .frame(height: max(height - topInset, 1))
        .offset(y: (height - peekHeight) * (1 - p) + topInset * p)
        .onAppear {
            startHint()
            // Coming back to Today (the screen is rebuilt on a tab change) with the sheet still open: play its content again,
            // or it would show empty.
            if controller.isOpen { replay() }
        }
        .onChange(of: controller.isOpen) { _, open in if open { play = false; replay() } else { play = false } }
        .accessibilityElement(children: .contain)
    }

    private func smooth(_ x: CGFloat) -> CGFloat { let t = min(max(x, 0), 1); return t * t * (3 - 2 * t) }

    // MARK: closed

    private var grabber: some View {
        Button {
            controller.isOpen ? controller.close() : controller.open()
        } label: {
            // The handle lifts and settles every few seconds, the way a drawer handle invites a pull.
            Capsule(style: .continuous)
                .fill(Palette.text2)
                .frame(width: 48, height: 6)
                .offset(y: nudge ? -4 : 0)
                .frame(maxWidth: .infinity, minHeight: 28)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(controller.isOpen ? L("today.drawer.close") : L("today.drawer.open"))
        .accessibilityIdentifier("drawer.grabber")
    }

    private var peek: some View {
        HStack(spacing: Space.s12) {
            Text(TodayInsights.peek(snapshot))
                .font(.system(size: 15, weight: .regular))
                .foregroundStyle(Palette.text1)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, Space.margin)
        .frame(height: peekHeight - 28, alignment: .top)
        .padding(.top, 2)
        .contentShape(Rectangle())
        .onTapGesture { if !controller.isOpen { controller.open() } }
        .accessibilityHidden(true)
    }

    private func startHint() {
        guard !reduceMotion else { return }
        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(1800))
            while !Task.isCancelled {
                if !controller.isOpen, !controller.isDragging {
                    withAnimation(.spring(response: 0.32, dampingFraction: 0.45)) { nudge = true }
                    try? await Task.sleep(for: .milliseconds(260))
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.6)) { nudge = false }
                }
                try? await Task.sleep(for: .milliseconds(4200))
            }
        }
    }

    // MARK: open

    private func replay() {
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) { play = false }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { play = true }
    }

    private var sheet: some View {
        let signals = TodayInsights.signals(snapshot)
        let sleep = TodayInsights.sleepSummary(snapshot)
        let day = TodayInsights.daySummary(snapshot)
        return ScrollView {
            VStack(alignment: .leading, spacing: Space.s32) {
                VStack(alignment: .leading, spacing: Space.s12) {
                    Text(Date.now, format: .dateTime.weekday(.wide).day().month(.wide))
                        .font(.monoFixed(.regular, 13)).foregroundStyle(Palette.text3)
                    Text(TodayInsights.headline(snapshot))
                        .font(.system(size: 26, weight: .medium))
                        .foregroundStyle(Palette.text1)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.top, Space.s4)
                .modifier(RiseIn(play: play, index: 0))
                if !signals.isEmpty {
                    SheetSection(title: L("today.group.signals")) {
                        ForEach(Array(signals.enumerated()), id: \.element.id) { i, s in
                            SignalRow(signal: s, play: play, delay: 0.15 + Double(i) * 0.07, onOpen: onOpen)
                        }
                    }
                    .modifier(RiseIn(play: play, index: 1))
                }
                if let sleep {
                    SheetSection(title: L("today.lastNight")) {
                        SleepSection(summary: sleep, play: play, onOpen: onOpen)
                    }
                    .modifier(RiseIn(play: play, index: 2))
                }
                if let day {
                    SheetSection(title: L("today.group.day")) {
                        DaySection(summary: day, play: play, onOpen: onOpen)
                    }
                    .modifier(RiseIn(play: play, index: 3))
                }
                Text(L("today.drawer.footer"))
                    .font(.system(size: 12)).foregroundStyle(Palette.text3)
                    .fixedSize(horizontal: false, vertical: true)
                    .modifier(RiseIn(play: play, index: 4))
                Color.clear.frame(height: Space.s24)
            }
            .padding(.horizontal, Space.margin)
            // Where the content sits inside the scroll view: 0 at the top, negative once scrolled.
            .onGeometryChange(for: CGFloat.self) { $0.frame(in: .named("drawerScroll")).minY } action: { y in
                controller.scrollOffset = y
                controller.scrollAtTop = y >= -1
            }
        }
        .coordinateSpace(name: "drawerScroll")
        .scrollIndicators(.hidden)
        .scrollDisabled(controller.isDragging)
        .accessibilityIdentifier("drawer.sheet")
    }
}

/// Fades and rises into place, one after another.
private struct RiseIn: ViewModifier {
    var play: Bool
    var index: Int

    func body(content: Content) -> some View {
        content
            .opacity(play ? 1 : 0)
            .offset(y: play ? 0 : 22)
            .motion(.spring(response: 0.55, dampingFraction: 0.8).delay(0.06 * Double(index)), value: play)
    }
}
