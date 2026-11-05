import SwiftUI
import WidgetKit

// The widgets, drawn once and used by the extension and by the in-app gallery (`-widget-gallery YES`). Same language as the app:
// on the black, hairlines, mono numerals, the metric colour only on the number and the line, plain words for the zone. A widget never
// animates and never shows more than its size can hold: small is one number, medium is three scores.

// MARK: pieces

/// The score as a short ruler: a thin capsule filled up to the score, ticks at the zone limits, a dot where you are.
struct ScoreRuler: View {
    var score: Int
    var kind: ScoreKind
    var color: Color

    var body: some View {
        GeometryReader { g in
            let t = ScoreZone.thresholds(kind)
            let x: (Int) -> CGFloat = { CGFloat($0) / 100 * (g.size.width - 8) + 4 }
            ZStack(alignment: .leading) {
                Capsule(style: .continuous).fill(Palette.hairline).frame(height: 6)
                Capsule(style: .continuous).fill(color).frame(width: max(x(score), 6), height: 6)
                ForEach([t.low, t.high], id: \.self) { limit in
                    Rectangle().fill(Palette.text3).frame(width: 1.5, height: 12).position(x: x(limit), y: g.size.height / 2)
                }
                Circle().fill(color).frame(width: 12, height: 12).position(x: x(score), y: g.size.height / 2)
            }
        }
        .accessibilityHidden(true)
    }
}

private struct HairlineV: View {
    @Environment(\.displayScale) private var scale
    var body: some View { Rectangle().fill(Palette.hairline).frame(width: 1 / scale) }
}

private struct HairlineH: View {
    @Environment(\.displayScale) private var scale
    var body: some View { Rectangle().fill(Palette.hairline).frame(height: 1 / scale) }
}

/// The words and numbers of one metric, shared by the small widget, the medium columns and the lock screen.
struct WidgetFigure {
    var value: String
    var unit: String
    /// The zone word or the way it compares with your normal.
    var word: String?
    /// Scores wear the metric colour; the rest are white.
    var scoreColor: Bool

    static func make(_ kind: WidgetMetricKind, _ s: WidgetSnapshot) -> WidgetFigure? {
        switch kind {
        case .readiness:
            guard let v = s.recoveryScore else { return nil }
            return WidgetFigure(value: "\(v)", unit: "", word: ScoreZone.of(v, .recovery).word(.recovery), scoreColor: true)
        case .sleep:
            guard let v = s.sleepScore else { return nil }
            var word = ScoreZone.of(v, .sleep).word(.sleep)
            if let m = s.sleepMinutes {
                let d = TodayFormat.duration(minutes: m)
                word += " · " + (d.unit.isEmpty ? d.value : "\(d.value) \(d.unit)")
            }
            return WidgetFigure(value: "\(v)", unit: "", word: word, scoreColor: true)
        case .steps:
            guard let v = s.steps else { return nil }
            return WidgetFigure(
                value: NumberFormatter.localizedString(from: NSNumber(value: v), number: .decimal), unit: "", word: L("trends.partial"),
                scoreColor: false)
        case .pulse:
            guard let v = s.pulseBPM else { return nil }
            return WidgetFigure(
                value: "\(v)", unit: "bpm", word: s.pulseAgeMinutes.map { TodayFormat.age(minutes: $0) }, scoreColor: false)
        case .restingHR:
            guard let r = s.restingHR else { return nil }
            return WidgetFigure(value: "\(r.value)", unit: "bpm", word: direction(r), scoreColor: false)
        case .hrv:
            guard let r = s.hrv else { return nil }
            return WidgetFigure(value: "\(r.value)", unit: "ms", word: direction(r), scoreColor: false)
        case .skinTemp:
            guard let t = s.skinTemp else { return nil }
            if let n = t.calibratingNights { return WidgetFigure(value: "\(n)/5", unit: L("today.temp.nights"), word: L("today.status.calibrating"), scoreColor: false) }
            guard let v = t.value else { return nil }
            return WidgetFigure(value: v, unit: "°C", word: L("today.status.trend"), scoreColor: false)
        case .spo2:
            guard let t = s.spo2, let v = t.value else { return nil }
            return WidgetFigure(value: v, unit: "%", word: L("today.status.trend"), scoreColor: false)
        }
    }

    private static func direction(_ r: WidgetSignal) -> String? {
        guard let b = r.baseline else { return nil }
        return SignalStatus.direction(delta: Double(r.delta), baseline: b)
    }
}

// MARK: small

/// One metric, as large as it can be: its name and mark, the number, a word, and the line that shows where it sits.
struct SmallWidgetView: View {
    var snapshot: WidgetSnapshot
    var kind: WidgetMetricKind
    var now: Date

    var body: some View {
        let f = WidgetFreshness.of(updatedAt: snapshot.updatedAt, now: now)
        let ph = snapshot.placeholder(for: kind, freshness: f)
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .center) {
                Text(kind.name).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.text3).lineLimit(1).minimumScaleFactor(0.8)
                Spacer(minLength: 4)
                MetricMarkShape(metric: kind.metric, size: 12).widgetAccentable()
            }
            Spacer(minLength: 2)
            if let ph { placeholder(ph) } else if let fig = WidgetFigure.make(kind, snapshot) { content(fig, f).frame(maxHeight: .infinity) }
        }
        .dynamicTypeSize(...DynamicTypeSize.large)
    }

    @ViewBuilder private func content(_ fig: WidgetFigure, _ f: WidgetFreshness) -> some View {
        let color = kind.metric.color
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(fig.value).font(.monoFixed(.light, 42)).foregroundStyle(fig.scoreColor ? color : Palette.text1)
                    .lineLimit(1).minimumScaleFactor(0.5).widgetAccentable().privacySensitive()
                if !fig.unit.isEmpty { Text(fig.unit).font(.monoFixed(.regular, 11)).foregroundStyle(Palette.text3) }
            }
            if let w = fig.word {
                Text(w).font(.system(size: 13, weight: .semibold)).foregroundStyle(fig.scoreColor ? color : Palette.text2)
                    .lineLimit(1).minimumScaleFactor(0.7)
            }
            Spacer(minLength: 6)
            chart.frame(height: 28)
            footer(f).padding(.top, 4)
        }
        .opacity(f.isDim ? 0.55 : 1)
    }

    @ViewBuilder private var chart: some View {
        switch kind {
        case .readiness: if let s = snapshot.recoveryScore { ScoreRuler(score: s, kind: .recovery, color: kind.metric.color) }
        case .sleep: if let s = snapshot.sleepScore { ScoreRuler(score: s, kind: .sleep, color: kind.metric.color) }
        case .steps: ThickBars(values: snapshot.stepBins, metric: .steps, play: true)
        case .pulse: ThickLine(series: snapshot.pulseRecent, metric: .heartRate, baseline: nil, play: true, dot: 7)
        case .restingHR:
            if let r = snapshot.restingHR { ThickLine(series: r.series, metric: .heartRate, baseline: r.baseline, play: true, dot: 7) }
        case .hrv:
            if let r = snapshot.hrv { ThickLine(series: r.series, metric: .hrv, baseline: r.baseline, play: true, dot: 7) }
        case .skinTemp:
            if let t = snapshot.skinTemp {
                if let n = t.calibratingNights { Dots(done: n, total: 5, color: Metric.skinTemp.color, size: 9, play: true) }
                else { ThickLine(series: t.series, metric: .skinTemp, baseline: nil, dashed: true, play: true, dot: 7) }
            }
        case .spo2:
            if let t = snapshot.spo2 { ThickLine(series: t.series, metric: .spo2, baseline: nil, dashed: true, play: true, dot: 7) }
        }
    }

    /// The one line under the chart: the alert (as on Today), or how old the numbers are.
    @ViewBuilder private func footer(_ f: WidgetFreshness) -> some View {
        if let a = snapshot.alertText() {
            Text(a).font(.system(size: 11, weight: .medium)).foregroundStyle(Palette.alert).lineLimit(1).minimumScaleFactor(0.7)
        } else if let t = f.text(updatedAt: snapshot.updatedAt) {
            Text(t).font(.system(size: 11)).foregroundStyle(Palette.text3).lineLimit(1)
        } else {
            Color.clear.frame(height: 14)
        }
    }

    @ViewBuilder private func placeholder(_ p: WidgetPlaceholder) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            switch p {
            case .unpaired:
                Spacer(minLength: 0)
                Text(L("widget.unpaired.title")).font(.system(size: 18, weight: .semibold)).foregroundStyle(Palette.text1)
                Text(L("widget.unpaired.body")).font(.system(size: 13)).foregroundStyle(Palette.text2)
            case .calibrating(let day):
                Spacer(minLength: 0)
                Dots(done: day, total: 7, color: kind.metric.color, size: 8, play: true).frame(height: 14)
                Text(L("widget.calibrating", day)).font(.system(size: 14, weight: .semibold)).foregroundStyle(Palette.text1)
            case .noData:
                Spacer(minLength: 0)
                Text("—").font(.monoFixed(.light, 42)).foregroundStyle(Palette.text3)
                Text(L("widget.nodata")).font(.system(size: 13)).foregroundStyle(Palette.text2)
            case .expired:
                Spacer(minLength: 0)
                Text("—").font(.monoFixed(.light, 42)).foregroundStyle(Palette.text3)
                Text(WidgetFreshness.expired.text(updatedAt: snapshot.updatedAt) ?? "").font(.system(size: 13)).foregroundStyle(Palette.text2)
                    .lineLimit(2)
            }
            Spacer(minLength: 0)
        }
    }
}

// MARK: medium

/// The three scores of the day side by side, the way Today puts them, and one line under them.
struct MediumWidgetView: View {
    var snapshot: WidgetSnapshot
    var now: Date

    private static let kinds: [WidgetMetricKind] = [.readiness, .sleep, .steps]

    var body: some View {
        let f = WidgetFreshness.of(updatedAt: snapshot.updatedAt, now: now)
        Group {
            if !snapshot.paired {
                VStack(alignment: .leading, spacing: 6) {
                    Spacer(minLength: 0)
                    Text(L("widget.unpaired.title")).font(.system(size: 22, weight: .semibold)).foregroundStyle(Palette.text1)
                    Text(L("widget.unpaired.body")).font(.system(size: 14)).foregroundStyle(Palette.text2)
                    Spacer(minLength: 0)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                VStack(spacing: 0) {
                    HStack(alignment: .top, spacing: 0) {
                        ForEach(Array(Self.kinds.enumerated()), id: \.element) { i, k in
                            Link(destination: WidgetLink.metric(k.destination).url) { column(k, f) }
                                .frame(maxWidth: .infinity, alignment: .leading)
                            if i < Self.kinds.count - 1 { HairlineV().padding(.horizontal, 10) }
                        }
                    }
                    .frame(maxHeight: .infinity)
                    HairlineH().padding(.bottom, 8)
                    footer(f)
                }
            }
        }
        .dynamicTypeSize(...DynamicTypeSize.large)
    }

    private func column(_ k: WidgetMetricKind, _ f: WidgetFreshness) -> some View {
        let fig = f.showsNumbers ? WidgetFigure.make(k, snapshot) : nil
        let color = k.metric.color
        return VStack(alignment: .leading, spacing: 2) {
            Text(k.name).font(.system(size: 12, weight: .medium)).foregroundStyle(Palette.text3).lineLimit(1).minimumScaleFactor(0.7)
            if let fig {
                Text(fig.value).font(.monoFixed(.light, 32)).foregroundStyle(fig.scoreColor ? color : Palette.text1)
                    .lineLimit(1).minimumScaleFactor(0.5).widgetAccentable().privacySensitive().padding(.top, 4)
                if let w = fig.word {
                    Text(w).font(.system(size: 12, weight: .semibold)).foregroundStyle(fig.scoreColor ? color : Palette.text2)
                        .lineLimit(2).minimumScaleFactor(0.75)
                }
            } else if k == .readiness, let d = snapshot.recoveryCalibratingDay, f.showsNumbers {
                Text("\(d)/7").font(.monoFixed(.light, 32)).foregroundStyle(Palette.text2).padding(.top, 4)
                Text(L("today.status.calibrating")).font(.system(size: 12, weight: .semibold)).foregroundStyle(Palette.text2)
            } else {
                Text("—").font(.monoFixed(.light, 32)).foregroundStyle(Palette.text3).padding(.top, 4)
                Text(L("widget.nodata")).font(.system(size: 12)).foregroundStyle(Palette.text3)
            }
        }
        .opacity(f.isDim ? 0.55 : 1)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// The alert if there is one; otherwise how old it is when it is not fresh; otherwise the sentence Today starts with.
    @ViewBuilder private func footer(_ f: WidgetFreshness) -> some View {
        if let a = snapshot.alertText() {
            line(a, Palette.alert, .medium)
        } else if let t = f.text(updatedAt: snapshot.updatedAt) {
            line(f == .expired ? t : L("device.status.synced", t), Palette.text3, .regular)
        } else if let h = snapshot.headline {
            line(h, Palette.text2, .regular)
        } else {
            Color.clear.frame(height: 16)
        }
    }

    private func line(_ text: String, _ color: Color, _ weight: Font.Weight) -> some View {
        Text(text).font(.system(size: 13, weight: weight)).foregroundStyle(color).lineLimit(1).minimumScaleFactor(0.75)
            .frame(maxWidth: .infinity, alignment: .leading).frame(height: 16)
    }
}

// MARK: lock screen

/// Lock Screen, circular: the score on the system gauge. Vibrant: no colour, so the number and the ring carry it.
struct CircularWidgetView: View {
    var snapshot: WidgetSnapshot
    var kind: WidgetMetricKind
    var now: Date

    var body: some View {
        let f = WidgetFreshness.of(updatedAt: snapshot.updatedAt, now: now)
        let score = kind == .sleep ? snapshot.sleepScore : (kind == .readiness ? snapshot.recoveryScore : nil)
        Group {
            if snapshot.paired, f.showsNumbers, let fig = WidgetFigure.make(kind, snapshot) {
                if let score {
                    Gauge(value: Double(score), in: 0...100) { Text(kind.name.prefix(1)) } currentValueLabel: {
                        Text(fig.value).privacySensitive()
                    }
                    .gaugeStyle(.accessoryCircular)
                } else {
                    VStack(spacing: 0) {
                        Text(fig.value).font(.system(size: 22, weight: .semibold, design: .rounded)).privacySensitive().minimumScaleFactor(0.5)
                        if !fig.unit.isEmpty { Text(fig.unit).font(.system(size: 10)) }
                    }
                }
            } else {
                Text("—").font(.system(size: 22, weight: .semibold))
            }
        }
        .opacity(f.isDim ? 0.6 : 1)
        .widgetAccentable()
    }
}

/// Lock Screen, rectangular: recovery with its word, and sleep or the alert under it.
struct RectangularWidgetView: View {
    var snapshot: WidgetSnapshot
    var now: Date

    var body: some View {
        let f = WidgetFreshness.of(updatedAt: snapshot.updatedAt, now: now)
        VStack(alignment: .leading, spacing: 1) {
            if !snapshot.paired {
                Text(L("widget.unpaired.title")).font(.system(size: 14, weight: .semibold))
                Text(L("widget.unpaired.body")).font(.system(size: 12)).opacity(0.7)
            } else if f.showsNumbers, let r = WidgetFigure.make(.readiness, snapshot) {
                Text(WidgetMetricKind.readiness.name).font(.system(size: 12, weight: .medium)).opacity(0.7)
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(r.value).font(.monoFixed(.regular, 26)).privacySensitive().widgetAccentable()
                    Text(r.word ?? "").font(.system(size: 14, weight: .semibold))
                }
                line3(f)
            } else {
                Text(WidgetMetricKind.readiness.name).font(.system(size: 12, weight: .medium)).opacity(0.7)
                Text("—").font(.monoFixed(.regular, 26))
                Text(f.text(updatedAt: snapshot.updatedAt) ?? L("widget.nodata")).font(.system(size: 12)).opacity(0.7).lineLimit(1)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .opacity(f.isDim ? 0.6 : 1)
    }

    @ViewBuilder private func line3(_ f: WidgetFreshness) -> some View {
        if let a = snapshot.alertText() {
            Text(a).font(.system(size: 12, weight: .medium)).lineLimit(1).minimumScaleFactor(0.7)
        } else if let t = f.text(updatedAt: snapshot.updatedAt) {
            Text(t).font(.system(size: 12)).opacity(0.7).lineLimit(1)
        } else if let s = WidgetFigure.make(.sleep, snapshot) {
            Text("\(WidgetMetricKind.sleep.name) \(s.value)").font(.system(size: 12)).opacity(0.7).lineLimit(1).privacySensitive()
        }
    }
}

/// Lock Screen, inline: one line of text, one tap.
struct InlineWidgetView: View {
    var snapshot: WidgetSnapshot
    var now: Date

    var body: some View {
        let f = WidgetFreshness.of(updatedAt: snapshot.updatedAt, now: now)
        Text(Self.text(snapshot, f)).privacySensitive()
    }

    static func text(_ s: WidgetSnapshot, _ f: WidgetFreshness) -> String {
        guard s.paired else { return L("widget.unpaired.title") }
        guard f.showsNumbers else { return L("widget.expired.short") }
        var parts: [String] = []
        if let r = s.recoveryScore { parts.append("\(WidgetMetricKind.readiness.name) \(r)") }
        if let sl = s.sleepScore { parts.append("\(WidgetMetricKind.sleep.name) \(sl)") }
        return parts.isEmpty ? L("widget.nodata") : parts.joined(separator: " · ")
    }
}
