import CoreGraphics
import Foundation
import SceneKit
import SwiftUI
import simd

/// The 3D watch of the mount step (model in `Resources/CasebackWatch.usdz`, built by `tools/watch3d/build_watch.py`).
/// It turns up beside a loose mass of blobs, turns over, and the blobs fly to the back of its case and settle
/// there as the disc. The blobs stay plain 2D: this file holds the pose of the watch over time and the projection the blobs use
/// to find the back of the case.
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

/// The model, in a transparent SceneKit view under the blob field.
struct WatchModelView: UIViewRepresentable {
    var stage: BlobStage?
    /// Seconds since the scene began; nil draws the finished state (Reduce Motion).
    var elapsed: Double

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> SCNView {
        let v = SCNView()
        v.backgroundColor = .clear
        v.isOpaque = false
        v.antialiasingMode = .multisampling4X
        v.allowsCameraControl = false
        v.isUserInteractionEnabled = false
        v.scene = context.coordinator.scene
        v.pointOfView = context.coordinator.cameraNode
        v.rendersContinuously = false
        return v
    }

    func updateUIView(_ v: SCNView, context: Context) {
        context.coordinator.update(view: v, elapsed: elapsed, stage: stage)
    }

    final class Coordinator {
        let scene = SCNScene()
        let cameraNode = SCNNode()
        let holder = SCNNode()
        private var watch: SCNNode?

        init() {
            scene.background.contents = UIColor.clear
            if let url = Bundle.main.url(forResource: "CasebackStudio", withExtension: "hdr") {
                scene.lightingEnvironment.contents = url
                scene.lightingEnvironment.intensity = 1.0
            }
            let cam = SCNCamera()
            cam.zNear = 1
            cam.zFar = 30
            cameraNode.camera = cam
            cameraNode.position = SCNVector3(0, 0, Float(Watch3D.camera))
            scene.rootNode.addChildNode(cameraNode)
            // A key light with soft shadows.
            let key = SCNLight()
            key.type = .directional
            key.intensity = 1200
            key.castsShadow = true
            key.shadowMode = .deferred
            key.shadowRadius = 5
            key.shadowSampleCount = 8
            key.shadowColor = UIColor.black.withAlphaComponent(0.55)
            let lightNode = SCNNode()
            lightNode.light = key
            lightNode.look(at: SCNVector3(0.5, -0.75, -0.45).normalizedVector, up: SCNVector3(0, 1, 0), localFront: SCNVector3(0, 0, -1))
            scene.rootNode.addChildNode(lightNode)
            scene.rootNode.addChildNode(holder)
            if let url = Bundle.main.url(forResource: "CasebackWatch", withExtension: "usdz"), let s = try? SCNScene(url: url) {
                let node = SCNNode()
                for child in s.rootNode.childNodes { node.addChildNode(child) }
                node.enumerateHierarchy { n, _ in
                    n.geometry?.materials.forEach { $0.lightingModel = .physicallyBased }
                }
                holder.addChildNode(node)
                watch = node
            }
        }

        func update(view: SCNView, elapsed: Double, stage: BlobStage?) {
            let size = view.bounds.size
            guard size.width > 1, size.height > 1 else { return }
            let t = elapsed
            let p = Watch3D.pose(t)
            let half = Double(Watch3D.half(size: size, stage: stage))
            let f = Watch3D.focal / p.scale
            let focalPx = half / f
            let c = Watch3D.centre(size: size, stage: stage)
            // Off-axis perspective: the centre of projection is the centre of the free band, so nothing is clipped.
            let n = 1.0, fa = 30.0
            var m = simd_float4x4(0)
            m[0][0] = Float(2 * focalPx / Double(size.width))
            m[1][1] = Float(2 * focalPx / Double(size.height))
            m[2][0] = Float(-(Double(c.x) - Double(size.width) / 2) / (Double(size.width) / 2))
            m[2][1] = Float((Double(c.y) - Double(size.height) / 2) / (Double(size.height) / 2))
            m[2][2] = Float(-(fa + n) / (fa - n))
            m[2][3] = -1
            m[3][2] = Float(-2 * fa * n / (fa - n))
            cameraNode.camera?.projectionTransform = SCNMatrix4(m)

            let rotX = simd_float4x4(simd_quatf(angle: Float(p.pitch), axis: SIMD3<Float>(1, 0, 0)))
            let rotY = simd_float4x4(simd_quatf(angle: Float(p.yaw), axis: SIMD3<Float>(0, 1, 0)))
            holder.simdTransform = rotX * rotY
            view.layer.opacity = Float(p.fade)
            view.setNeedsDisplay()
        }
    }
}

private extension SCNVector3 {
    var normalizedVector: SCNVector3 {
        let l = (x * x + y * y + z * z).squareRoot()
        return l > 0 ? SCNVector3(x / l, y / l, z / l) : self
    }
}

/// The mount step's watch: the model under the blob field, on its own clock that starts when the step appears.
struct MountWatch: View {
    var stage: BlobStage?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var began = Date()

    var body: some View {
        TimelineView(.animation) { timeline in
            WatchModelView(stage: stage, elapsed: reduceMotion ? Watch3D.settled : timeline.date.timeIntervalSince(began))
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
