import SwiftUI

/// The mark (D29): a ring (the disc) with a 30 degree opening at the upper right and a small filled lume dot in the
/// opening. White ring on black, dot in the readiness colour.
struct CasebackMark: View {
    /// 0...1: how much of the ring is drawn.
    var ringProgress: CGFloat = 1
    /// 0...1: scale of the dot.
    var dotScale: CGFloat = 1
    var ringColor: Color = Palette.text1
    var lineWidth: CGFloat = 1.5

    static let gapDegrees: Double = 30
    /// Centre of the opening, measured clockwise from 3 o'clock; upper right is -45 degrees.
    static let gapCenterDegrees: Double = -45

    var body: some View {
        GeometryReader { geo in
            let side = min(geo.size.width, geo.size.height)
            let r = side / 2 - lineWidth
            let c = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
            ZStack {
                MarkRing()
                    .trim(from: 0, to: ringProgress)
                    .stroke(ringColor, style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
                Circle()
                    .fill(Metric.readiness.color)
                    .frame(width: max(side * 0.11, lineWidth * 3), height: max(side * 0.11, lineWidth * 3))
                    .scaleEffect(dotScale)
                    .position(
                        x: c.x + r * CGFloat(cos(Self.gapCenterDegrees * .pi / 180)),
                        y: c.y + r * CGFloat(sin(Self.gapCenterDegrees * .pi / 180)))
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityHidden(true)
    }
}

/// The ring path: starts at the far side of the opening and runs clockwise to the near side.
struct MarkRing: Shape {
    func path(in rect: CGRect) -> Path {
        let side = min(rect.width, rect.height)
        let r = side / 2 - 1
        let start = CasebackMark.gapCenterDegrees + CasebackMark.gapDegrees / 2
        let end = CasebackMark.gapCenterDegrees - CasebackMark.gapDegrees / 2 + 360
        var p = Path()
        p.addArc(
            center: CGPoint(x: rect.midX, y: rect.midY), radius: r,
            startAngle: .degrees(start), endAngle: .degrees(end), clockwise: false)
        return p
    }
}
