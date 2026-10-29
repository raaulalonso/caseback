import SwiftUI

// The detail screens of the Device tab. Each is a sheet in the language of the explanations: black-grey ground, one title,
// plain words first, controls as capsules.

/// Shared frame: title, content, same presentation as `InfoSheet`.
private struct DeviceSheetFrame<Content: View>: View {
    var title: String
    var detents: Set<PresentationDetent> = [.large]
    @ViewBuilder var content: () -> Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Space.s16) {
                Text(title).font(.system(size: 22, weight: .semibold)).foregroundStyle(Palette.text1)
                content()
            }
            .padding(.horizontal, Space.margin)
            .padding(.top, Space.s32)
            .padding(.bottom, Space.s24)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .scrollBounceBehavior(.basedOnSize)
        .presentationDetents(detents)
        .presentationDragIndicator(.visible)
        .presentationBackground(Palette.tile)
        .presentationCornerRadius(Radius.hero)
    }
}

private extension Text {
    func body1() -> some View { font(.system(size: 17)).foregroundStyle(Palette.text1).fixedSize(horizontal: false, vertical: true) }
    func body2() -> some View { font(.system(size: 15)).foregroundStyle(Palette.text2).fixedSize(horizontal: false, vertical: true) }
}

/// A switch drawn as a capsule with a dot, like the rest of the controls.
private struct CapsuleToggle: View {
    var title: String
    var detail: String?
    @Binding var isOn: Bool
    var enabled = true

    var body: some View {
        Button {
            Haptics.tick()
            withAnimation(.spring(response: 0.3, dampingFraction: 0.75)) { isOn.toggle() }
        } label: {
            HStack(alignment: .top, spacing: Space.s16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(title).font(.system(size: 17)).foregroundStyle(Palette.text1)
                    if let detail { Text(detail).body2() }
                }
                Spacer(minLength: 0)
                ZStack(alignment: isOn ? .trailing : .leading) {
                    Capsule(style: .continuous).fill(isOn ? Palette.text1 : Palette.hairline).frame(width: 52, height: 30)
                    Circle().fill(isOn ? Palette.ground : Palette.text2).frame(width: 22, height: 22).padding(.horizontal, 4)
                }
                .padding(.top, 2)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(SectionPress())
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.4)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(isOn ? [.isButton, .isSelected] : .isButton)
    }
}

/// One choice among a few, as capsules in a row.
private struct Choices<T: Hashable & Identifiable>: View {
    var options: [T]
    var label: (T) -> String
    @Binding var selection: T

    var body: some View {
        HStack(spacing: Space.s8) {
            ForEach(options) { o in
                let on = o == selection
                Button {
                    guard !on else { return }
                    Haptics.tick()
                    selection = o
                } label: {
                    Text(label(o))
                        .font(.system(size: 15, weight: .medium))
                        .foregroundStyle(on ? Palette.ground : Palette.text2)
                        .padding(.horizontal, Space.s16).frame(minHeight: 40)
                        .background {
                            if on { Capsule(style: .continuous).fill(Palette.text1) } else {
                                Capsule(style: .continuous).strokeBorder(Palette.text3, lineWidth: 1)
                            }
                        }
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }
}

private var hairline: some View { Rectangle().fill(Palette.hairline).frame(height: 1 / UIScreen.main.scale) }

// MARK: mode

struct ModeSheet: View {
    var model: DeviceModel

    var body: some View {
        DeviceSheetFrame(title: L("device.row.mode")) {
            Text(L("device.mode.intro")).body2()
            VStack(spacing: 6) {
                ForEach(DeviceMode.allCases) { m in
                    let current = m == model.snapshot.mode
                    Button {
                        guard !current else { return }
                        Haptics.tap()
                        withAnimation(Motion.standard) { model.setMode(m) }
                    } label: {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(m.name).font(.system(size: 17, weight: .semibold))
                                .foregroundStyle(current ? Palette.ground : Palette.text1)
                            Text(m.about).font(.system(size: 14))
                                .foregroundStyle(current ? Palette.ground.opacity(0.75) : Palette.text2)
                                .multilineTextAlignment(.leading)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, Space.s16).padding(.vertical, Space.s12)
                        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(current ? Palette.text1 : Palette.control))
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(SectionPress())
                    .accessibilityIdentifier("device.mode.\(m.key)")
                    .accessibilityAddTraits(current ? [.isButton, .isSelected] : .isButton)
                }
            }
        }
    }
}

// MARK: update

struct UpdateSheet: View {
    var model: DeviceModel
    @State private var play = false

    var body: some View {
        let f = model.snapshot.firmware
        DeviceSheetFrame(title: L("device.row.update"), detents: [.medium, .large]) {
            switch f {
            case .upToDate:
                Text(L("device.update.upToDate", model.snapshot.firmwareVersion)).body1()
                Text(L("device.update.upToDate.note")).body2()
            case .available(let version):
                Text(L("device.update.available", version)).body1()
                Text(L("device.update.available.note")).body2()
                gateNote
                Button(L("device.update.start")) { model.startUpdate() }
                    .buttonStyle(.primary).disabled(model.gate != .ok).padding(.top, Space.s8)
            case .downloading(let p):
                progress(L("device.update.downloading"), p)
                Button(L("device.update.cancel")) { model.cancelUpdate() }.buttonStyle(.textual).padding(.leading, -Space.s8)
            case .transferring(let p):
                progress(L("device.update.transferring"), p)
                Text(L("device.update.keepOpen")).body2()
            case .verifying:
                progress(L("device.update.verifying"), 1)
            case .done(let version):
                Text(L("device.update.done", version)).body1()
                Text(L("device.update.done.note")).body2()
            case .failed:
                Text(L("device.update.failed")).body1()
                Text(L("device.update.failed.note")).body2()
                Button(L("device.update.retry")) { model.retryUpdate() }
                    .buttonStyle(.primary).disabled(model.gate != .ok).padding(.top, Space.s8)
                gateNote
            }
        }
    }

    @ViewBuilder private var gateNote: some View {
        switch model.gate {
        case .ok: EmptyView()
        case .notConnected: Text(L("device.update.gate.connect")).body2()
        case .needsCharge(let p): Text(L("device.update.gate.charge", p)).body2()
        }
    }

    /// A step, its percentage and a thin capsule that fills as the transfer advances: the one moving thing here.
    private func progress(_ step: String, _ p: Double) -> some View {
        VStack(alignment: .leading, spacing: Space.s12) {
            HStack(alignment: .firstTextBaseline) {
                Text(step).body1()
                Spacer(minLength: 0)
                Text("\(Int((p * 100).rounded())) %").font(.monoFixed(.regular, 17)).foregroundStyle(Palette.text1)
            }
            GeometryReader { g in
                ZStack(alignment: .leading) {
                    Capsule(style: .continuous).fill(Palette.hairline)
                    Capsule(style: .continuous).fill(Palette.text1).frame(width: max(8, g.size.width * p))
                        .animation(.linear(duration: 0.12), value: p)
                }
            }
            .frame(height: 8)
        }
    }
}

// MARK: Apple Health

struct HealthSheet: View {
    var model: DeviceModel

    var body: some View {
        let h = model.snapshot.health
        DeviceSheetFrame(title: L("device.row.health"), detents: [.medium, .large]) {
            Text(L("device.health.what")).body1()
            if h == .denied {
                Text(L("device.health.denied")).body2()
                Button(L("device.health.settings")) { Self.openSettings() }.buttonStyle(.secondary).padding(.top, Space.s8)
            } else {
                CapsuleToggle(
                    title: L("device.health.toggle"), detail: nil,
                    isOn: Binding(get: { h == .on }, set: { model.setHealth($0) }))
            }
            VStack(spacing: 0) {
                ForEach(Metric.allCases.filter { $0 != .readiness && $0 != .skinTemp }) { m in
                    HStack(spacing: Space.s12) {
                        MetricMarkShape(metric: m, size: 14)
                        Text(Self.name(m)).font(.system(size: 16)).foregroundStyle(Palette.text1)
                        Spacer(minLength: 0)
                        Text(m.writtenToHealth ? L("device.health.writes") : L("device.health.never"))
                            .font(.system(size: 14)).foregroundStyle(Palette.text2)
                    }
                    .frame(minHeight: 48)
                    .overlay(alignment: .bottom) { hairline }
                }
            }
            Text(L("device.health.locked")).font(.system(size: 14)).foregroundStyle(Palette.text3)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private static func name(_ m: Metric) -> String {
        switch m {
        case .heartRate: return L("device.health.hr")
        case .hrv: return L("metric.1")
        case .sleep: return L("device.health.sleep")
        case .steps: return L("device.health.steps")
        case .spo2: return L("metric.5")
        default: return ""
        }
    }

    private static func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
    }
}

// MARK: data

struct DataSheet: View {
    var model: DeviceModel
    @State private var format: ExportFormat = .csv
    @State private var range: ExportRange = .all
    @State private var encrypt = true
    @State private var passphrase = ""
    @State private var deleting = false
    @State private var typed = ""
    @State private var alsoHealth = false
    @FocusState private var focus: Bool

    var body: some View {
        let days = model.snapshot.storedDays
        DeviceSheetFrame(title: L("device.row.data")) {
            if deleting { deleteConfirm(days) } else { main(days) }
        }
        .animation(Motion.standard, value: deleting)
    }

    @ViewBuilder private func main(_ days: Int) -> some View {
        Text(days > 0 ? L("device.data.stored", days) : L("device.data.empty")).body1()
        Text(L("device.data.private")).body2()
        if days > 0 {
            sectionTitle(L("device.data.export"))
            Choices(options: ExportFormat.allCases, label: { $0.rawValue }, selection: $format)
            Choices(options: ExportRange.allCases, label: { $0 == .all ? L("device.data.all") : L("device.data.lastDays", $0.rawValue) }, selection: $range)
            CapsuleToggle(title: L("device.data.encrypt"), detail: L("device.data.encrypt.note"), isOn: $encrypt)
            if encrypt {
                SecureField(L("device.data.passphrase"), text: $passphrase)
                    .font(.system(size: 17)).foregroundStyle(Palette.text1)
                    .padding(.horizontal, Space.s16).frame(minHeight: 52)
                    .background(Capsule(style: .continuous).strokeBorder(Palette.text3, lineWidth: 1))
            }
            Button(exportTitle) { model.export() }
                .buttonStyle(.primary)
                .disabled(model.exportState == .working || (encrypt && passphrase.count < 4))
            Text(L("device.data.export.note")).font(.system(size: 14)).foregroundStyle(Palette.text3)
                .fixedSize(horizontal: false, vertical: true)
            sectionTitle(L("device.data.delete")).padding(.top, Space.s12)
            Button(L("device.data.delete.cta")) { deleting = true }.buttonStyle(.secondary)
        }
    }

    private var exportTitle: String {
        switch model.exportState {
        case .idle: return L("device.data.export.cta")
        case .working: return L("device.data.export.working")
        case .done: return L("device.data.export.done")
        }
    }

    @ViewBuilder private func deleteConfirm(_ days: Int) -> some View {
        Text(L("device.data.delete.warn", days)).body1()
        Text(L("device.data.delete.note")).body2()
        CapsuleToggle(title: L("device.data.delete.health"), detail: nil, isOn: $alsoHealth)
        Text(L("device.data.delete.type", L("device.data.delete.word"))).body2()
        TextField("", text: $typed)
            .focused($focus)
            .textInputAutocapitalization(.never).autocorrectionDisabled()
            .font(.monoFixed(.regular, 17)).foregroundStyle(Palette.text1)
            .padding(.horizontal, Space.s16).frame(minHeight: 52)
            .background(Capsule(style: .continuous).strokeBorder(Palette.text3, lineWidth: 1))
        Button(L("device.data.delete.confirm")) {
            Haptics.warning()
            model.deleteData()
            deleting = false
            typed = ""
        }
        .buttonStyle(.destructive)
        .disabled(typed != L("device.data.delete.word"))
        Button(L("device.cancel")) { deleting = false; typed = "" }.buttonStyle(.textual).padding(.leading, -Space.s8)
    }

    private func sectionTitle(_ t: String) -> some View {
        Text(t).font(.system(size: 14, weight: .medium)).foregroundStyle(Palette.text3)
    }
}

// MARK: experimental

struct ExperimentalSheet: View {
    var model: DeviceModel

    var body: some View {
        let s = model.snapshot
        DeviceSheetFrame(title: L("device.row.exp"), detents: [.medium, .large]) {
            Text(L("device.exp.what")).body1()
            Text(L("device.exp.note")).body2()
            CapsuleToggle(
                title: L("metric.5"), detail: s.supportsSpO2 ? L("device.exp.spo2") : L("device.exp.unsupported", L("metric.5")),
                isOn: Binding(get: { s.spo2Enabled }, set: { model.setSpO2($0) }), enabled: s.supportsSpO2)
            hairline
            CapsuleToggle(
                title: L("today.tile.temp"),
                detail: s.supportsTemperature ? L("device.exp.temp") : L("device.exp.unsupported", L("today.tile.temp")),
                isOn: Binding(get: { s.temperatureEnabled }, set: { model.setTemperature($0) }), enabled: s.supportsTemperature)
        }
    }
}

// MARK: forget

struct ForgetSheet: View {
    var model: DeviceModel
    var onForget: () -> Void

    var body: some View {
        DeviceSheetFrame(title: L("device.row.forget"), detents: [.medium, .large]) {
            Text(L("device.forget.what")).body1()
            Text(L("device.forget.disc")).body2()
            Text(L("device.forget.ios")).body2()
            Button(L("device.forget.app")) {
                Haptics.warning()
                model.sheet = nil
                onForget()
            }
            .buttonStyle(.destructive).padding(.top, Space.s8)
            Button(L("device.forget.settings")) {
                if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
            }
            .buttonStyle(.textual).padding(.leading, -Space.s8)
        }
    }
}

// MARK: about

/// What the "i" opens: the technical side of the disc, one level down from the sentence on the screen.
struct AboutSheet: View {
    var snapshot: DeviceSnapshot

    var body: some View {
        DeviceSheetFrame(title: snapshot.name, detents: [.medium, .large]) {
            Text(L("device.about.what")).body1()
            VStack(spacing: 0) {
                line(L("device.about.fw"), snapshot.firmwareVersion)
                line(L("device.about.hw"), snapshot.hardwareRevision)
                line(L("device.about.id"), snapshot.deviceID)
                line(L("device.about.proto"), snapshot.protocolVersion)
                line(L("device.about.sensors"), sensors)
            }
        }
    }

    private var sensors: String {
        var parts = [L("device.about.sensor.hr"), L("device.about.sensor.motion")]
        if snapshot.supportsSpO2 { parts.append(L("metric.5")) }
        if snapshot.supportsTemperature { parts.append(L("today.tile.temp")) }
        return parts.joined(separator: ", ")
    }

    private func line(_ k: String, _ v: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: Space.s12) {
            Text(k).font(.system(size: 15)).foregroundStyle(Palette.text2)
            Spacer(minLength: 0)
            Text(v).font(.monoFixed(.regular, 14)).foregroundStyle(Palette.text1).multilineTextAlignment(.trailing)
        }
        .frame(minHeight: 48)
        .overlay(alignment: .bottom) { hairline }
    }
}
