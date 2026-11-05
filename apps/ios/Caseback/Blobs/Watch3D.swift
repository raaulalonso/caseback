import SwiftUI
import simd

// Screen-space animation for the mounting illustration. Units are relative to the icon.
enum Watch3D {
    static let camera: Double = 9
    static let focal: Double = 0.27
    /// Where the disc sits on the back of the case, in watch units (the case radius is 1).
    static let discRadius: Double = 0.76
    static let discZ: Double = -0.2
    /// Total height of the watch with its straps, in watch units: it has to fit the free band.
    static let extent: Double = 5.1
    static let turnStart = 1.0, turnEnd = 2.2, flyStart = 1.5
    /// The time to draw when motion is reduced: everything done.
    static let settled: Double = 9

    struct Pose {
        var yaw: Double
        var pitch: Double
        var scale: Double
        var fade: Double
    }

    private static func ease(_ t: Double) -> Double { let c = min(max(t, 0), 1); return c * c * (3 - 2 * c) }
    private static func easeInOut(_ t: Double) -> Double {
        let c = min(max(t, 0), 1)
        return c < 0.5 ? 4 * c * c * c : 1 - pow(-2 * c + 2, 3) / 2
    }
    private static func easeOutBack(_ t: Double) -> Double {
        let c = min(max(t, 0), 1)
        return 1 + 2.2 * pow(c - 1, 3) + 1.2 * pow(c - 1, 2)
    }

    static func pose(_ t: Double) -> Pose {
        let turned = easeInOut((t - turnStart) / (turnEnd - turnStart))
        let sway = 0.26 - 0.17 * ease((t - turnEnd + 0.2) / 0.8)
        let enter = -1.5 * (1 - easeInOut(t / 1.0))
        return Pose(
            yaw: -0.55 + enter + .pi * turned + sway * sin(t * 0.75),
            pitch: 0.3 + 0.05 * sin(t * 0.5),
            scale: 0.55 + 0.45 * min(easeOutBack(t / 0.8), 1.08),
            fade: ease(t / 0.35))
    }

    /// The scale of the picture: `half` is the half-size of the square the camera is calibrated on, in points.
    static func half(size: CGSize, stage: BlobStage?) -> CGFloat {
        let st = stage ?? .fallback(size)
        let unit = st.height * 0.94 / extent       // points per watch unit
        return min(unit / (1 / (camera * focal)), size.width / 2)
    }

    static func centre(size: CGSize, stage: BlobStage?) -> CGPoint {
        CGPoint(x: size.width / 2, y: (stage ?? .fallback(size)).midY)
    }

    /// A point of the watch (object space, dial towards +z, 12 o'clock towards +y) in screen points, and the points of one watch unit there.
    static func project(_ p: SIMD3<Double>, at t: Double, size: CGSize, stage: BlobStage?) -> (point: CGPoint, k: CGFloat) {
        let w = pose(t)
        let cy = cos(w.yaw), sy = sin(w.yaw), cx = cos(w.pitch), sx = sin(w.pitch)
        let x1 = cy * p.x + sy * p.z
        let z1 = -sy * p.x + cy * p.z
        let y2 = cx * p.y - sx * z1
        let z2 = sx * p.y + cx * z1
        let half = Double(Self.half(size: size, stage: stage))
        let f = focal / w.scale
        let k = half / ((camera - z2) * f)
        let c = centre(size: size, stage: stage)
        return (CGPoint(x: Double(c.x) + x1 * k, y: Double(c.y) - y2 * k), CGFloat(k))
    }
}

struct MountWatch: View {
    var stage: BlobStage?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var began = Date()

    var body: some View {
        TimelineView(.animation) { timeline in
            GeometryReader { geometry in
                let elapsed = reduceMotion ? Watch3D.settled : timeline.date.timeIntervalSince(began)
                let pose = Watch3D.pose(elapsed)
                let centre = Watch3D.centre(size: geometry.size, stage: stage)
                let radius = Watch3D.project(.zero, at: elapsed, size: geometry.size, stage: stage).k
                Image(systemName: "clock")
                    .font(.system(size: 2 * radius, weight: .light))
                    .foregroundStyle(.secondary)
                    .rotation3DEffect(.radians(pose.yaw), axis: (x: 0, y: 1, z: 0))
                    .opacity(pose.fade)
                    .position(centre)
            }
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L("mount.a11y"))
        .onAppear { began = Date() }
        .task {
            // The disc lands on the caseback: one thud, when the blobs have arrived.
            guard !reduceMotion else { return }
            try? await Task.sleep(for: .milliseconds(Int((Watch3D.flyStart + 1.0) * 1000)))
            if !Task.isCancelled { Haptics.thud() }
        }
    }
}
