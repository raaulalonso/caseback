import SwiftUI

/// What a tap opens: the screen of that metric (`MetricDetailScreen`). It comes out of the section that was touched: the ground
/// grows from where the finger was to fill the window and the content settles in after it.
struct TodayDetailOverlay: View {
    let model: TodayModel
    let trends: TrendsModel
    /// 0 closed, 1 open. The screen fades and rises in; it fades and sinks out.
    @State private var shown: CGFloat = 0
    /// How far a finger has pulled the screen to the right from the left edge.
    @State private var drag: CGFloat = 0
    @State private var pulling = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        GeometryReader { g in
            if let dest = model.selected {
                ZStack(alignment: .topLeading) {
                    Palette.ground.opacity(min(shown * 1.6, 1))
                    MetricDetailScreen(destination: dest, today: model, trends: trends, onClose: { close(width: g.size.width) })
                        .id(dest)
                        .frame(width: g.size.width, height: g.size.height)
                        .opacity(shown)
                        .offset(y: (1 - shown) * 22)
                }
                .offset(x: drag)
                .onAppear { open() }
                // Back from the left edge: the screen follows the finger, and leaves or springs back when it is let go.
                .simultaneousGesture(
                    DragGesture(minimumDistance: 10, coordinateSpace: .global)
                        .onChanged { v in
                            if !pulling {
                                guard v.startLocation.x < 28, v.translation.width > 0, abs(v.translation.height) < v.translation.width else { return }
                                pulling = true
                            }
                            drag = max(v.translation.width, 0)
                            model.coverage = 1 - min(drag / g.size.width, 1)
                        }
                        .onEnded { v in
                            guard pulling else { return }
                            pulling = false
                            if drag > g.size.width * 0.33 || v.predictedEndTranslation.width > g.size.width * 0.6 {
                                finish(width: g.size.width)
                            } else {
                                withAnimation(reduceMotion ? nil : .spring(response: 0.35, dampingFraction: 0.85)) {
                                    drag = 0
                                    model.coverage = 1
                                }
                            }
                        })
            }
        }
        .ignoresSafeArea()
        .allowsHitTesting(model.selected != nil)
    }

    private func open() {
        if reduceMotion { shown = 1; model.coverage = 1; return }
        withAnimation(.spring(response: 0.46, dampingFraction: 0.88)) {
            shown = 1
            model.coverage = 1
        }
        Haptics.step()
    }

    /// The chevron: the screen fades and sinks while Today comes forward, in one motion.
    private func close(width: CGFloat) {
        Haptics.tap()
        if reduceMotion { model.coverage = 0; shown = 0; model.close(); return }
        withAnimation(.easeOut(duration: 0.3), completionCriteria: .logicallyComplete) {
            shown = 0
            model.coverage = 0
        } completion: {
            model.close()
        }
    }

    /// The pull was far enough: slide the rest of the way out.
    private func finish(width: CGFloat) {
        Haptics.tap()
        if reduceMotion { model.coverage = 0; model.close(); drag = 0; shown = 0; return }
        withAnimation(.easeOut(duration: 0.22), completionCriteria: .logicallyComplete) {
            drag = width
            model.coverage = 0
        } completion: {
            model.close()
            drag = 0
            shown = 0
        }
    }
}
