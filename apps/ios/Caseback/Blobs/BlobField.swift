import SwiftUI

/// The onboarding blob field: a full-screen Metal shader driven by `BlobSimulator`. Decorative: hidden from
/// accessibility and static under Reduce Motion.
struct BlobField: View {
    var pose: BlobPose
    var inputs: BlobInputs = BlobInputs()
    /// Change this value on every detected heartbeat.
    var beat: Int = 0
    var stage: BlobStage?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    @State private var sim = BlobSimulator()

    var body: some View {
        GeometryReader { geo in
            TimelineView(.animation(paused: scenePhase != .active)) { timeline in
                let time = timeline.date.timeIntervalSinceReferenceDate
                let _ = advance(time: time, size: geo.size)
                Rectangle()
                    .fill(Color.black.opacity(0.01))  // the shader draws only the blobs; the watch is visible behind them
                    .colorEffect(
                        ShaderLibrary.default.blobField(
                            .float2(geo.size), .float(Float(time.truncatingRemainder(dividingBy: 10_000))),
                            .floatArray(sim.packed(time: time)), .float(sim.smoothness)))
            }
            .contentShape(Rectangle())
            .simultaneousGesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { v in if !reduceMotion { sim.touch = v.location } }
                    .onEnded { _ in sim.touch = nil })
        }
        .onChange(of: beat) { _, _ in sim.pulseBeat() }
        .accessibilityHidden(true)
        .allowsHitTesting(true)
    }

    private func advance(time: Double, size: CGSize) {
        sim.reduceMotion = reduceMotion
        sim.inputs = inputs
        sim.stage = stage
        sim.setPose(pose, at: time, size: size)
        sim.advance(to: time, size: size)
    }
}
