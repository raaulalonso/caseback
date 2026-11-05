import SwiftUI

/// The fixed panel: a header with two pages you can swipe between, and the blocks of the page, sized to the screen.
struct TodayPanel: View {
    @Bindable var model: TodayModel
    var onAlert: () -> Void
    var onSetup: () -> Void
    @State private var play: [Bool] = [false, false]
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// Space between the two columns of a row, and the side margin: the panel uses nearly the whole width.
    private static let gap: CGFloat = 20
    private static let side: CGFloat = 16

    var body: some View {
        let s = model.snapshot
        VStack(spacing: 0) {
            if s.paired {
                header.padding(.horizontal, Self.side).padding(.top, Space.s8).padding(.bottom, Space.s12)
                if let alert = s.alert { alertBar(alert) }
                GeometryReader { g in
                    TabView(selection: $model.page) {
                        page(now: true, size: g.size, s).tag(0)
                        page(now: false, size: g.size, s).tag(1)
                    }
                    .tabViewStyle(.page(indexDisplayMode: .never))
                    .ignoresSafeArea(edges: .bottom)
                }
            } else {
                unpaired
            }
        }
        .task { replay(model.page) }
        .onChange(of: model.page) { old, p in
            Haptics.tick()
            // The page that was left is wiped without animation, so its charts draw again on the next visit.
            var t = Transaction()
            t.disablesAnimations = true
            withTransaction(t) { play[old] = false }
            replay(p)
        }
    }

    // MARK: header

    /// The name of the page, small, and two dots that say there are two pages.
    private var header: some View {
        HStack(spacing: Space.s12) {
            Text(model.page == 0 ? L("today.page.now") : L("today.lastNight"))
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(Palette.text2)
                .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                .id(model.page)
                .transition(.opacity.combined(with: .offset(y: 5)))
                .accessibilityAddTraits(.isHeader)
            Spacer(minLength: 0)
            HStack(spacing: 2) { dot(0); dot(1) }
        }
        .frame(height: 28)
        .animation(.easeOut(duration: 0.25), value: model.page)
    }

    private func dot(_ page: Int) -> some View {
        let active = model.page == page
        return Button {
            withAnimation(.spring(response: 0.45, dampingFraction: 0.85)) { model.page = page }
        } label: {
            Capsule(style: .continuous)
                .fill(active ? Palette.text1 : Palette.text3)
                .frame(width: active ? 20 : 7, height: 7)
                .animation(.spring(response: 0.4, dampingFraction: 0.8), value: active)
                .frame(width: active ? 28 : 15, height: 28)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(page == 0 ? L("today.page.now") : L("today.lastNight"))
        .accessibilityAddTraits(active ? [.isSelected] : [])
    }

    // MARK: alert

    /// The only extra line that ever appears: something is wrong and needs the owner.
    private func alertBar(_ alert: TodayAlert) -> some View {
        Button(action: onAlert) {
            Text("! " + alert.text)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(Palette.alert)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
                .frame(maxWidth: .infinity, minHeight: 40)
                .background(Capsule(style: .continuous).strokeBorder(Palette.alert, lineWidth: 2))
        }
        .buttonStyle(TilePress())
        .padding(.horizontal, Space.margin)
        .padding(.bottom, Space.s8)
    }

    // MARK: pages

    private func page(now: Bool, size: CGSize, _ s: TodaySnapshot) -> some View {
        let i = now ? 0 : 1  // page index
        let usable = max(size.height - Space.s8, 100)
        let weights: [CGFloat] = now ? [0.43, 0.30, 0.27] : [0.43, 0.285, 0.285]
        let h = weights.map { usable * $0 }
        return VStack(spacing: 0) {
            if now {
                tile(.readiness, ReadinessTileContent.a11y(s.readiness), CGSize(width: 361, height: 262)) {
                    ReadinessTileContent(readiness: s.readiness, play: play[i])
                }
                .frame(height: h[0])
                rule
                HStack(spacing: Self.gap) {
                    if let p = s.pulse {
                        tile(.pulse, PulseTileContent.a11y(p), half) { PulseTileContent(block: p, play: play[i]) }
                    }
                    if let st = s.steps {
                        tile(.steps, StepsTileContent.a11y(st), half) { StepsTileContent(block: st, play: play[i]) }
                    }
                }
                .frame(height: h[1])
                rule
                tile(.day, L("today.a11y.tape"), CGSize(width: 361, height: 170)) {
                    TapeTileContent(tape: s.tape, play: play[i])
                }
                .frame(height: h[2])
            } else {
                if let sl = s.sleep {
                    tile(.sleep, SleepTileContent.a11y(sl), CGSize(width: 361, height: 262)) {
                        SleepTileContent(block: sl, play: play[i])
                    }
                    .frame(height: h[0])
                } else {
                    emptyNight.frame(height: h[0])
                }
                rule
                HStack(spacing: Self.gap) {
                    if let r = s.restingHR {
                        tile(.restingHR, SeriesTileContent.a11y(L("today.row.rhr"), r), half) {
                            SeriesTileContent(metric: .heartRate, name: L("today.row.rhr"), block: r, play: play[i])
                        }
                    }
                    if let v = s.hrv {
                        tile(.hrv, SeriesTileContent.a11y(L("metric.1"), v), half) {
                            SeriesTileContent(metric: .hrv, name: L("metric.1"), block: v, play: play[i])
                        }
                    }
                }
                .frame(height: h[1])
                rule
                HStack(spacing: Self.gap) {
                    if let t = s.skinTemp {
                        tile(.skinTemp, TrendTileContent.a11y(L("today.tile.temp"), t), half) {
                            TrendTileContent(metric: .skinTemp, name: L("today.tile.temp"), block: t, play: play[i])
                        }
                    }
                    if let o = s.spo2 {
                        tile(.spo2, TrendTileContent.a11y(L("metric.5"), o), half) {
                            TrendTileContent(metric: .spo2, name: L("metric.5"), block: o, play: play[i])
                        }
                    }
                }
                .frame(height: h[2])
            }
        }
        .padding(.horizontal, Self.side)
        .padding(.top, 0)
        .frame(maxHeight: .infinity, alignment: .top)
    }

    private var rule: some View { Rectangle().fill(Palette.hairline).frame(height: 1 / UIScreen.main.scale) }

    private let half = CGSize(width: 172, height: 200)

    private func tile<C: View>(
        _ d: TodayDestination, _ a11y: String, _ design: CGSize, @ViewBuilder content: @escaping () -> C
    ) -> some View {
        Tile(destination: d, design: design, a11y: a11y, onOpen: model.open, onInfo: { model.info = $0 }, content: content)
    }

    private var emptyNight: some View {
        VStack(spacing: Space.s12) {
            MetricMarkShape(metric: .sleep, size: 30, color: Palette.text3)
            Text(L("today.noNight")).font(.system(size: 15)).foregroundStyle(Palette.text2).multilineTextAlignment(.center)
                .padding(.horizontal, Space.s24)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: playback

    /// Every visit to a page plays its entrance again: reset without animation, then let the blocks come in.
    private func replay(_ p: Int) {
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) { play[p] = false }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.06) { play[p] = true }
    }

    // MARK: no disc

    private var unpaired: some View {
        VStack(alignment: .leading, spacing: Space.s16) {
            Spacer()
            HStack(spacing: Space.s12) {
                ForEach(Metric.allCases) { m in PoppingMark(metric: m, size: 30, play: play[0], delay: 0.1 + Double(m.rawValue) * 0.08) }
            }
            Text(L("today.setup")).font(.title).foregroundStyle(Palette.text1)
            Text(L("today.setup.body")).font(.body).foregroundStyle(Palette.text2)
            Button(L("today.setup.cta")) { onSetup() }.buttonStyle(.primary).padding(.top, Space.s8)
            Spacer()
        }
        .padding(.horizontal, Space.margin)
    }
}
