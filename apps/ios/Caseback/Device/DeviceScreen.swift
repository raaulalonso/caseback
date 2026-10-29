import SwiftUI

/// Device: the disc in a sentence, its battery, then one line per thing you can do. Same language as Today and Trends: on the
/// black, hairlines, full width, no icons; the only thing that animates is the battery chart. Versions and identifiers live
/// behind the "i".
struct DeviceScreen: View {
    @Bindable var model: DeviceModel
    var onSetup: () -> Void
    @State private var play = false

    private static let side: CGFloat = 16

    var body: some View {
        let s = model.snapshot
        VStack(spacing: 0) {
            if s.paired {
                header(s).padding(.horizontal, Self.side).padding(.top, Space.s8).padding(.bottom, Space.s12)
                // Fixed on a tall phone; scrolls only where the rows do not fit (iPhone SE).
                ScrollView {
                    VStack(spacing: 0) {
                        hero(s)
                        rule
                        rows(s)
                        demoRestart
                    }
                    .padding(.horizontal, Self.side)
                }
                .scrollBounceBehavior(.basedOnSize)
                .scrollIndicators(.hidden)
            } else {
                unpaired
            }
        }
        .task { replay() }
        .onChange(of: model.snapshot.battery) { _, _ in replay() }
        .sheet(item: $model.sheet) { sheet in
            switch sheet {
            case .mode: ModeSheet(model: model)
            case .update: UpdateSheet(model: model)
            case .health: HealthSheet(model: model)
            case .data: DataSheet(model: model)
            case .experimental: ExperimentalSheet(model: model)
            case .forget: ForgetSheet(model: model, onForget: onSetup)
            case .about: AboutSheet(snapshot: model.snapshot)
            }
        }
    }

    // MARK: header

    private func header(_ s: DeviceSnapshot) -> some View {
        ZStack(alignment: .trailing) {
            Text(s.name)
                .font(.system(size: 15, weight: .medium)).foregroundStyle(Palette.text2)
                .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
            InfoButton { model.sheet = .about }.offset(x: 10)
        }
        .frame(height: 28)
    }

    // MARK: hero

    private func hero(_ s: DeviceSnapshot) -> some View {
        let status = model.status
        return VStack(alignment: .leading, spacing: 0) {
            Text(status.headline)
                .font(.system(size: 34, weight: .semibold))
                .foregroundStyle(status.needsAction ? Palette.alert : Palette.text1)
                .lineLimit(2).minimumScaleFactor(0.7)
                .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                .padding(.top, Space.s12)
            if !status.detail.isEmpty {
                Text(status.detail)
                    .font(.system(size: 16)).foregroundStyle(Palette.text2)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 6)
            }
            if status.needsAction && s.link == .bondLost {
                Button(L("device.status.bondLost.cta"), action: onSetup)
                    .buttonStyle(.textual).padding(.leading, -Space.s8)
            }
            battery(s).padding(.top, Space.s24)
        }
        .padding(.bottom, Space.s20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    /// Small name, the number, then the charge as a thin capsule that fills in.
    private func battery(_ s: DeviceSnapshot) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            SectionTitle(text: L("device.battery"))
            HStack(alignment: .firstTextBaseline, spacing: Space.s12) {
                batteryNumeral(s.battery)
                if let word = DeviceInsights.chargeWord(s.battery) {
                    Text(word).font(.system(size: 15, weight: .medium)).foregroundStyle(Palette.text2)
                }
            }
            BatteryBar(
                fraction: Double(s.battery.percent ?? 0) / 100,
                low: (s.battery.percent ?? 100) <= DeviceInsights.lowBattery && s.battery.charge != .charging,
                play: play
            )
            .frame(height: 8).padding(.top, 4)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L("device.battery") + ", " + DeviceInsights.batteryText(s.battery) + " " + (DeviceInsights.chargeWord(s.battery) ?? ""))
    }

    /// "≈ 64 %" with the approximation and the unit small, so the number leads.
    private func batteryNumeral(_ b: BatteryReading) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            if let p = b.percent {
                Text("≈").font(.monoFixed(.regular, 20)).foregroundStyle(Palette.text3)
                Text("\(p)").font(.monoFixed(.light, 40)).foregroundStyle(Palette.text1)
                Text("%").font(.monoFixed(.regular, 20)).foregroundStyle(Palette.text3)
            } else {
                Text("–").font(.monoFixed(.light, 40)).foregroundStyle(Palette.text1)
            }
        }
    }

    // MARK: rows

    /// One line per thing you can do: name left, how it is now right, a hairline between them.
    private func rows(_ s: DeviceSnapshot) -> some View {
        VStack(spacing: 0) {
            row(L("device.row.mode"), s.mode.name, .mode, id: "mode")
            row(L("device.row.update"), DeviceInsights.updateValue(s.firmware), .update, id: "update", highlight: isAvailable(s.firmware))
            row(L("device.row.health"), DeviceInsights.healthValue(s.health), .health, id: "health")
            row(L("device.row.data"), L("device.row.data.value"), .data, id: "data")
            row(L("device.row.exp"), DeviceInsights.experimentalValue(s), .experimental, id: "experimental")
            Button {
                Haptics.tap()
                model.sheet = .forget
            } label: {
                Text(L("device.row.forget"))
                    .font(.system(size: 16)).foregroundStyle(Palette.alert)
                    .frame(maxWidth: .infinity, minHeight: 56, alignment: .leading)
                    .contentShape(Rectangle())
            }
            .buttonStyle(SectionPress())
            .accessibilityIdentifier("device.row.forget")
        }
    }

    /// TEMPORARY, to show the app: starts onboarding again. Remove before shipping.
    private var demoRestart: some View {
        Button {
            Haptics.tap()
            onSetup()
        } label: {
            Text(L("device.demo.restart"))
                .font(.system(size: 13)).foregroundStyle(Palette.text3)
                .frame(maxWidth: .infinity, minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(SectionPress())
        .padding(.top, Space.s8).padding(.bottom, Space.s8)
        .accessibilityIdentifier("device.demo.restart")
    }

    private func isAvailable(_ f: FirmwareState) -> Bool {
        if case .available = f { return true }
        return false
    }

    private func row(_ title: String, _ value: String, _ sheet: DeviceSheet, id: String, highlight: Bool = false) -> some View {
        Button {
            Haptics.tap()
            model.sheet = sheet
        } label: {
            HStack(spacing: Space.s12) {
                Text(title).font(.system(size: 17)).foregroundStyle(Palette.text1)
                Spacer(minLength: 0)
                Text(value)
                    .font(.system(size: 15, weight: highlight ? .semibold : .regular))
                    .foregroundStyle(highlight ? Palette.text1 : Palette.text2)
                    .lineLimit(1).minimumScaleFactor(0.7)
            }
            .frame(minHeight: 56)
            .contentShape(Rectangle())
        }
        .buttonStyle(SectionPress())
        .overlay(alignment: .bottom) { Rectangle().fill(Palette.hairline).frame(height: 1 / UIScreen.main.scale) }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(title), \(value)")
        .accessibilityIdentifier("device.row.\(id)")
        .accessibilityAddTraits(.isButton)
    }

    private var rule: some View { Rectangle().fill(Palette.hairline).frame(height: 1 / UIScreen.main.scale) }

    private func replay() {
        var t = Transaction()
        t.disablesAnimations = true
        withTransaction(t) { play = false }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.06) { play = true }
    }

    // MARK: no disc

    private var unpaired: some View {
        VStack(alignment: .leading, spacing: Space.s16) {
            Spacer()
            Text(L("device.unpaired")).font(.title).foregroundStyle(Palette.text1)
            Text(L("device.unpaired.body")).font(.body).foregroundStyle(Palette.text2)
            Button(L("today.setup.cta")) { onSetup() }.buttonStyle(.primary).padding(.top, Space.s8)
            Spacer()
        }
        .padding(.horizontal, Space.margin)
    }
}

/// The charge as a thin capsule that fills in; it turns to the alert colour when the battery is low.
struct BatteryBar: View {
    var fraction: Double
    var low: Bool
    var play: Bool

    var body: some View {
        GeometryReader { g in
            ZStack(alignment: .leading) {
                Capsule(style: .continuous).fill(Palette.hairline)
                Capsule(style: .continuous)
                    .fill(low ? Palette.alert : Palette.text1)
                    .frame(width: max(g.size.height, g.size.width * (play ? min(max(fraction, 0), 1) : 0)))
                    .opacity(fraction > 0 ? 1 : 0)
                    .motion(ChartMotion.grow(0.1), value: play)
            }
        }
        .accessibilityHidden(true)
    }
}
