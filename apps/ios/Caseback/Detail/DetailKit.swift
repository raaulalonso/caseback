import SwiftUI

// The pieces every metric screen is made of, in the language of Today and Trends: on the black, hairlines, full width, no
// icons, only the charts move.

/// Top and bottom safe areas, for the screens that cover the whole window (the overlay ignores them).
enum SafeArea {
    private static var insets: UIEdgeInsets {
        (UIApplication.shared.connectedScenes.first as? UIWindowScene)?.keyWindow?.safeAreaInsets ?? .zero
    }
    static var top: CGFloat { insets.top }
    static var bottom: CGFloat { insets.bottom }
}

/// Back chevron, the name of the metric, and the "i" that explains it.
struct DetailTopBar: View {
    var title: String
    var metric: Metric
    var onBack: () -> Void
    var onInfo: () -> Void

    var body: some View {
        ZStack(alignment: .trailing) {
            HStack(spacing: Space.s4) {
                Button(action: onBack) {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 15, weight: .semibold)).foregroundStyle(Palette.text1)
                        .frame(width: Space.hit, height: Space.hit)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(L("action.back"))
                .accessibilityIdentifier("detail.back")
                Text(title)
                    .font(.system(size: 15, weight: .medium)).foregroundStyle(Palette.text2)
                    .dynamicTypeSize(...DynamicTypeSize.xxxLarge)
                    .lineLimit(1).minimumScaleFactor(0.75)
                    .padding(.trailing, 64)
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 0)
            }
            .padding(.leading, -Space.s12)
            InfoButton(metric: metric, action: onInfo).offset(x: 10)
        }
        .frame(height: Space.hit)
    }
}

/// A group under the hero: a hairline, a quiet title, the content.
struct DetailSection<Content: View>: View {
    var title: String?
    @ViewBuilder var content: () -> Content

    var body: some View {
        VStack(alignment: .leading, spacing: Space.s12) {
            if let title { Text(title).font(.system(size: 14, weight: .medium)).foregroundStyle(Palette.text3) }
            content()
        }
        .padding(.vertical, Space.s16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(alignment: .top) { Rectangle().fill(Palette.hairline).frame(height: 1 / UIScreen.main.scale) }
    }
}

/// A few words to pick from; the active one is `ground` on a `text1` capsule that slides to the next.
struct WordPicker<T: Hashable & Identifiable>: View {
    var options: [T]
    @Binding var selection: T
    var label: (T) -> String
    var accessibility: (T) -> String
    var mono = false
    @Namespace private var ns
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 2) {
            ForEach(options) { o in
                let active = o == selection
                Button {
                    guard !active else { return }
                    Haptics.tick()
                    withAnimation(reduceMotion ? nil : .spring(response: 0.4, dampingFraction: 0.8)) { selection = o }
                } label: {
                    Text(label(o))
                        .font(mono ? .monoFixed(.medium, 15) : .system(size: 15, weight: .medium))
                        .foregroundStyle(active ? Palette.ground : Palette.text3)
                        .padding(.horizontal, 12)
                        .frame(minWidth: 42, minHeight: 30)
                        .background {
                            if active { Capsule(style: .continuous).fill(Palette.text1).matchedGeometryEffect(id: "pick", in: ns) }
                        }
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityLabel(accessibility(o))
                .accessibilityAddTraits(active ? .isSelected : [])
            }
        }
    }
}

/// A figure with its name under it, for the three-up rows of facts.
struct Fact: View {
    var value: String
    var label: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value).font(.monoFixed(.light, 24)).foregroundStyle(Palette.text1).lineLimit(1).minimumScaleFactor(0.6)
            Text(label).font(.system(size: 13)).foregroundStyle(Palette.text3).lineLimit(1).minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// A part of something that adds up: its name, what it earned of what it could, and a capsule that fills.
struct PartBar: View {
    var name: String
    var points: Int
    var outOf: Int
    var color: Color
    var play: Bool
    var delay: Double

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(name).font(.system(size: 16)).foregroundStyle(Palette.text1)
                Spacer(minLength: 0)
                Text("\(points)").font(.monoFixed(.regular, 16)).foregroundStyle(Palette.text1)
                Text("/ \(outOf)").font(.monoFixed(.regular, 12)).foregroundStyle(Palette.text3)
            }
            GeometryReader { g in
                ZStack(alignment: .leading) {
                    Capsule(style: .continuous).fill(Palette.hairline)
                    Capsule(style: .continuous).fill(color)
                        .frame(width: max(6, g.size.width * (play ? CGFloat(points) / CGFloat(max(outOf, 1)) : 0)))
                        .motion(ChartMotion.grow(delay), value: play)
                }
            }
            .frame(height: 6)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(name), \(points) / \(outOf)")
    }
}
