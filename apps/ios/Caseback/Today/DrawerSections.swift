import SwiftUI

// The sections of the conclusions sheet. Same language as the panel: flat shapes, round caps, the metric's mark once per
// item, and only the charts move.

/// A titled group; the title is small and quiet so the numbers lead.
struct SheetSection<Content: View>: View {
    var title: String
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s12) {
            Text(title).font(.system(size: 14, weight: .medium)).foregroundStyle(Palette.text3)
            content()
        }
    }
}

/// Makes any row open the screen of a block, remembering where it sits so the screen can grow out of it.
private struct OpensDestination: ViewModifier {
    var destination: TodayDestination
    var a11y: String
    var onOpen: (TodayDestination, CGRect) -> Void
    @State private var frame: CGRect = .zero

    func body(content: Content) -> some View {
        Button {
            Haptics.tap()
            onOpen(destination, frame)
        } label: {
            content.contentShape(Rectangle())
        }
        .buttonStyle(TilePress())
        .background(
            GeometryReader { g in
                Color.clear.onChange(of: g.frame(in: .global), initial: true) { _, f in frame = f }
            })
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(a11y)
        .accessibilityAddTraits(.isButton)
    }
}

private extension View {
    func opens(_ d: TodayDestination, a11y: String, _ onOpen: @escaping (TodayDestination, CGRect) -> Void) -> some View {
        modifier(OpensDestination(destination: d, a11y: a11y, onOpen: onOpen))
    }
}

// MARK: signals

/// One signal behind the score: name and value, a track that shows where today sits among the last nights and against the
/// median, then the word for it and the numbers.
struct SignalRow: View {
    var signal: Signal
    var play: Bool
    var delay: Double
    var onOpen: (TodayDestination, CGRect) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: Space.s12) {
                MetricMarkShape(metric: signal.metric, size: 16)
                Text(signal.name).font(.system(size: 16, weight: .medium)).foregroundStyle(Palette.text1)
                Spacer(minLength: 0)
                if let v = signal.value {
                    Text(v).font(.monoFixed(.regular, 16)).foregroundStyle(Palette.text1)
                }
            }
            track
            HStack(alignment: .firstTextBaseline, spacing: Space.s8) {
                Text(signal.status.text).font(.system(size: 14, weight: .medium)).foregroundStyle(Palette.text2)
                    .lineLimit(1).minimumScaleFactor(0.8)
                Spacer(minLength: 0)
                Text(signal.detail).font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3)
                    .lineLimit(1).minimumScaleFactor(0.7)
            }
        }
        .padding(.vertical, Space.s12)
        .overlay(alignment: .bottom) { Rectangle().fill(Palette.hairline).frame(height: 1 / UIScreen.main.scale) }
        .opens(signal.destination, a11y: a11y, onOpen)
    }

    @ViewBuilder private var track: some View {
        switch signal.status {
        case .calibrating(let n):
            Dots(done: n, total: 5, color: signal.metric.color, size: 11, play: play)
                .frame(width: 5 * 34, height: 18, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .leading)
        case .missing:
            Capsule(style: .continuous)
                .strokeBorder(Palette.text3, style: StrokeStyle(lineWidth: 1.5, dash: [3, 5]))
                .frame(height: 8).frame(height: 18)
        default:
            RangeTrack(series: signal.series, baseline: signal.baseline, color: signal.metric.color, play: play, delay: delay)
                .frame(height: 18)
        }
    }

    private var a11y: String {
        [signal.name, signal.value, signal.status.text, signal.detail].compactMap { $0 }.joined(separator: ", ")
    }
}

/// The last nights as small dots on a track, the median as a tick, and today as a big dot joined to the median by a bar:
/// where today sits in your own range, at a glance.
struct RangeTrack: View {
    var series: [Double?]
    var baseline: Double?
    var color: Color
    var play: Bool
    var delay: Double

    var body: some View {
        GeometryReader { g in
            let values = series.compactMap { $0 } + [baseline].compactMap { $0 }
            let lo = (values.min() ?? 0), hi = (values.max() ?? 1)
            let span = max(hi - lo, 1e-6)
            let pad: CGFloat = 12
            let x: (Double) -> CGFloat = { pad + CGFloat(($0 - lo) / span) * (g.size.width - 2 * pad) }
            let today = series.last(where: { $0 != nil }) ?? nil
            let from = baseline.map(x) ?? (today.map(x) ?? pad)
            let to = today.map(x) ?? from
            let midY = g.size.height / 2
            ZStack(alignment: .leading) {
                Capsule(style: .continuous).fill(Palette.hairline).frame(height: 6)
                // The nights before today.
                ForEach(Array(series.dropLast().enumerated()), id: \.offset) { _, v in
                    if let v {
                        Circle().fill(Palette.text3).frame(width: 5, height: 5).position(x: x(v), y: midY)
                    }
                }
                if let b = baseline {
                    Rectangle().fill(Palette.text2).frame(width: 2, height: 16).position(x: x(b), y: midY)
                }
                Capsule(style: .continuous).fill(color)
                    .frame(width: play ? max(abs(to - from), 6) : 6, height: 6)
                    .position(x: play ? (from + to) / 2 : from, y: midY)
                    .motion(ChartMotion.grow(delay), value: play)
                if today != nil {
                    Circle().fill(color).frame(width: 14, height: 14)
                        .position(x: play ? to : from, y: midY)
                        .motion(ChartMotion.grow(delay), value: play)
                }
            }
        }
        .accessibilityHidden(true)
    }
}

// MARK: sleep

struct SleepSection: View {
    var summary: SleepSummary
    var play: Bool
    var onOpen: (TodayDestination, CGRect) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s16) {
            HStack(alignment: .top, spacing: Space.s12) {
                MetricMarkShape(metric: .sleep, size: 16).padding(.top, 4)
                Text(summary.sentence).font(.system(size: 17)).foregroundStyle(Palette.text1)
                    .fixedSize(horizontal: false, vertical: true)
            }
            StageBreakdown(stages: summary.stages, play: play)
            if summary.nights.contains(where: { $0 != nil }) {
                VStack(alignment: .leading, spacing: 6) {
                    NightsBars(nights: summary.nights, baseline: summary.baseline, play: play).frame(height: 56)
                    Text(L("today.sleep.week")).font(.system(size: 12)).foregroundStyle(Palette.text3)
                }
            }
        }
        .opens(.sleep, a11y: summary.sentence, onOpen)
    }
}

/// The night split by stage: one capsule per stage as wide as it lasted, and under it each stage with its time.
struct StageBreakdown: View {
    var stages: [StageMinutes]
    var play: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s16) {
            StageBar(stages: stages, play: play).frame(height: 14)
            HStack(alignment: .top, spacing: 0) {
                ForEach(stages, id: \.stage) { s in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            Circle().fill(StageBar.color(s.stage)).frame(width: 8, height: 8)
                            Text(Self.name(s.stage)).font(.system(size: 12)).foregroundStyle(Palette.text3).lineLimit(1)
                        }
                        Text(Self.duration(s.minutes)).font(.monoFixed(.regular, 14)).foregroundStyle(Palette.text1)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    /// How long a stage lasted, "1 h 35" or "12 min": an amount, not a change, so no sign.
    static func duration(_ minutes: Int) -> String {
        let d = TodayFormat.duration(minutes: minutes)
        return d.unit.isEmpty ? d.value : "\(d.value) \(d.unit)"
    }

    static func name(_ s: SleepStage) -> String {
        switch s {
        case .deep: return L("today.stage.deep")
        case .rem: return L("today.stage.rem")
        case .light: return L("today.stage.light")
        case .wake: return L("today.stage.wake")
        }
    }
}

/// The night split by stage: one capsule per stage, as wide as it lasted.
struct StageBar: View {
    var stages: [StageMinutes]
    var play: Bool

    static func color(_ s: SleepStage) -> Color {
        switch s {
        case .deep: return Palette.stageDeep
        case .light: return Palette.stageLight
        case .rem: return Palette.stageRem
        case .wake: return Palette.text2
        }
    }

    var body: some View {
        GeometryReader { g in
            let shown = stages.filter { $0.minutes > 0 }
            let gap: CGFloat = 4
            let total = CGFloat(max(shown.reduce(0) { $0 + $1.minutes }, 1))
            let room = g.size.width - gap * CGFloat(max(shown.count - 1, 0))
            HStack(spacing: gap) {
                ForEach(shown, id: \.stage) { s in
                    Capsule(style: .continuous).fill(StageBar.color(s.stage))
                        .frame(width: max(room * CGFloat(s.minutes) / total, 8))
                }
            }
            .modifier(DrawIn(play: play, delay: 0.3))
        }
        .accessibilityHidden(true)
    }
}

/// The last nights of sleep as capsules, tonight's in full colour, the median as a dotted line.
struct NightsBars: View {
    var nights: [Double?]
    var baseline: Double?
    var play: Bool

    var body: some View {
        GeometryReader { g in
            let n = max(nights.count, 1)
            let w: CGFloat = 12
            let top = max((nights.compactMap { $0 } + [baseline].compactMap { $0 }).max() ?? 1, 1)
            let h: (Double) -> CGFloat = { max(CGFloat($0 / top) * g.size.height, w) }
            ZStack(alignment: .bottomLeading) {
                if let b = baseline {
                    Path { p in
                        p.move(to: CGPoint(x: 0, y: g.size.height - h(b)))
                        p.addLine(to: CGPoint(x: g.size.width, y: g.size.height - h(b)))
                    }
                    .stroke(Palette.text3.opacity(0.8), style: StrokeStyle(lineWidth: 1.5, lineCap: .round, dash: [0.1, 5]))
                }
                HStack(alignment: .bottom, spacing: (g.size.width - w * CGFloat(n)) / CGFloat(max(n - 1, 1))) {
                    ForEach(nights.indices, id: \.self) { i in
                        if let v = nights[i] {
                            Capsule(style: .continuous)
                                .fill(Metric.sleep.color.opacity(i == nights.count - 1 ? 1 : 0.4))
                                .frame(width: w, height: play ? h(v) : w)
                                .motion(ChartMotion.grow(0.25 + Double(i) * 0.05), value: play)
                        } else {
                            Circle().strokeBorder(Palette.text3, lineWidth: 2).frame(width: w * 0.6, height: w * 0.6).frame(width: w)
                        }
                    }
                }
                .frame(width: g.size.width, alignment: .leading)
            }
        }
        .accessibilityHidden(true)
    }
}

// MARK: day

struct DaySection: View {
    var summary: DaySummary
    var play: Bool
    var onOpen: (TodayDestination, CGRect) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s12) {
            HStack(alignment: .top, spacing: Space.s16) {
                if let r = summary.heartRate {
                    stat(.heartRate, L("today.day.hr"), "\(r.lowerBound)–\(r.upperBound)", "bpm", .pulse)
                }
                if let s = summary.steps {
                    stat(.steps, L("today.steps.caption.title"), NumberFormatter.localizedString(from: NSNumber(value: s), number: .decimal), "", .steps)
                }
            }
            Text(L("today.insight.coverage", summary.hoursRead, summary.hoursElapsed))
                .font(.system(size: 13)).foregroundStyle(Palette.text3)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func stat(_ m: Metric, _ label: String, _ value: String, _ unit: String, _ d: TodayDestination) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            MetricMarkShape(metric: m, size: 16)
            HStack(alignment: .firstTextBaseline, spacing: 5) {
                Text(value).font(.monoFixed(.light, 30)).foregroundStyle(Palette.text1).lineLimit(1).minimumScaleFactor(0.6)
                if !unit.isEmpty { Text(unit).font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3) }
            }
            Text(label).font(.system(size: 13, weight: .medium)).foregroundStyle(Palette.text3)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .opens(d, a11y: "\(label), \(value) \(unit)", onOpen)
    }
}
