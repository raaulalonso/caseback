import SwiftUI

/// The first-launch flow (the design notes section A): welcome, Bluetooth, mount, pair, contact check,
/// Apple Health, done. Behind everything the blob field tells the story in motion (02 section 10).
struct OnboardingView: View {
    @State var model: OnboardingModel
    var onFinish: () -> Void

    @Environment(\.openURL) private var openURL
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var stage: BlobStage?
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        GeometryReader { geo in
            ZStack {
                if model.step == .mount { MountWatch(stage: stage).transition(.opacity) }
                BlobField(pose: model.pose, inputs: model.blobInputs, beat: model.beat, stage: stage)
                    .ignoresSafeArea()
                VStack(alignment: .leading, spacing: 0) {
                    topBar
                    Group {
                        if typeSize.isAccessibilitySize {
                            // Very large text: the step scrolls instead of squeezing the blob stage.
                            ScrollView { content }.scrollBounceBehavior(.basedOnSize)
                        } else {
                            content
                        }
                    }
                    .id(contentKey)
                    .transition(.opacity.animation(.easeOut(duration: 0.18)))
                }
                .padding(.horizontal, Space.margin)
                .opacity(model.step == .done && !model.finaleSettled ? 0 : 1)
                .animation(.easeOut(duration: 0.25), value: model.finaleSettled)
            }
        }
        .background(Palette.ground)
        .preferredColorScheme(.dark)
        .dynamicTypeSize(...DynamicTypeSize.accessibility3)
        .onPreferenceChange(StageKey.self) { rect in
            stage = rect.map { BlobStage(minY: $0.minY, maxY: $0.maxY) }
        }
        .onAppear { Haptics.prepare() }
        .onChange(of: model.finished) { _, done in if done { onFinish() } }
    }

    // MARK: top bar

    @ViewBuilder
    private var topBar: some View {
        if model.step == .welcome || model.step == .done {
            Color.clear.frame(height: Space.hit)
        } else {
            TopBar(index: model.progressIndex, canGoBack: model.canGoBack) { model.back() }
                .transition(.opacity)
        }
    }

    private var contentKey: String {
        switch model.step {
        case .pair:
            switch model.pair {
            case .idle, .searching: return "pair.search"
            case .found: return "pair.found"
            case .pairing: return "pair.pairing"
            case .paired: return "pair.paired"
            case .failed(let f): return "pair.failed.\(f)"
            }
        case .bluetooth: return "bluetooth.\(model.bluetooth)"
        default: return "step.\(model.step.rawValue)"
        }
    }

    // MARK: steps

    @ViewBuilder
    private var content: some View {
        switch model.step {
        case .welcome: welcome
        case .bluetooth: bluetooth
        case .mount: mount
        case .pair: pairStep
        case .contact: contact
        case .health: health
        case .done: done
        }
    }

    private func titleBlock(_ title: String, _ body: String? = nil, startIndex: Int = 0) -> some View {
        VStack(alignment: .leading, spacing: Space.s12) {
            Text(title)
                .font(.title)
                .foregroundStyle(Palette.text1)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
                .reveal(startIndex)
            if let body {
                Text(body)
                    .font(.body)
                    .foregroundStyle(Palette.text2)
                    .fixedSize(horizontal: false, vertical: true)
                    .reveal(startIndex + 1)
            }
        }
        .padding(.top, Space.s32)
    }

    private func actions<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        VStack(spacing: Space.s4) { content() }
            .padding(.bottom, Space.s12)
            .reveal(4)
    }

    private func frame<Middle: View, Actions: View>(
        title: String, body: String? = nil, @ViewBuilder middle: () -> Middle = { EmptyView() },
        @ViewBuilder actions a: () -> Actions
    ) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            titleBlock(title, body)
            StageRegion()
            middle()
            actions(a)
        }
    }

    // MARK: welcome

    private var welcome: some View {
        frame(title: L("welcome.title"), body: L("welcome.body")) {
            Button(L("welcome.cta")) { Haptics.step(); model.next() }.buttonStyle(.primary)
            Button(L("welcome.later")) { model.skip() }.buttonStyle(.textual)
        }
    }

    // MARK: bluetooth

    private var bluetooth: some View {
        let access = model.bluetooth
        let title: String
        let body: String
        switch access {
        case .denied: (title, body) = (L("bt.denied.title"), L("bt.denied.body"))
        case .off: (title, body) = (L("bt.off.title"), L("bt.off.body"))
        case .unsupported:
            #if targetEnvironment(simulator)
            (title, body) = (L("bt.title"), L("bt.body"))
            #else
            (title, body) = (L("bt.unsupported.title"), L("bt.unsupported.body"))
            #endif
        default: (title, body) = (L("bt.title"), L("bt.body"))
        }
        return frame(title: title, body: body) {
            switch access {
            case .denied:
                Button(L("action.openSettings")) { openSettings() }.buttonStyle(.primary)
                Button(L("action.checkAgain")) { model.refreshBluetooth() }.buttonStyle(.textual)
            case .off:
                Button(L("action.checkAgain")) { Task { await model.requestBluetooth() } }.buttonStyle(.primary)
            default:
                Button(L("bt.cta")) { Task { await model.requestBluetooth() } }.buttonStyle(.primary)
            }
        }
    }

    // MARK: mount

    private var mount: some View {
        VStack(alignment: .leading, spacing: 0) {
            titleBlock(L("mount.title"), L("mount.body"))
            StageRegion()
            Text(L("mount.warn"))
                .font(.callout)
                .foregroundStyle(Palette.text3)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.bottom, Space.s16)
                .reveal(3)
            actions {
                Button(L("action.next")) { Haptics.step(); model.next() }.buttonStyle(.primary)
            }
        }
    }

    // MARK: pair

    @ViewBuilder
    private var pairStep: some View {
        switch model.pair {
        case .idle, .searching:
            frame(title: L("pair.wake.title"), body: L("pair.wake.body")) {
                searchingStatus
            } actions: {
                Text(L("pair.hint")).font(.callout).foregroundStyle(Palette.text3).padding(.vertical, Space.s12)
            }
        case .found(let discs):
            frame(title: L("pair.found.title", discs[0].name), body: L("pair.found.body")) {
                if discs.count > 1 { discList(discs) }
            } actions: {
                Button(L("pair.cta")) { model.pairWith(discs[0]) }.buttonStyle(.primary)
            }
        case .pairing(let disc, let phase):
            frame(title: L("pair.pairing.title"), body: nil) {
                phaseStatus(phase)
            } actions: {
                Text(disc.name).font(.axis).foregroundStyle(Palette.text3).padding(.vertical, Space.s12)
            }
        case .paired(let disc):
            frame(title: L("pair.done.title"), body: pairedSummary(disc)) {
            } actions: {
                EmptyView()
            }
        case .failed(let failure):
            failureView(failure)
        }
    }

    private func pairedSummary(_ d: PairedDisc) -> String {
        let battery = d.batteryPercent.map { "≈ \($0) %" } ?? "≈ ?"
        return "\(d.name) · \(d.firmwareText) · \(battery)"
    }

    private var searchingStatus: some View {
        TimelineView(.periodic(from: .now, by: 1)) { ctx in
            let elapsed = Int(ctx.date.timeIntervalSince(model.searchStartedAt ?? ctx.date))
            VStack(alignment: .leading, spacing: Space.s8) {
                HStack {
                    Text(L("pair.search.label")).font(.callout).foregroundStyle(Palette.text2)
                    Spacer()
                    Text(String(format: "%d:%02d", elapsed / 60, elapsed % 60)).font(.axis).foregroundStyle(Palette.text3)
                        .monospacedDigit()
                }
                Rectangle().fill(Palette.hairline).frame(height: 1)
            }
            .padding(.bottom, Space.s16)
        }
        .reveal(2)
    }

    private func phaseStatus(_ phase: PairingPhase) -> some View {
        VStack(alignment: .leading, spacing: Space.s8) {
            Text(phaseText(phase)).font(.callout).foregroundStyle(Palette.text2)
                .id(phase)
                .transition(.opacity)
            GeometryReader { g in
                ZStack(alignment: .leading) {
                    Rectangle().fill(Palette.hairline).frame(height: 1)
                    Rectangle().fill(Palette.text1).frame(width: g.size.width * phase.progress, height: 1)
                        .animation(Motion.standard(0.5), value: phase)
                }
            }
            .frame(height: 1)
        }
        .padding(.bottom, Space.s16)
        .animation(Motion.standard, value: phase)
    }

    private func phaseText(_ p: PairingPhase) -> String {
        switch p {
        case .connecting: return L("pair.phase.connecting")
        case .securing: return L("pair.phase.securing")
        case .readingInfo: return L("pair.phase.info")
        case .settingClock: return L("pair.phase.clock")
        case .readingBattery: return L("pair.phase.battery")
        }
    }

    private func discList(_ discs: [DiscoveredDisc]) -> some View {
        VStack(spacing: 0) {
            ForEach(discs) { disc in
                Button { model.pairWith(disc) } label: {
                    HStack {
                        Text(disc.name).font(.mono(.regular, 15)).foregroundStyle(Palette.text1)
                        Spacer()
                        Text("\(Self.minus(disc.rssi)) dBm").font(.axis).foregroundStyle(Palette.text3)
                    }
                    .frame(minHeight: 48)
                    .overlay(alignment: .bottom) { Rectangle().fill(Palette.hairline).frame(height: 1) }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.bottom, Space.s16)
    }

    @ViewBuilder
    private func failureView(_ failure: PairingFailure) -> some View {
        switch failure {
        case .noDiscFound:
            frame(title: L("pair.none.title"), body: L("pair.none.body")) {
            } actions: {
                Button(L("action.searchAgain")) { model.retryPairing() }.buttonStyle(.primary)
            }
        case .bondMismatch(let name):
            frame(title: L("pair.bond.title"), body: L("pair.bond.body", name)) {
            } actions: {
                Button(L("action.openSettings")) { openSettings() }.buttonStyle(.primary)
                Button(L("action.tryAgain")) { model.retryPairing() }.buttonStyle(.textual)
            }
        case .needsNewerApp:
            frame(title: L("pair.version.title"), body: L("pair.version.body")) {
            } actions: {
                Button(L("action.tryAgain")) { model.retryPairing() }.buttonStyle(.secondary)
            }
        case .timedOut, .link:
            frame(title: L("pair.link.title"), body: L("pair.link.body")) {
            } actions: {
                Button(L("action.tryAgain")) { model.retryPairing() }.buttonStyle(.primary)
            }
        }
    }

    // MARK: contact

    private var contact: some View {
        let sample = model.signal
        let ok = sample.map { $0.word == .good || $0.word == .strong } ?? false
        return frame(title: L("contact.title"), body: model.contactStalled ? L("contact.none") : L("contact.body")) {
            VStack(spacing: 0) {
                contactRow(L("contact.signal"), value: sample.map { L("signal.\($0.word.rawValue)") } ?? "—", mark: ok)
                contactRow(L("contact.contact"), value: nil, bar: sample?.contact ?? 0)
                contactRow(L("contact.link"), value: sample.map { "\(Self.minus($0.rssi)) dBm" } ?? "—", mono: true)
            }
            .padding(.bottom, Space.s24)
            .reveal(2)
        } actions: {
            Button(L("contact.cta")) { Haptics.step(); model.next() }.buttonStyle(.primary).disabled(!ok)
            if model.contactStalled {
                Button(L("action.checkAgain")) { model.recheckContact() }.buttonStyle(.textual)
                Button(L("contact.skip")) { model.next() }.buttonStyle(.textual)
            }
        }
    }

    private func contactRow(_ label: String, value: String?, mark: Bool = false, bar: Double? = nil, mono: Bool = false)
        -> some View
    {
        HStack(spacing: Space.s8) {
            Text(label).font(.callout).foregroundStyle(Palette.text2)
            Spacer()
            if let bar { ContactBar(value: bar) }
            if let value {
                if mark { MetricMarkShape(metric: .heartRate, size: 8, color: Palette.text1) }
                Text(value).font(mono ? .mono(.regular, 15) : .callout).foregroundStyle(Palette.text1)
            }
        }
        .frame(minHeight: 40)
        .overlay(alignment: .bottom) { Rectangle().fill(Palette.hairline).frame(height: 1) }
        .accessibilityElement(children: .combine)
    }

    // MARK: health

    private var health: some View {
        frame(title: L("health.title"), body: L("health.body")) {
            VStack(spacing: 0) {
                ForEach(Metric.allCases.filter { $0 != .readiness }) { metric in healthRow(metric) }
            }
            .padding(.bottom, Space.s16)
            .reveal(2)
        } actions: {
            Button(model.healthAvailable ? L("health.cta") : L("action.next")) {
                Haptics.step()
                Task { await model.requestHealth() }
            }
            .buttonStyle(.primary)
            Button(L("health.later")) { model.next() }.buttonStyle(.textual)
        }
    }

    private func healthRow(_ metric: Metric) -> some View {
        let writes = metric.writtenToHealth
        let on = model.healthChoice.contains(metric)
        return Button { model.toggleHealth(metric) } label: {
            HStack(spacing: Space.s12) {
                MetricMarkShape(metric: metric, size: 10)
                    .opacity(writes && on ? 1 : 0.35)
                Text(L("metric.\(metric.rawValue)")).font(.body).foregroundStyle(writes ? Palette.text1 : Palette.text3)
                Spacer()
                Text(writes ? (on ? L("health.writes") : L("health.off")) : L("health.never"))
                    .font(.axis)
                    .foregroundStyle(writes && on ? Palette.text1 : Palette.text3)
            }
            .frame(minHeight: 44)
            .overlay(alignment: .bottom) { Rectangle().fill(Palette.hairline).frame(height: 1) }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!writes)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L("metric.\(metric.rawValue)"))
        .accessibilityValue(writes ? (on ? L("health.writes") : L("health.off")) : L("health.never"))
        .accessibilityAddTraits(writes ? .isButton : [])
    }

    // MARK: done

    private var done: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer(minLength: Space.s48)
            Spacer().frame(height: 120)
            titleBlock(L("done.title"), L("done.body"))
            Spacer(minLength: Space.s16)
            actions {
                Button(L("done.cta")) { Haptics.success(); model.complete() }.buttonStyle(.primary)
            }
        }
    }

    /// Negative numbers use the true minus sign (04 section 8).
    static func minus(_ n: Int) -> String { n < 0 ? "\u{2212}\(-n)" : "\(n)" }

    private func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
    }
}
