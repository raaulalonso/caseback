import SwiftUI

// MARK: buttons

struct CasebackButtonStyle: ButtonStyle {
    enum Kind { case primary, secondary, text, destructive }
    var kind: Kind = .primary
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        let pressed = configuration.isPressed
        configuration.label
            .font(.label)
            .foregroundStyle(foreground(pressed))
            .frame(maxWidth: kind == .text ? nil : .infinity)
            .frame(minHeight: kind == .text ? Space.hit : 56)
            .padding(.horizontal, kind == .text ? Space.s8 : 0)
            .background {
                switch kind {
                case .primary:
                    Capsule(style: .continuous).fill(pressed ? Palette.text2 : Palette.text1)
                case .secondary:
                    Capsule(style: .continuous).strokeBorder(Palette.text2, lineWidth: 1)
                case .destructive:
                    Capsule(style: .continuous).strokeBorder(Palette.alert, lineWidth: 1.5)
                case .text: Color.clear
                }
            }
            .scaleEffect(pressed && kind != .text ? 0.98 : 1)
            .opacity(isEnabled ? 1 : 0.35)
            .animation(.easeOut(duration: Motion.tap), value: pressed)
            .contentShape(Rectangle())
    }

    private func foreground(_ pressed: Bool) -> Color {
        switch kind {
        case .primary: return Palette.ground
        case .secondary: return Palette.text1
        case .destructive: return Palette.alert
        case .text: return pressed ? Palette.text1 : Palette.text2
        }
    }
}

extension ButtonStyle where Self == CasebackButtonStyle {
    static var primary: CasebackButtonStyle { .init(kind: .primary) }
    static var secondary: CasebackButtonStyle { .init(kind: .secondary) }
    static var textual: CasebackButtonStyle { .init(kind: .text) }
    static var destructive: CasebackButtonStyle { .init(kind: .destructive) }
}

// MARK: reveal

/// Lines of a step appear one after another: opacity and a short rise. Under Reduce Motion: a plain fade.
struct Reveal: ViewModifier {
    var index: Int
    @State private var shown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        content
            .opacity(shown ? 1 : 0)
            .offset(y: shown || reduceMotion ? 0 : 14)
            .onAppear {
                let delay = reduceMotion ? 0 : 0.10 + Double(index) * 0.07
                withAnimation(reduceMotion ? .easeOut(duration: 0.2) : Motion.standard(0.55).delay(delay)) { shown = true }
            }
    }
}

extension View {
    func reveal(_ index: Int) -> some View { modifier(Reveal(index: index)) }
}

// MARK: stage

/// The flexible clear band of a step; the blob field composes inside it (see `BlobStage`).
struct StageRegion: View {
    var minHeight: CGFloat = 60
    /// False for a step whose own content takes the free space and the stage is only a slim band.
    var flexible = true
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        Color.clear
            // With very large text the step scrolls, so the stage keeps a usable height instead of collapsing.
            .frame(minHeight: typeSize.isAccessibilitySize ? max(minHeight, flexible ? 220 : minHeight) : minHeight)
            .frame(maxHeight: flexible ? .infinity : minHeight)
            .background(
                GeometryReader { g in
                    Color.clear.preference(key: StageKey.self, value: g.frame(in: .global))
                })
    }
}

struct StageKey: PreferenceKey {
    static var defaultValue: CGRect?
    static func reduce(value: inout CGRect?, nextValue: () -> CGRect?) { value = nextValue() ?? value }
}

// MARK: top bar

/// Back and progress on one line: a chevron, then six rounded segments (the steps after the welcome). Done segments are
/// `text1`, the rest `hairline`.
struct TopBar: View {
    var index: Int
    var canGoBack: Bool
    var back: () -> Void
    var total: Int = OnboardingStep.counted.count

    var body: some View {
        HStack(spacing: Space.s8) {
            Button(action: back) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(Palette.text1)
                    .frame(width: Space.hit, height: Space.hit)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .opacity(canGoBack ? 1 : 0)
            .disabled(!canGoBack)
            .accessibilityLabel(L("action.back"))
            .accessibilityHidden(!canGoBack)

            HStack(spacing: 5) {
                ForEach(1...total, id: \.self) { i in
                    Capsule()
                        .fill(i <= index ? Palette.text1 : Palette.hairline)
                        .frame(height: 3)
                        .animation(Motion.standard(0.5), value: index)
                }
            }
            .padding(.trailing, Space.s8)
            .accessibilityElement()
            .accessibilityLabel(L("a11y.progress", index, total))
        }
        .frame(height: Space.hit)
        .padding(.leading, -Space.s12)  // the chevron's hit area starts inside the margin; its glyph aligns with the text
    }
}

// MARK: contact bar

/// Twenty ticks like the readiness ruler; the filled ones follow the contact quality.
struct ContactBar: View {
    var value: Double  // 0...1

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0..<20, id: \.self) { i in
                Capsule()
                    .fill(Double(i) < value * 20 ? Palette.text1 : Palette.hairline)
                    .frame(width: 2, height: i % 5 == 0 ? 16 : 10)
                    .frame(maxHeight: 16, alignment: .bottom)
            }
        }
        .animation(Motion.standard(0.4), value: value)
        .accessibilityHidden(true)
    }
}

// MARK: fitting

/// Lays a block out at a fixed design size and scales it uniformly to the space it is given, so a fixed panel works on
/// every phone: the block keeps its proportions and never scrolls.
struct FitCanvas<Content: View>: View {
    var design: CGSize
    @ViewBuilder var content: () -> Content

    var body: some View {
        GeometryReader { g in
            let s = min(g.size.width / design.width, g.size.height / design.height, 1.25)
            content()
                .frame(width: design.width, height: design.height)
                .scaleEffect(s, anchor: .center)
                .frame(width: g.size.width, height: g.size.height)
        }
    }
}
