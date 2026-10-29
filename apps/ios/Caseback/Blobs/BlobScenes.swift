import CoreGraphics
import Foundation

/// A pose of the blob field: where the seven blobs want to be. The choreography is in
/// the design notes section 10.
enum BlobPose: Equatable {
    case welcome
    case bluetooth
    case mount
    case searching
    case fused
    case burst
    case marks
    case marksHigh
    case flood
    case settle
}

/// Where one blob wants to be, in points. `morph` 0 is a blob, 1 is its metric mark.
struct BlobTarget: Equatable {
    var x: CGFloat
    var y: CGFloat
    var radius: CGFloat
    var morph: CGFloat = 0
    var rotation: CGFloat = 0
    var wobble: CGFloat = 0.06
    /// Idle drift amplitude in points.
    var drift: CGFloat = 0
    /// Spring stiffness, when a blob has to keep up with something that moves (the watch).
    var stiff: Float?
}

/// The free band of the screen between the title and the actions, in points. The field composes inside it so blobs never
/// sit on text, on any screen size.
struct BlobStage: Equatable {
    var minY: CGFloat
    var maxY: CGFloat
    var midY: CGFloat { (minY + maxY) / 2 }
    var height: CGFloat { max(maxY - minY, 1) }

    static func fallback(_ size: CGSize) -> BlobStage { BlobStage(minY: size.height * 0.30, maxY: size.height * 0.78) }
}

/// Live inputs to a pose that are not geometry.
struct BlobInputs: Equatable {
    /// Signal level per metric, 0...1, used by `.marks`.
    var levels: [Double] = Array(repeating: 0.6, count: 7)
    /// Metrics that are highlighted (e.g. chosen for Health); others stay dim.
    var lit: Set<Metric> = Set(Metric.allCases)
}

enum BlobScenes {
    static let count = Metric.allCases.count

    /// The disc as the blobs make it: seven blobs of different sizes packed a little unevenly inside a circle, so the
    /// silhouette is round and the inside is not a pie chart. Unit disc, x right and y down, as fractions of its radius.
    static let discLayout: [(x: CGFloat, y: CGFloat, r: CGFloat)] = [
        (0.48, -0.45, 0.33),  // heart rate
        (-0.57, -0.33, 0.31),  // hrv
        (-0.04, 0.03, 0.36),  // sleep
        (-0.11, 0.67, 0.30),  // readiness
        (0.60, 0.28, 0.32),  // steps
        (-0.64, 0.38, 0.27),  // spo2
        (0.06, -0.74, 0.24),  // skin temperature
    ]

    /// One blob of the disc with a slow independent breath, so the packing is never quite still.
    static func discBlob(_ i: Int, time: Double) -> (x: CGFloat, y: CGFloat, r: CGFloat) {
        let l = discLayout[i]
        let ph = Double(i) * 1.7
        return (
            l.x + 0.018 * CGFloat(sin(time * 0.9 + ph)), l.y + 0.018 * CGFloat(cos(time * 0.8 + ph * 1.3)),
            l.r * CGFloat(1 + 0.03 * sin(time * 1.3 + ph))
        )
    }

    /// Target for blob `i` at `time` (seconds) in a field of `size`.
    static func target(
        _ pose: BlobPose, index i: Int, size: CGSize, time: Double, inputs: BlobInputs = BlobInputs(),
        stage: BlobStage? = nil, elapsed: Double = 0
    ) -> BlobTarget {
        let w = size.width, h = size.height
        let st = stage ?? .fallback(size)
        let cy = st.midY
        // Unit of composition: the width, unless the free band is short (small phones, large text).
        let u = min(w, st.height * 1.08)
        let n = CGFloat(count)
        let fi = CGFloat(i)

        switch pose {
        case .welcome:
            // A loose mass that merges; the readiness blob sits highest.
            let layout: [(CGFloat, CGFloat, CGFloat)] = [
                (-0.22, -0.04, 0.14),  // heart rate
                (0.20, -0.16, 0.115),  // hrv
                (-0.02, 0.14, 0.17),  // sleep
                (0.00, -0.22, 0.10),  // readiness
                (0.28, 0.06, 0.12),  // steps
                (-0.30, 0.20, 0.09),  // spo2
                (0.22, 0.26, 0.10),  // temp
            ]
            let l = layout[i]
            // The first screen is the calm one: a slow breath and a small drift.
            let breath = CGFloat(1 + 0.025 * sin(time * 1.1 + Double(i) * 1.1))
            return BlobTarget(x: w * 0.5 + u * l.0, y: cy + u * l.1, radius: u * l.2 * breath, wobble: 0.06, drift: 7)

        case .bluetooth:
            // An elastic ring that turns and breathes; each blob pulses a beat behind its neighbour.
            let a = time * 0.55 + Double(i) / Double(count) * 2 * .pi
            let elastic = CGFloat(1 + 0.10 * sin(time * 1.8 + Double(i) * 0.9))
            let ring = u * 0.30 * elastic
            let pulse = CGFloat(1 + 0.22 * sin(time * 2.4 - Double(i) * 0.9))
            return BlobTarget(
                x: w * 0.5 + ring * CGFloat(cos(a)), y: cy + ring * CGFloat(sin(a)), radius: u * 0.085 * pulse,
                wobble: 0.11, drift: 6)

        case .mount:
            // A 3D watch (`Watch3D`) turns up beside a loose mass of blobs. When it has turned over, the blobs fly to the back of the
            // case and settle there as the disc. The blobs stay plain 2D: they came from the previous scene and go on to the next.
            let half = Watch3D.half(size: size, stage: stage)
            if elapsed < Watch3D.flyStart + Double(i) * 0.07 {
                let mass: [(CGFloat, CGFloat, CGFloat)] = [
                    (-0.22, 0.04, 0.14), (0.20, 0.16, 0.115), (-0.02, -0.14, 0.17), (0.0, 0.22, 0.10), (0.28, -0.06, 0.12), (-0.30, -0.20, 0.09), (0.22, -0.26, 0.10),
                ]
                let l = mass[i]
                let breath = CGFloat(1 + 0.025 * sin(time * 1.1 + Double(i) * 1.1))
                // The mass sits at the upper left of the watch, the way the 3D watch sits.
                let c = Watch3D.centre(size: size, stage: stage)
                return BlobTarget(x: c.x - half * 0.78 + half * l.0, y: c.y - half * 0.5 + half * l.1, radius: half * 0.9 * l.2 * breath, wobble: 0.06, drift: 5)
            }
            let d = discBlob(i, time: time)
            let p = Watch3D.project(SIMD3(-Double(d.x) * Watch3D.discRadius, -Double(d.y) * Watch3D.discRadius, Watch3D.discZ), at: elapsed, size: size, stage: stage)
            return BlobTarget(x: p.point.x, y: p.point.y, radius: d.r * CGFloat(Watch3D.discRadius) * p.k, wobble: 0.05, drift: 0, stiff: 190 + Float(i) * 14)

        case .searching:
            // A slow sonar: the ring swells and settles once every 2.6 s, each blob a little behind the previous one.
            // Calmer than the other scenes on purpose: the user is waiting and reading.
            let phase = time * 2 * .pi / 2.6 - Double(i) * 0.40
            let breath = CGFloat(0.5 + 0.5 * sin(phase))
            let a = time * 0.18 + Double(i) / Double(count) * 2 * .pi
            let ring = u * (0.21 + 0.09 * breath)
            return BlobTarget(
                x: w * 0.5 + ring * CGFloat(cos(a)), y: cy + ring * CGFloat(sin(a)),
                radius: u * (0.050 + 0.014 * breath), wobble: 0.07, drift: 0)

        case .fused:
            // The disc: seven blobs packed unevenly into a round shape that pulses like a heart.
            let R = u * 0.2
            let beat = CGFloat(1 + 0.04 * sin(time * 5.2))
            let d = discBlob(i, time: time)
            return BlobTarget(x: w * 0.5 + d.x * R * beat, y: cy + d.y * R * beat, radius: d.r * R * beat, wobble: 0.05, drift: 0)

        case .burst:
            // The disc exhales: the blobs fly out to a wide ring, half way to their marks.
            let a = -Double.pi / 2 + Double(i) / Double(count) * 2 * .pi
            let ring = u * 0.36
            return BlobTarget(
                x: w * 0.5 + ring * CGFloat(cos(a)), y: cy + ring * CGFloat(sin(a)), radius: u * 0.075, morph: 0.5,
                rotation: CGFloat(a), wobble: 0.04, drift: 0)

        case .marks, .marksHigh:
            let x = w * (0.5 + (fi - (n - 1) / 2) * 0.125)
            let rowY = cy
            let level = CGFloat(inputs.levels.indices.contains(i) ? inputs.levels[i] : 0.6)
            let metric = Metric(rawValue: i) ?? .heartRate
            let lit = inputs.lit.contains(metric)
            let r = min(w * 0.034, st.height * 0.26) * (lit ? (0.62 + 0.80 * level) : 0.40)
            let bob = CGFloat(sin(time * 2.6 - Double(i) * 0.7)) * min(7, st.height * 0.08)
            return BlobTarget(x: x, y: rowY + bob, radius: r, morph: 1, rotation: CGFloat(sin(time * 1.4 + Double(i)) * 0.12), wobble: 0, drift: 0)

        case .flood:
            // The marks swell until colour fills the screen.
            let cols: [(CGFloat, CGFloat)] = [
                (0.20, 0.18), (0.80, 0.22), (0.50, 0.40), (0.15, 0.60), (0.85, 0.62), (0.35, 0.85), (0.70, 0.88),
            ]
            let c = cols[i]
            return BlobTarget(x: w * c.0, y: h * c.1, radius: w * 0.62, morph: 0, wobble: 0.12, drift: 30)

        case .settle:
            // A small row of marks at the top, the way Today will wear them.
            let x = w * (0.5 + (fi - (n - 1) / 2) * 0.095)
            return BlobTarget(x: x, y: h * 0.30, radius: w * 0.022, morph: 1, wobble: 0, drift: 0)
        }
    }
}
