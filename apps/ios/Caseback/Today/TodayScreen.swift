import SwiftUI

/// Today: the fixed panel, the conclusions sheet under it and the gesture that opens it.
struct TodayScreen: View {
    let model: TodayModel
    let drawer: DrawerController
    var onAlert: () -> Void
    var onSetup: () -> Void

    private let peekHeight: CGFloat = 78
    @State private var dragActive = false
    @State private var touching = false
    @State private var decided = false
    @State private var startedAtTop = true

    var body: some View {
        GeometryReader { g in
            let p = drawer.progress
            ZStack(alignment: .top) {
                TodayPanel(model: model, onAlert: onAlert, onSetup: onSetup)
                    .padding(.bottom, model.snapshot.paired ? peekHeight : 0)
                    // The panel sinks and dims as the sheet comes up: depth, not a cut.
                    .scaleEffect(1 - 0.06 * p, anchor: .top)
                    .opacity(Double(1 - 0.55 * p))
                    .allowsHitTesting(p < 0.05)
                if model.snapshot.paired {
                    InsightsDrawer(
                        controller: drawer, snapshot: model.snapshot, height: g.size.height, peekHeight: peekHeight, topInset: 6,
                        onOpen: model.open)
                }
            }
            .frame(width: g.size.width, height: g.size.height, alignment: .top)
            .clipped()
            .contentShape(Rectangle())
            .simultaneousGesture(pull)
            .sheet(item: Bindable(model).info) { InfoSheet(destination: $0) }
            .onAppear {
                drawer.distance = max(g.size.height - peekHeight - 6, 1)
                // Screenshots only: `-today-drawer 1` opens the sheet, `-today-drawer 0.4` freezes it part way.
                if let v = LaunchOnce.take("today-drawer").flatMap(Double.init) { drawer.preview(CGFloat(v)) }
                // `-today-info readiness` shows the explanation of that chart.
                if let name = LaunchOnce.take("today-info"), let d = TodayDestination.allKnown.first(where: { $0.infoKey == name }) {
                    model.info = d
                }
                // `-today-open sleep` opens that metric's screen.
                if let name = LaunchOnce.take("today-open"), let d = TodayDestination.allKnown.first(where: { $0.infoKey == name }) {
                    model.open(d, from: CGRect(x: 20, y: 150, width: 353, height: 260))
                }
            }
            .onChange(of: g.size.height) { _, h in drawer.distance = max(h - peekHeight - 6, 1) }
        }
    }

    private var pull: some Gesture {
        DragGesture(minimumDistance: 0, coordinateSpace: .global)
            .onChanged { v in
                guard model.snapshot.paired else { return }
                if !touching {
                    touching = true
                    decided = false
                    startedAtTop = drawer.scrollAtTop
                }
                if !dragActive {
                    guard !decided, hypot(v.translation.width, v.translation.height) >= 10 else { return }
                    // One decision per touch: a swipe that starts as a scroll never turns into a close.
                    decided = true
                    guard drawer.accepts(dx: v.translation.width, dy: v.translation.height, atTop: startedAtTop) else { return }
                    dragActive = true
                    drawer.begin()
                }
                // Travel in the direction that moves the sheet: up to open, down to close.
                drawer.drag(travel: drawer.isOpen ? v.translation.height : -v.translation.height)
            }
            .onEnded { v in
                touching = false
                guard dragActive else { return }
                dragActive = false
                let up = drawer.isOpen ? v.translation.height : -v.translation.height
                let speed = drawer.isOpen ? v.velocity.height : -v.velocity.height
                drawer.end(travel: up, velocity: speed)
            }
    }
}
