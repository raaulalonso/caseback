import SwiftUI

/// What a tap on a section of Today, or on the chosen row of Trends, opens: one screen per metric. They share a skeleton (the
/// name and its "i" at the top, the number and the chart you can scrub, then what is specific to the metric, what usually affects
/// it) and differ in what sits between. Scores say how they add up; signals say where they sit against
/// your normal; the day says how the heart went through it. Nothing gives advice.
struct MetricDetailScreen: View {
    let destination: TodayDestination
    let today: TodayModel
    let trends: TrendsModel
    var onClose: () -> Void

    @State private var range: TrendRange
    @State private var scrub: Int?
    @State private var sleepMetric: TrendMetric = .sleepScore
    @State private var play = false
    @State private var info: TodayDestination?

    init(destination: TodayDestination, today: TodayModel, trends: TrendsModel, onClose: @escaping () -> Void) {
        self.destination = destination
        self.today = today
        self.trends = trends
        self.onClose = onClose
        _range = State(initialValue: trends.range)
    }

    /// The day and the pulse are the same screen.
    private var shown: TodayDestination { destination == .day ? .pulse : destination }
    private var s: TodaySnapshot { today.snapshot }

    var body: some View {
        VStack(spacing: 0) {
            DetailTopBar(title: shown.title, metric: shown.metric, onBack: onClose, onInfo: { info = shown })
                .padding(.horizontal, Self.side).padding(.top, SafeArea.top + Space.s4)
            ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    content
                    DetailSection(title: L("detail.sec.affects")) {
                        VStack(alignment: .leading, spacing: 10) {
                            ForEach(DetailCopy.affects(shown), id: \.self) { line in
                                Text(line).font(.system(size: 15)).foregroundStyle(Palette.text2)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .id("affects")
                }
                .padding(.horizontal, Self.side)
                .padding(.bottom, SafeArea.bottom + Space.s32)
            }
            .scrollIndicators(.hidden)
            .scrollBounceBehavior(.basedOnSize)
            .accessibilityIdentifier("detail.scroll")
            .task {
                // Screenshots only: `-detail-scroll a|b|affects`.
                if let id = LaunchOnce.take("detail-scroll") {
                    try? await Task.sleep(nanoseconds: 600_000_000)
                    proxy.scrollTo(id, anchor: .top)
                }
            }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Palette.ground)
        .task {
            replay()
            // Screenshots only: `-detail-info YES` opens the "i" of the screen.
            if LaunchOnce.take("detail-info") != nil { info = shown }
        }
        .onChange(of: range) { _, _ in replay() }
        .onChange(of: sleepMetric) { _, _ in scrub = nil; replay() }
        .sheet(item: $info) { InfoSheet(destination: $0, fine: DetailCopy.caveat($0)) }
    }

    private static let side: CGFloat = 16

    // MARK: content by metric

    @ViewBuilder private var content: some View {
        switch shown {
        case .readiness:
            hero(.readiness)
            readinessMoves.id("a")
        case .sleep:
            sleepPicker
            hero(sleepMetric)
            sleepNight.id("a")
            sleepScoreParts.id("b")
        case .steps:
            hero(.steps)
            stepsToday.id("a")
            stepsWeek.id("b")
        case .pulse, .day:
            pulseNow
            pulseDay.id("a")
            pulseRecent.id("b")
        case .restingHR: hero(.restingHR); normal(.restingHR).id("a")
        case .hrv: hero(.hrv); normal(.hrv).id("a")
        case .skinTemp: hero(.skinTemp); normal(.skinTemp).id("a")
        case .spo2: hero(.spo2); normal(.spo2).id("a")
        }
    }

    @ViewBuilder private func hero(_ m: TrendMetric) -> some View {
        if trends.hasTrends {
            TrendHero(metric: m, series: trends.series(m), endDate: trends.snapshot.endDate, range: $range, scrub: $scrub, play: play)
        } else {
            VStack(alignment: .leading, spacing: Space.s12) {
                Dots(done: trends.snapshot.nights, total: TrendsSnapshot.minimumNights, color: m.metric.color, size: 14, play: play)
                    .frame(width: 100)
                Text(L("trends.empty")).font(.system(size: 17)).foregroundStyle(Palette.text2)
            }
            .padding(.vertical, Space.s24)
        }
    }

    // MARK: readiness

    @ViewBuilder private var readinessMoves: some View {
        DetailSection(title: L("detail.sec.moves")) {
            Text(TodayInsights.headline(s)).font(.system(size: 17)).foregroundStyle(Palette.text1)
                .fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 0) {
                ForEach(Array(TodayInsights.signals(s).enumerated()), id: \.element.id) { i, sig in
                    SignalRow(signal: sig, play: play, delay: 0.2 + Double(i) * 0.08) { d, _ in today.navigate(d) }
                }
            }
        }
    }

    // MARK: sleep

    private var sleepPicker: some View {
        HStack {
            WordPicker(
                options: [TrendMetric.sleepScore, .sleep], selection: $sleepMetric,
                label: { $0 == .sleepScore ? L("detail.sleep.score") : L("detail.sleep.hours") },
                accessibility: { $0 == .sleepScore ? L("detail.sleep.score") : L("detail.sleep.hours") })
            Spacer(minLength: 0)
        }
        .padding(.top, Space.s8)
    }

    @ViewBuilder private var sleepNight: some View {
        if let b = s.sleep, let facts = SleepFacts.make(b), let summary = TodayInsights.sleepSummary(s) {
            DetailSection(title: L("today.lastNight")) {
                Text(summary.sentence).font(.system(size: 17)).foregroundStyle(Palette.text1)
                    .fixedSize(horizontal: false, vertical: true)
                Hypnogram(block: b, play: play, labels: true).frame(height: 150)
                HStack {
                    Text(b.from); Spacer(); Text(b.to)
                }
                .font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3)
                .padding(.leading, Hypnogram.gutter)
                HStack(alignment: .top, spacing: Space.s16) {
                    Fact(value: duration(facts.inBedMinutes), label: L("detail.sleep.inBed"))
                    Fact(value: duration(facts.asleepMinutes), label: L("detail.sleep.asleep"))
                    Fact(value: "\(Int((facts.efficiency * 100).rounded())) %", label: L("detail.sleep.efficiency"))
                }
                .padding(.top, 4)
                StageBreakdown(stages: summary.stages, play: play).padding(.top, 4)
            }
        } else {
            DetailSection(title: L("today.lastNight")) {
                Text(L("today.noNight")).font(.system(size: 17)).foregroundStyle(Palette.text2)
            }
        }
    }

    @ViewBuilder private var sleepScoreParts: some View {
        if let b = s.sleep, let p = SleepScore.parts(segments: b.segments) {
            let w = SleepScore.Parts.weights
            let rows: [(String, Double, Double)] = [
                (L("detail.sleep.duration"), p.duration, w.duration), (L("detail.sleep.efficiency"), p.efficiency, w.efficiency),
                (L("detail.sleep.deep"), p.deep, w.deep), (L("detail.sleep.rem"), p.rem, w.rem),
            ]
            DetailSection(title: L("detail.sec.score")) {
                VStack(spacing: Space.s16) {
                    ForEach(Array(rows.enumerated()), id: \.offset) { i, r in
                        PartBar(
                            name: r.0, points: Int((100 * r.1 * r.2).rounded()), outOf: Int((100 * r.2).rounded()),
                            color: Metric.sleep.color, play: play, delay: 0.2 + Double(i) * 0.08)
                    }
                }
                Text(L("detail.sleep.how")).font(.system(size: 13)).foregroundStyle(Palette.text3)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func duration(_ minutes: Int) -> String {
        let d = TodayFormat.duration(minutes: minutes)
        return d.unit.isEmpty ? d.value : "\(d.value) \(d.unit)"
    }

    // MARK: steps

    @ViewBuilder private var stepsToday: some View {
        if let st = s.steps {
            DetailSection(title: L("detail.sec.hours")) {
                ThickBars(values: st.bins, metric: .steps, play: play).frame(height: 96)
                HStack {
                    ForEach(["0", "6", "12", "18"], id: \.self) { h in
                        Text("\(h) h").frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3)
                Text(L("detail.steps.today", NumberFormatter.localizedString(from: NSNumber(value: st.total), number: .decimal)))
                    .font(.system(size: 14)).foregroundStyle(Palette.text2)
            }
        }
    }

    @ViewBuilder private var stepsWeek: some View {
        if let w = StepsWeek.make(trends.series(.steps)) {
            DetailSection(title: L("detail.sec.week")) {
                HStack(alignment: .top, spacing: Space.s16) {
                    Fact(value: TrendFormat.parts(w.average, .steps).value, label: L("detail.steps.average"))
                    Fact(value: TrendFormat.parts(w.normal, .steps).value, label: L("detail.steps.normal"))
                }
                Text(L("detail.steps.note")).font(.system(size: 13)).foregroundStyle(Palette.text3)
                    .fixedSize(horizontal: false, vertical: true)
            }
        } else {
            DetailSection(title: L("detail.sec.week")) {
                Text(L("detail.steps.note")).font(.system(size: 13)).foregroundStyle(Palette.text3)
            }
        }
    }

    // MARK: pulse

    private var pulseNow: some View {
        VStack(alignment: .leading, spacing: 6) {
            ValueRow(
                value: s.pulse?.bpm.map(String.init) ?? "—", unit: "bpm",
                note: s.pulse.map { TodayFormat.age(minutes: $0.ageMinutes) }, size: 56, dim: s.pulse?.bpm == nil)
            if let f = PulseFacts.make(s) {
                Text(L("today.insight.coverage", f.hoursRead, f.hoursElapsed)).font(.system(size: 14)).foregroundStyle(Palette.text2)
            }
        }
        .padding(.top, Space.s16).padding(.bottom, Space.s16)
    }

    @ViewBuilder private var pulseDay: some View {
        DetailSection(title: L("today.group.day")) {
            HStack(spacing: 14) {
                legend(Metric.heartRate.color, L("today.tape.hr"))
                legend(Metric.sleep.color, L("today.tape.sleep"))
            }
            DayTapeChart(tape: s.tape, play: play).frame(height: 190)
            if let f = PulseFacts.make(s) {
                HStack(alignment: .top, spacing: Space.s16) {
                    Fact(value: f.lowest.map(String.init) ?? "—", label: L("detail.pulse.lowest"))
                    Fact(value: f.highest.map(String.init) ?? "—", label: L("detail.pulse.highest"))
                    Fact(value: f.resting.map(String.init) ?? "—", label: L("detail.pulse.resting"))
                }
                .padding(.top, 4)
            }
        }
    }

    @ViewBuilder private var pulseRecent: some View {
        if let p = s.pulse, p.recent.contains(where: { $0 != nil }) {
            DetailSection(title: L("detail.sec.recent")) {
                ThickLine(series: p.recent, metric: .heartRate, baseline: nil, play: play).frame(height: 110)
                Text(L("today.info.pulse.what")).font(.system(size: 13)).foregroundStyle(Palette.text3)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func legend(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 6) {
            Capsule().fill(color).frame(width: 7, height: 12)
            Text(text).font(.system(size: 12)).foregroundStyle(Palette.text3).lineLimit(1)
        }
    }

    // MARK: your normal

    @ViewBuilder private func normal(_ m: TrendMetric) -> some View {
        let r = TrendMath.reading(trends.series(m), range: range)
        DetailSection(title: L("detail.sec.normal")) {
            if let u = r.usual, let med = r.median {
                HStack(alignment: .top, spacing: Space.s16) {
                    Fact(value: DetailCopy.rangeText(u, m), label: L("detail.normal.range"))
                    Fact(value: TrendFormat.parts(med, m).value, label: L("detail.normal.median"))
                }
                Text(L(m.trendOnly ? "detail.normal.note.trend" : "detail.normal.note")).font(.system(size: 13)).foregroundStyle(Palette.text3)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                Text(L("detail.normal.none", TrendMath.minimumForNormal)).font(.system(size: 15)).foregroundStyle(Palette.text2)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    // MARK: playback

    private func replay() {
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) { play = false }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) { play = true }
    }
}
