import SwiftUI

/// Every widget family and state at its real size, on the screen of the app (`-widget-gallery YES`). It draws the same views as the
/// extension, so what you see here is what the Home Screen and the Lock Screen draw. Invented numbers.
struct WidgetGallery: View {
    /// "all", or one section: small, states, medium, lock.
    var only = "all"
    private let now = Date()

    private var normal: WidgetSnapshot { .make(from: TodayFixtures.snapshot(.normal), syncedAt: now.addingTimeInterval(-12 * 60)) }
    private func aged(_ hours: Double) -> WidgetSnapshot {
        var s = normal
        s.updatedAt = now.addingTimeInterval(-hours * 3600)
        return s
    }
    private var calibrating: WidgetSnapshot { .make(from: TodayFixtures.snapshot(.calibrating), syncedAt: now.addingTimeInterval(-12 * 60)) }
    private var alert: WidgetSnapshot { .make(from: TodayFixtures.snapshot(.lowBattery), syncedAt: now.addingTimeInterval(-12 * 60)) }
    private var bond: WidgetSnapshot { .make(from: TodayFixtures.snapshot(.bondLost), syncedAt: now.addingTimeInterval(-12 * 60)) }
    private var unpaired: WidgetSnapshot { .make(from: TodayFixtures.snapshot(.unpaired), syncedAt: now) }

    private let page = Color(hex: 0x1C1C1E)
    /// Roughly a dark wallpaper, to see the Lock Screen accessories on something that is not black.
    private let wall = LinearGradient(colors: [Color(hex: 0x3A4A5E), Color(hex: 0x1D2733)], startPoint: .top, endPoint: .bottom)

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                if show("small") {
                title("Pequeño · una métrica a elegir")
                grid(WidgetMetricKind.allCases.map { k in AnyView(small(normal, k)) })
                }
                if show("states") {
                title("Pequeño · estados")
                grid([
                    AnyView(small(aged(9), .readiness)), AnyView(small(aged(30), .readiness)),
                    AnyView(small(aged(100), .readiness)), AnyView(small(calibrating, .readiness)),
                    AnyView(small(alert, .readiness)), AnyView(small(bond, .sleep)),
                    AnyView(small(unpaired, .readiness)), AnyView(small(calibrating, .skinTemp)),
                ])
                }
                if show("medium") {
                title("Mediano")
                VStack(spacing: 12) {
                    medium(normal); medium(aged(30)); medium(alert); medium(calibrating); medium(aged(100)); medium(unpaired)
                }
                }
                if show("lock") {
                title("Pantalla de bloqueo")
                lock
                }
            }
            .padding(16)
        }
        .background(page.ignoresSafeArea())
        .environment(\.colorScheme, .dark)
    }

    private func show(_ section: String) -> Bool { only == "all" || only == section }

    private func title(_ t: String) -> some View {
        Text(t).font(.system(size: 13, weight: .medium)).foregroundStyle(Palette.text3)
    }

    private func grid(_ items: [AnyView]) -> some View {
        LazyVGrid(columns: [GridItem(.fixed(158), spacing: 16), GridItem(.fixed(158))], alignment: .leading, spacing: 16) {
            ForEach(items.indices, id: \.self) { items[$0] }
        }
    }

    /// A widget on the Home Screen: black, 22 pt corners, the system's 16 pt margin.
    private func frame<V: View>(_ w: CGFloat, _ h: CGFloat, @ViewBuilder _ content: () -> V) -> some View {
        content().padding(16).frame(width: w, height: h, alignment: .topLeading)
            .background(Palette.ground).clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    private func small(_ s: WidgetSnapshot, _ k: WidgetMetricKind) -> some View {
        frame(158, 158) { SmallWidgetView(snapshot: s, kind: k, now: now) }
    }

    private func medium(_ s: WidgetSnapshot) -> some View {
        frame(338, 158) { MediumWidgetView(snapshot: s, now: now) }
    }

    private var lock: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(spacing: 14) {
                circle(normal, .readiness); circle(normal, .sleep); circle(aged(30), .readiness); circle(unpaired, .readiness)
            }
            HStack(spacing: 8) { rect(normal); rect(alert) }
            HStack(spacing: 8) { rect(aged(100)); rect(unpaired) }
            VStack(alignment: .leading, spacing: 8) { inline(normal); inline(aged(100)) }
        }
        .padding(12).frame(maxWidth: .infinity, alignment: .leading)
        .background(wall).clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    private func circle(_ s: WidgetSnapshot, _ k: WidgetMetricKind) -> some View {
        CircularWidgetView(snapshot: s, kind: k, now: now).frame(width: 72, height: 72)
            .background(Circle().fill(.white.opacity(0.14))).foregroundStyle(.white)
    }

    private func rect(_ s: WidgetSnapshot) -> some View {
        RectangularWidgetView(snapshot: s, now: now).padding(.horizontal, 12).frame(width: 160, height: 72, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(.white.opacity(0.14))).foregroundStyle(.white)
    }

    private func inline(_ s: WidgetSnapshot) -> some View {
        InlineWidgetView(snapshot: s, now: now).font(.system(size: 14, weight: .medium)).foregroundStyle(.white)
            .frame(width: 234, height: 26, alignment: .leading)
    }
}
