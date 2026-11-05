import SwiftUI

// Small pieces shared by the app and the widget extension.

/// Looks up a string in the String Catalog (the design notes section 7).
func L(_ key: String) -> String { String(localized: String.LocalizationValue(key)) }
func L(_ key: String, _ args: CVarArg...) -> String { String(format: L(key), arguments: args) }

// MARK: marks

/// A metric mark drawn as a bare shape (02 section 1): circle, diamond, square, triangle, open circle, bar.
struct MetricMarkShape: View {
    var metric: Metric
    var size: CGFloat = 10
    var color: Color?

    var body: some View {
        let c = color ?? metric.color
        Group {
            switch metric {
            case .heartRate: Circle().fill(c)
            case .hrv: Rectangle().fill(c).rotationEffect(.degrees(45)).scaleEffect(0.78)
            case .sleep: Rectangle().fill(c).scaleEffect(0.82)
            case .steps: Triangle().fill(c)
            case .spo2: Circle().strokeBorder(c, lineWidth: max(size * 0.2, 1.5))
            case .skinTemp: Triangle().fill(c).rotationEffect(.degrees(180))
            case .readiness: Rectangle().fill(c).frame(width: size * 0.34, height: size * 1.05)
            }
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}

struct Triangle: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.midX, y: rect.minY + rect.height * 0.06))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - rect.height * 0.08))
        p.addLine(to: CGPoint(x: rect.minX, y: rect.maxY - rect.height * 0.08))
        p.closeSubpath()
        return p
    }
}

// MARK: motion

/// Applies `animation` to changes of `value`, unless Reduce Motion is on.
struct MotionModifier<V: Equatable>: ViewModifier {
    var animation: Animation
    var value: V
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View { content.animation(reduceMotion ? nil : animation, value: value) }
}

extension View {
    func motion<V: Equatable>(_ animation: Animation, value: V) -> some View { modifier(MotionModifier(animation: animation, value: value)) }
}
