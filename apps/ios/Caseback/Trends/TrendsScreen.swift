import SwiftUI

/// Trends: one chart you can explore, over a list of every metric that picks which one it shows. Fixed, like Today: it does not
/// scroll, it is divided by the screen's height. A range of 7, 30 or 90 days applies to all of it.
struct TrendsScreen: View {
    @Bindable var model: TrendsModel
    var onOpen: (TodayDestination, CGRect) -> Void

    @State private var heroPlay = false
    @State private var listPlay = false
    @State private var heroFrame: CGRect = .zero
    @Namespace private var rangeNS
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private static let side: CGFloat = 16

    var body: some View {
        VStack(spacing: 0) {
            header.padding(.horizontal, Self.side).padding(.top, Space.s8).padding(.bottom, Space.s12)
            if model.hasTrends {
                GeometryReader { g in
                    VStack(spacing: 0) {
                        hero.frame(height: g.size.height * 0.43)
                        rule
                        list.frame(height: g.size.height * 0.57 - 1)
                    }
                    .padding(.horizontal, Self.side)
                }
            } else {
                empty
            }
        }
        .task {
            replayAll()
            // Screenshots only: `-trends-scrub 12` holds the cursor on that day, `-trends-info YES` shows the explanation.
            if let v = UserDefaults.standard.string(forKey: "trends-scrub").flatMap(Int.init) { model.scrub = v }
            if UserDefaults.standard.bool(forKey: "trends-info") { model.info = model.metric }
        }
        .onChange(of: model.range) { _, _ in replayAll() }
        .onChange(of: model.metric) { _, _ in replay(hero: true) }
        .sheet(item: $model.info) { m in
            InfoSheet(
                destination: m.destination,
                extra: m.scoreKind.map { L($0 == .recovery ? "trends.info.zones.recovery" : "trends.info.zones.sleep") } ?? L("trends.info.band"))
        }
    }

    // MARK: header

    private var header: some View {
        HStack(spacing: Space.s12) {
            Text(L("trends.range.title", model.range.days))
                .font(.system(size: 15, weight: .medium)).foregroundStyle(Palette.text2)
                .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                .id(model.range)
                .transition(.opacity.combined(with: .offset(y: 5)))
                .accessibilityAddTraits(.isHeader)
            Spacer(minLength: 0)
            HStack(spacing: 2) { ForEach(TrendRange.allCases) { rangeButton($0) } }
        }
        .frame(height: 32)
        .animation(.easeOut(duration: 0.25), value: model.range)
    }

    private func rangeButton(_ r: TrendRange) -> some View {
        let active = model.range == r
        return Button {
            guard !active else { return }
            Haptics.tick()
            withAnimation(reduceMotion ? nil : .spring(response: 0.4, dampingFraction: 0.8)) { model.range = r }
        } label: {
            Text("\(r.days)")
                .font(.monoFixed(.medium, 15))
                .foregroundStyle(active ? Palette.ground : Palette.text3)
                .frame(width: 42, height: 30)
                .background {
                    if active { Capsule(style: .continuous).fill(Palette.text1).matchedGeometryEffect(id: "range", in: rangeNS) }
                }
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(L("trends.range.title", r.days))
        .accessibilityAddTraits(active ? .isSelected : [])
    }

    private var rule: some View { Rectangle().fill(Palette.hairline).frame(height: 1 / UIScreen.main.scale) }

    // MARK: hero

    private var hero: some View {
        let m = model.metric
        let series = model.series(m)
        let reading = model.reading(m)
        return ZStack(alignment: .topTrailing) {
            FitHeight(designHeight: 322) {
                VStack(alignment: .leading, spacing: 0) {
                    Button {
                        Haptics.tap()
                        onOpen(m.destination, heroFrame)
                    } label: {
                        heroHeader(m, series, reading).contentShape(Rectangle())
                    }
                    .buttonStyle(SectionPress())
                    .background(
                        GeometryReader { g in
                            Color.clear.onChange(of: g.frame(in: .global), initial: true) { _, f in heroFrame = f }
                        })
                    if let nights = series.calibratingNights, series.values.isEmpty {
                        calibrating(m, nights)
                    } else {
                        TrendChart(
                            metric: m, reading: reading, partialLast: series.lastIsPartial, endDate: model.snapshot.endDate,
                            play: heroPlay, scrub: model.scrub, onScrub: { model.scrub = $0 }
                        )
                        .frame(maxHeight: .infinity)
                        .padding(.top, 10)
                        .accessibilityElement()
                        .accessibilityLabel(a11y(m, reading))
                        .accessibilityAdjustableAction { dir in step(dir, count: reading.window.count) }
                        if let c = TrendConclusion.text(m, series: series, reading: reading) {
                            Text(c).font(.system(size: 13)).foregroundStyle(Palette.text2)
                                .lineLimit(2).fixedSize(horizontal: false, vertical: true)
                                .frame(maxWidth: .infinity, minHeight: 34, alignment: .topLeading)
                                .padding(.top, 8)
                        }
                        if m.scoreKind == nil { extremes(m, reading).padding(.top, 2) }
                    }
                }
                .padding(.top, 12)
                .padding(.bottom, 10)
            }
            InfoButton(metric: m.metric) { model.info = m }.offset(x: 10, y: 2)
        }
    }

    /// Name, then the number: the latest value, or the day under the finger.
    private func heroHeader(_ m: TrendMetric, _ series: TrendSeries, _ r: TrendReading) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionTitle(text: m.name)
            if let nights = series.calibratingNights, series.values.isEmpty {
                ValueRow(value: "\(nights)/5", unit: L("today.temp.nights"), note: L("today.temp.trend"))
            } else if let s = model.scrub, s < r.window.count {
                let date = TrendMath.date(index: s, count: r.window.count, end: model.snapshot.endDate)
                let partial = series.lastIsPartial && s == r.window.count - 1
                if let v = r.window[s] {
                    let p = TrendFormat.parts(v, m)
                    ValueRow(
                        value: p.value, unit: p.unit,
                        note: (m.scoreKind.map { ScoreZone.of(Int(v.rounded()), $0).word($0) + " · " } ?? "")
                            + TrendFormat.longDate(date) + (partial ? " · " + L("trends.partial") : ""),
                        color: m.scoreKind == nil ? Palette.text1 : m.metric.color)
                } else {
                    ValueRow(value: "—", note: TrendFormat.longDate(date) + " · " + L("trends.noData"), dim: true)
                }
            } else if let v = r.latest {
                let p = TrendFormat.parts(v, m)
                ValueRow(
                    value: p.value, unit: p.unit,
                    note: series.lastIsPartial
                        ? L("trends.partial")
                        : (m.scoreKind != nil ? scoreNote(m, v, r) : r.delta.map { TrendFormat.delta($0, m) + " " + L("today.vsMedian") } ?? L("trends.noBand")),
                    color: m.scoreKind == nil ? Palette.text1 : m.metric.color)
            } else {
                ValueRow(value: "—", dim: true)
            }
        }
    }

    /// "Moderate · −3 vs your 30-day median": the zone first, then how it compares.
    private func scoreNote(_ m: TrendMetric, _ v: Double, _ r: TrendReading) -> String {
        guard let kind = m.scoreKind else { return "" }
        let word = ScoreZone.of(Int(v.rounded()), kind).word(kind)
        guard let d = r.delta else { return word }
        return word + " · " + TrendFormat.delta(d, m) + " " + L("today.vsMedian")
    }

    private func calibrating(_ m: TrendMetric, _ nights: Int) -> some View {
        VStack(spacing: 12) {
            Dots(done: nights, total: 5, color: m.metric.color, size: 14, play: heroPlay)
            Text(L("today.temp.calibratingWord")).font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    /// The lowest and highest day of the range, or why there is no usual range yet.
    private func extremes(_ m: TrendMetric, _ r: TrendReading) -> some View {
        let n = r.window.count
        func text(_ key: String, _ e: (index: Int, value: Double)?) -> String {
            guard let e else { return "" }
            let d = TrendFormat.shortDate(TrendMath.date(index: e.index, count: n, end: model.snapshot.endDate))
            return L(key, TrendFormat.text(e.value, m), d)
        }
        return HStack {
            Text(text("trends.low", r.low)); Spacer()
            Text(text("trends.high", r.high))
        }
        .font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3)
        .lineLimit(1).minimumScaleFactor(0.7)
        .frame(height: 16)
    }

    private func step(_ dir: AccessibilityAdjustmentDirection, count: Int) {
        guard count > 0 else { return }
        let cur = model.scrub ?? count - 1
        switch dir {
        case .increment: model.scrub = min(cur + 1, count - 1)
        case .decrement: model.scrub = max(cur - 1, 0)
        @unknown default: break
        }
    }

    private func a11y(_ m: TrendMetric, _ r: TrendReading) -> String {
        var parts = [m.name, L("trends.range.title", model.range.days)]
        if let v = r.latest { parts.append(TrendFormat.text(v, m)) }
        if let med = r.median { parts.append(L("today.signal.median", TrendFormat.text(med, m))) }
        return parts.joined(separator: ", ")
    }

    // MARK: list

    private var list: some View {
        FitHeight(designHeight: 420) {
            VStack(spacing: 0) {
                groupLabel(L("trends.group.summary"))
                rows(TrendMetric.summary)
                groupLabel(L("trends.group.signals")).padding(.top, 6)
                rows(TrendMetric.signals)
            }
        }
    }

    private func groupLabel(_ text: String) -> some View {
        Text(text).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.text3)
            .frame(maxWidth: .infinity, minHeight: 22, alignment: .leading)
    }

    private func rows(_ metrics: [TrendMetric]) -> some View {
        VStack(spacing: 0) {
            ForEach(metrics) { m in
                row(m)
                if m != metrics.last { rule }
            }
        }
    }

    private func row(_ m: TrendMetric) -> some View {
        let selected = model.metric == m
        let series = model.series(m)
        let r = model.reading(m)
        return Button {
            if selected {
                Haptics.tap()
                onOpen(m.destination, heroFrame)
            } else {
                Haptics.tick()
                withAnimation(reduceMotion ? nil : .spring(response: 0.4, dampingFraction: 0.85)) { model.metric = m }
            }
        } label: {
            HStack(spacing: 12) {
                Capsule(style: .continuous).fill(selected ? m.metric.color : .clear).frame(width: 3, height: 22)
                Text(m.name)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(selected ? Palette.text1 : Palette.text2)
                    .lineLimit(1).minimumScaleFactor(0.7)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if series.calibratingNights != nil, series.values.isEmpty {
                    Text(L("today.temp.calibratingWord")).font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3)
                        .frame(width: 140, alignment: .trailing)
                } else {
                    Sparkline(series: r.window, metric: m, play: listPlay).frame(width: 56, height: 26)
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(r.latest.map { TrendFormat.text($0, m) } ?? "—")
                            .font(.monoFixed(.regular, 15)).foregroundStyle(Palette.text1).lineLimit(1).minimumScaleFactor(0.7)
                        Text(rowNote(m, series, r))
                            .font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3).lineLimit(1).minimumScaleFactor(0.6)
                    }
                    .frame(width: 96, alignment: .trailing)
                }
            }
            .frame(height: 46)
            .contentShape(Rectangle())
        }
        .buttonStyle(SectionPress())
        .accessibilityLabel([m.name, r.latest.map { TrendFormat.text($0, m) }].compactMap { $0 }.joined(separator: ", "))
        .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
    }

    /// Under a score, its zone; under a signal, its change from your median.
    private func rowNote(_ m: TrendMetric, _ series: TrendSeries, _ r: TrendReading) -> String {
        if let kind = m.scoreKind, let v = r.latest { return ScoreZone.of(Int(v.rounded()), kind).word(kind) }
        if series.lastIsPartial { return L("trends.partial") }
        return r.delta.map { TrendFormat.delta($0, m) } ?? " "
    }

    // MARK: states

    private var empty: some View {
        VStack(spacing: Space.s16) {
            Spacer()
            Dots(done: model.snapshot.nights, total: TrendsSnapshot.minimumNights, color: Palette.text1, size: 16, play: heroPlay)
                .frame(width: 120)
            Text(L("trends.empty")).font(.system(size: 17)).foregroundStyle(Palette.text2).multilineTextAlignment(.center)
                .padding(.horizontal, Space.s32)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: playback

    private func replayAll() { replay(hero: true, list: true) }

    /// Every change of range or metric draws the charts again: wiped without animation, then drawn.
    private func replay(hero: Bool = false, list: Bool = false) {
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) {
            if hero { heroPlay = false }
            if list { listPlay = false }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            if hero { heroPlay = true }
            if list { listPlay = true }
        }
    }
}
