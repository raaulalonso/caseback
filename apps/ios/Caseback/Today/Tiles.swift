import SwiftUI

// The blocks of the Today panel. Each is drawn at a fixed design size and scaled to the space the panel gives it
// (`FitCanvas`), so the panel fits every phone without scrolling. The mark of the metric is the identifier: big, in the
// corner of every block.

struct TileFrames: PreferenceKey {
    static var defaultValue: [TodayDestination: CGRect] = [:]
    static func reduce(value: inout [TodayDestination: CGRect], nextValue: () -> [TodayDestination: CGRect]) {
        value.merge(nextValue()) { $1 }
    }
}

struct TilePress: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.965 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.7), value: configuration.isPressed)
    }
}

/// Lays content out at a fixed design height and scales it by height only, so it always spans the full width and every
/// section's left edge lines up, on any phone.
struct FitHeight<Content: View>: View {
    var designHeight: CGFloat
    @ViewBuilder var content: () -> Content

    var body: some View {
        GeometryReader { g in
            let k = min(g.size.height / designHeight, 1.25)
            content()
                .frame(width: g.size.width / k, height: designHeight)
                .scaleEffect(k, anchor: .topLeading)
                .frame(width: g.size.width, height: g.size.height, alignment: .topLeading)
        }
    }
}

/// A section's press: it dims a little, no box, no scale.
struct SectionPress: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .opacity(configuration.isPressed ? 0.55 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

/// A discreet "i" that explains the chart next to it. With a metric, that metric's mark sits to its left, a little smaller and a little
/// apart: the one place a section says which metric it is.
struct InfoButton: View {
    var metric: Metric?
    var action: () -> Void

    var body: some View {
        Button {
            Haptics.tick()
            action()
        } label: {
            HStack(spacing: 13) {
                if let metric { MetricMarkShape(metric: metric, size: 14) }
                Text("i")
                    .font(.monoFixed(.medium, 11))
                    .foregroundStyle(Palette.text3)
                    .frame(width: 18, height: 18)
                    .overlay(Circle().strokeBorder(Palette.text3, lineWidth: 1.2))
            }
            .padding(.horizontal, 11)
            .frame(height: 40)
            .contentShape(Rectangle())
        }
        .buttonStyle(SectionPress())
        .accessibilityLabel(L("today.info.open"))
    }
}

/// One section of the panel: no surface, only the content on the black, the tap that opens its screen and the "i" that
/// explains it. Nothing in it animates in; only its chart does.
struct Tile<Content: View>: View {
    var destination: TodayDestination
    var design: CGSize
    var a11y: String
    var onOpen: (TodayDestination, CGRect) -> Void
    var onInfo: (TodayDestination) -> Void
    @ViewBuilder var content: () -> Content

    @State private var frame: CGRect = .zero

    var body: some View {
        ZStack(alignment: .topTrailing) {
            Button {
                Haptics.tap()
                onOpen(destination, frame)
            } label: {
                FitHeight(designHeight: design.height) { content() }
                    .contentShape(Rectangle())
            }
            .buttonStyle(SectionPress())
            .background(
                GeometryReader { g in
                    Color.clear.onChange(of: g.frame(in: .global), initial: true) { _, f in frame = f }
                }
            )
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(a11y)
            .accessibilityAddTraits(.isButton)
            InfoButton(metric: destination.metric) { onInfo(destination) }.offset(x: 10, y: 2)
        }
    }
}

/// A mark that pops in with a little overshoot.
struct PoppingMark: View {
    var metric: Metric
    var size: CGFloat
    var play: Bool
    var delay = 0.1
    var color: Color?

    var body: some View {
        MetricMarkShape(metric: metric, size: size, color: color)
            .scaleEffect(play ? 1 : 0.01)
            .rotationEffect(.degrees(play ? 0 : -50))
            .motion(.spring(response: 0.55, dampingFraction: 0.48).delay(delay), value: play)
    }
}

/// The name of what the section shows, always in the same place.
struct SectionTitle: View {
    var text: String

    var body: some View {
        Text(text)
            .font(.system(size: 14, weight: .medium)).foregroundStyle(Palette.text3)
            .lineLimit(1).minimumScaleFactor(0.7)
            .padding(.trailing, 66)
            .frame(maxWidth: .infinity, minHeight: 22, alignment: .leading)
    }
}

/// A number, its unit and, at the far end, a change or an age.
struct ValueRow: View {
    var value: String
    var unit: String = ""
    var note: String?
    var size: CGFloat = 44
    var color: Color = Palette.text1
    var dim = false

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 5) {
            Text(value)
                .font(.monoFixed(.light, size))
                .foregroundStyle(dim ? Palette.text3 : color)
                .lineLimit(1).minimumScaleFactor(0.6).fixedSize()
            if !unit.isEmpty { Text(unit).font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3) }
            Spacer(minLength: 6)
            if let note {
                Text(note).font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text2).lineLimit(1).minimumScaleFactor(0.7)
            }
        }
        .frame(height: size * 1.2, alignment: .leading)
    }
}

// MARK: readiness

struct ReadinessTileContent: View {
    var readiness: ReadinessState
    var play: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionTitle(text: L("metric.3")).padding(.top, 12)
            HStack(alignment: .center, spacing: 16) {
                Text(numeral)
                    .font(.monoFixed(.light, 64))
                    .foregroundStyle(score == nil ? Palette.text3 : Metric.readiness.color)
                    .lineLimit(1).minimumScaleFactor(0.5).fixedSize()
                VStack(alignment: .leading, spacing: 4) {
                    if let zone {
                        Text(zone.word(.recovery)).font(.system(size: 20, weight: .semibold)).foregroundStyle(Metric.readiness.color)
                    }
                    Text(sentence)
                        .font(.system(size: 15))
                        .foregroundStyle(zone == nil ? Palette.text1 : Palette.text2)
                        .lineLimit(3).minimumScaleFactor(0.8)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(height: 70)
            Spacer(minLength: 6)
            ReadinessGauge(score: score, play: play).frame(height: 36)
            if case .calibrating(let day) = readiness {
                CalibrationPips(done: day, total: 7, play: play).frame(height: 36).padding(.top, 10)
            } else if case .score(_, let c) = readiness {
                ContributionBars(components: c, play: play).frame(height: 54).padding(.top, 12)
                HStack {
                    Text(L("today.bars.worse")); Spacer()
                    Text(L("today.bars.usual")); Spacer()
                    Text(L("today.bars.better"))
                }
                .font(.monoFixed(.regular, 10)).foregroundStyle(Palette.text3)
                .padding(.leading, 78).padding(.top, 4)
            }
        }
        .padding(.bottom, 10)
    }

    private var score: Int? { if case .score(let s, _) = readiness { return s } else { return nil } }
    private var zone: ScoreZone? { score.map { ScoreZone.of($0, .recovery) } }
    private var numeral: String { score.map(String.init) ?? "—" }

    private var sentence: String {
        switch readiness {
        case .score(_, let c): return ReadinessSentence.make(c, compact: true)
        case .calibrating(let day): return L("today.calibrating", day)
        case .noData: return L("today.noNight")
        }
    }

    static func a11y(_ r: ReadinessState) -> String {
        switch r {
        case .score(let s, let c):
            return [L("today.a11y.readiness", s), ScoreZone.of(s, .recovery).word(.recovery), ReadinessSentence.make(c)].joined(separator: ". ")
        case .calibrating(let day): return L("today.calibrating", day)
        case .noData: return L("today.noNight")
        }
    }
}

struct CalibrationPips: View {
    var done: Int
    var total: Int
    var play: Bool

    var body: some View { Dots(done: done, total: total, color: Metric.readiness.color, size: 16, play: play) }
}

// MARK: sleep

struct SleepTileContent: View {
    var block: SleepBlock
    var play: Bool

    private var duration: String {
        let d = TodayFormat.duration(minutes: block.minutes)
        return d.unit.isEmpty ? d.value : "\(d.value) \(d.unit)"
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionTitle(text: L("metric.2")).padding(.top, 12)
            if let score = block.score {
                // The score says how the night was; the hours and the change from your median are right next to it.
                HStack(alignment: .center, spacing: 16) {
                    Text("\(score)").font(.monoFixed(.light, 64)).foregroundStyle(Metric.sleep.color).fixedSize()
                    VStack(alignment: .leading, spacing: 4) {
                        Text(ScoreZone.of(score, .sleep).word(.sleep))
                            .font(.system(size: 20, weight: .semibold)).foregroundStyle(Metric.sleep.color)
                        Text("\(duration) · \(TodayFormat.sleepDelta(minutes: block.deltaMinutes))")
                            .font(.monoFixed(.regular, 13)).foregroundStyle(Palette.text2).lineLimit(1).minimumScaleFactor(0.7)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 70)
            } else {
                ValueRow(
                    value: TodayFormat.duration(minutes: block.minutes).value,
                    note: TodayFormat.sleepDelta(minutes: block.deltaMinutes), size: 56, color: Metric.sleep.color)
            }
            Spacer(minLength: 10)
            Hypnogram(block: block, play: play).frame(height: 84)
            HStack {
                Text(block.from); Spacer(); Text(block.to)
            }
            .font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3)
            .padding(.top, 8)
        }
        .padding(.bottom, 10)
    }

    static func a11y(_ b: SleepBlock) -> String {
        let d = TodayFormat.duration(minutes: b.minutes)
        var parts = [L("metric.2")]
        if let score = b.score { parts += ["\(score)", ScoreZone.of(score, .sleep).word(.sleep)] }
        parts += ["\(d.value) \(d.unit)", TodayFormat.sleepDelta(minutes: b.deltaMinutes)]
        return parts.joined(separator: ", ")
    }
}

// MARK: half blocks

/// The frame shared by the half-width sections: the name, the number and its change, then the chart.
struct MetricHalf<Chart: View>: View {
    var name: String
    var value: String?
    var unit: String
    /// A change or an age.
    var note: String?
    var play: Bool
    @ViewBuilder var chart: () -> Chart

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionTitle(text: name).padding(.top, 12)
            ValueRow(value: value ?? "—", unit: value == nil ? "" : unit, note: note, dim: value == nil)
            chart().frame(maxHeight: .infinity).padding(.top, 8)
        }
        .padding(.bottom, 10)
    }
}

struct SeriesTileContent: View {
    var metric: Metric
    var name: String
    var block: SeriesBlock
    var play: Bool

    var body: some View {
        MetricHalf(name: name, value: block.value, unit: block.unit, note: Self.note(block), play: play) {
            if !block.series.isEmpty { ThickLine(series: block.series, metric: metric, baseline: block.baseline, play: play) }
        }
    }

    /// "−4 · lower": the change and, in words, which way it went.
    static func note(_ b: SeriesBlock) -> String? {
        guard let delta = b.delta, let d = b.deltaValue else { return b.delta }
        let word = SignalStatus.direction(delta: Double(d), baseline: b.baseline ?? 0)
        return "\(delta) · \(word)"
    }

    static func a11y(_ name: String, _ b: SeriesBlock) -> String {
        [name, b.value.map { "\($0) \(b.unit)" }, b.delta.map { "\($0), \(L("today.vsMedian"))" }].compactMap { $0 }.joined(separator: ", ")
    }
}

struct PulseTileContent: View {
    var block: PulseBlock
    var play: Bool

    var body: some View {
        MetricHalf(
            name: L("metric.0"), value: block.bpm.map(String.init), unit: "bpm",
            note: TodayFormat.ageShort(minutes: block.ageMinutes), play: play
        ) {
            ThickLine(series: block.recent, metric: .heartRate, baseline: nil, play: play)
        }
    }

    static func a11y(_ b: PulseBlock) -> String {
        [L("metric.0"), b.bpm.map { "\($0) bpm" }, TodayFormat.age(minutes: b.ageMinutes)].compactMap { $0 }.joined(separator: ", ")
    }
}

struct StepsTileContent: View {
    var block: StepsBlock
    var play: Bool

    var body: some View {
        MetricHalf(
            name: L("metric.4"),
            value: NumberFormatter.localizedString(from: NSNumber(value: block.total), number: .decimal), unit: "",
            note: nil, play: play
        ) {
            ThickBars(values: block.bins, metric: .steps, play: play)
        }
    }

    static func a11y(_ b: StepsBlock) -> String {
        "\(L("metric.4")), \(b.total), \(L("today.steps.caption"))"
    }
}

/// SpO2 and skin temperature: trend only (D13). Dashed line, dots while calibrating, and the word "trend". While
/// calibrating the number is how many nights it has: "3/5 nights".
struct TrendTileContent: View {
    var metric: Metric
    var name: String
    var block: TrendBlock
    var play: Bool

    var body: some View {
        if let nights = block.calibratingNights {
            MetricHalf(name: name, value: "\(nights)/5", unit: L("today.temp.nights"), note: nil, play: play) {
                VStack(spacing: 10) {
                    Dots(done: nights, total: 5, color: metric.color, size: 12, play: play)
                    Text(L("today.temp.calibratingWord")).font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3)
                }
                .frame(maxHeight: .infinity, alignment: .center)
            }
        } else {
            MetricHalf(name: name, value: block.value, unit: block.unit, note: L("today.temp.trend"), play: play) {
                ThickLine(series: block.series, metric: metric, baseline: nil, dashed: true, play: play)
            }
        }
    }

    static func a11y(_ name: String, _ b: TrendBlock) -> String {
        if let n = b.calibratingNights { return "\(name), \(L("today.temp.calibrating", n))" }
        return [name, b.value.map { "\($0) \(b.unit)" }, L("today.temp.trend")].compactMap { $0 }.joined(separator: ", ")
    }
}

// MARK: day

struct TapeTileContent: View {
    var tape: DayTape
    var play: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            SectionTitle(text: L("today.group.day")).padding(.top, 12)
            HStack(spacing: 14) {
                legend(Metric.heartRate.color, L("today.tape.hr"))
                legend(Metric.sleep.color, L("today.tape.sleep"))
            }
            .padding(.top, 2)
            DayTapeChart(tape: tape, play: play).padding(.top, 8)
        }
        .padding(.bottom, 8)
    }

    private func legend(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 6) {
            Capsule().fill(color).frame(width: 7, height: 12)
            Text(text).font(.system(size: 12)).foregroundStyle(Palette.text3).lineLimit(1)
        }
    }
}
