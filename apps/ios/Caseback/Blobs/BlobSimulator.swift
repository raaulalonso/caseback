import CoreGraphics
import Foundation
import simd

/// Spring physics for the seven blobs. A reference type that is advanced from the render loop: it is not observable
/// state, so it never invalidates a view by itself.
final class BlobSimulator {
    struct State {
        var pos = SIMD2<Float>(0, 0)
        var vel = SIMD2<Float>(0, 0)
        var radius: Float = 0
        var radiusVel: Float = 0
        var morph: Float = 0
        var morphVel: Float = 0
        var rotation: Float = 0
        var rotationVel: Float = 0
        var wobble: Float = 0.06
        var drift: Float = 0
        var stretch: Float = 0
        var stretchAngle: Float = 0
    }

    private(set) var states: [State] = Array(repeating: State(), count: BlobScenes.count)
    private var lastTime: Double?
    private var seeded = false
    private(set) var pose: BlobPose = .welcome
    private var poseSince: Double = 0

    /// Finger position in points, if touching.
    var touch: CGPoint?
    var inputs = BlobInputs()
    var stage: BlobStage?
    /// Bumped on every detected heartbeat; the heart-rate mark pulses.
    var beatPulse: Float = 0
    var reduceMotion = false

    /// Neck width of the smooth union, in points: wide while the blobs are blobs, nearly zero once they are marks so
    /// each mark stays a crisp separate shape.
    var smoothness: Float {
        if pose == .mount {
            // A loose mass while the watch turns; once the blobs have landed on its back they keep their outlines, packed into a disc.
            let e = Float((lastTime ?? 0) - poseSince - Watch3D.flyStart - 0.8)
            return 16 - 10 * min(max(e / 0.6, 0), 1)
        }
        if pose == .fused { return 7 }
        let m = states.map(\.morph).reduce(0, +) / Float(max(states.count, 1))
        return 16 - 14.6 * min(max(m * 1.15, 0), 1)
    }

    /// Per-blob stiffness: staggered so the blobs arrive one after another.
    static func stiffness(_ i: Int) -> Float { 46 + Float(i) * 9 }
    static let positionDamping: Float = 0.55

    func setPose(_ new: BlobPose, at time: Double, size: CGSize) {
        guard new != pose else { return }
        let old = pose
        pose = new
        poseSince = time
        if new == .burst, !reduceMotion {
            // The fused disc bursts outward from its centre.
            let centre = SIMD2<Float>(Float(size.width / 2), Float((stage ?? .fallback(size)).midY))
            for i in states.indices {
                var d = states[i].pos - centre
                let len = simd_length(d)
                d = len > 0.01 ? d / len : SIMD2<Float>(cos(Float(i) * 0.9), sin(Float(i) * 0.9))
                states[i].vel += d * (900 + Float(i) * 60)
                states[i].radiusVel += 30
            }
        }
        if !reduceMotion, new != .burst, new != .flood, seeded {
            // Every change of scene whirls the blobs around the centre of the stage before they settle: motion design,
            // not a cross-fade. Neighbours spin in opposite senses so the field shears and merges on the way.
            let centre = SIMD2<Float>(Float(size.width / 2), Float((stage ?? .fallback(size)).midY))
            for i in states.indices {
                let d = states[i].pos - centre
                let tangent = SIMD2<Float>(-d.y, d.x)
                let len = max(simd_length(tangent), 1)
                let sign: Float = i % 2 == 0 ? 1 : -1
                states[i].vel += tangent / len * (520 + Float(i) * 45) * sign
                if new == .marks || new == .marksHigh {
                    // The marks spin once into place.
                    states[i].rotation -= .pi * 2
                    states[i].rotationVel += 0
                }
            }
        }
        if new == .flood, !reduceMotion {
            for i in states.indices { states[i].radiusVel += 400 }
        }
        _ = old
    }

    func pulseBeat() { beatPulse = 1 }

    /// Advances the simulation to `time`.
    func advance(to time: Double, size: CGSize) {
        guard size.width > 1, size.height > 1 else { return }
        if !seeded {
            // Everything starts as a point at the centre of the field and swells out of it.
            let centre = SIMD2<Float>(Float(size.width / 2), Float((stage ?? .fallback(size)).midY))
            for i in states.indices {
                states[i].pos = centre
                states[i].radius = 0
            }
            seeded = true
        }
        let last = lastTime ?? time
        lastTime = time
        var dt = Float(min(max(time - last, 0), 1.0 / 20.0))
        if dt <= 0 { dt = 0 }
        beatPulse = max(0, beatPulse - dt * 4.0)

        if reduceMotion {
            // No overshoot, no drift: ease straight to the target (about 240 ms).
            let a = 1 - exp(-dt * 14)
            for i in states.indices {
                let t = BlobScenes.target(pose, index: i, size: size, time: 0, inputs: inputs, stage: stage, elapsed: 99)
                states[i].pos += (SIMD2<Float>(Float(t.x), Float(t.y)) - states[i].pos) * a
                states[i].radius += (Float(t.radius) - states[i].radius) * a
                states[i].morph += (Float(t.morph) - states[i].morph) * a
                states[i].wobble = 0
                states[i].drift = 0
                states[i].vel = .zero
            }
            return
        }

        let steps = max(1, Int(ceil(dt / (1.0 / 120.0))))
        let h = dt / Float(steps)
        for _ in 0..<steps {
            for i in states.indices {
                step(i, dt: h, time: time, size: size)
            }
        }
    }

    private func step(_ i: Int, dt: Float, time: Double, size: CGSize) {
        let t = BlobScenes.target(pose, index: i, size: size, time: time, inputs: inputs, stage: stage, elapsed: time - poseSince)
        var s = states[i]

        // Position: underdamped spring (a little overshoot), plus touch repulsion.
        // A pen follows its line on a stiff spring: close enough to write with, loose enough to swing round the corners.
        let k = t.stiff ?? Self.stiffness(i)
        let c = 2 * Self.positionDamping * sqrt(k)
        let target = SIMD2<Float>(Float(t.x), Float(t.y))
        var force = (target - s.pos) * k - s.vel * c
        if let touch {
            let tp = SIMD2<Float>(Float(touch.x), Float(touch.y))
            var d = s.pos - tp
            let len = simd_length(d)
            let reach = Float(size.width) * 0.38
            if len < reach, len > 0.01 {
                d /= len
                let q = 1 - len / reach
                force += d * (14_000 * q * q)
            }
        }
        s.vel += force * dt
        s.pos += s.vel * dt

        // Radius and morph: critically damped so they never go negative.
        func critical(_ x: inout Float, _ v: inout Float, _ target: Float, omega: Float) {
            let f = (target - x) * omega * omega - 2 * omega * v
            v += f * dt
            x += v * dt
        }
        let heartPulse = (Metric(rawValue: i) == .heartRate && (pose == .marks || pose == .marksHigh)) ? beatPulse * 0.55 : 0
        critical(&s.radius, &s.radiusVel, max(Float(t.radius) * (1 + heartPulse), 0), omega: 9 + Float(i) * 0.6)
        if s.radius < 0 { s.radius = 0 }
        critical(&s.morph, &s.morphVel, Float(t.morph), omega: 7)
        s.morph = min(max(s.morph, 0), 1)
        critical(&s.rotation, &s.rotationVel, Float(t.rotation), omega: 6)
        s.wobble += (Float(t.wobble) - s.wobble) * min(1, dt * 4)
        s.drift += (Float(t.drift) - s.drift) * min(1, dt * 3)
        let speed = simd_length(s.vel)
        let wanted = min(speed / 1500, 0.55) * (1 - s.morph)
        s.stretch += (wanted - s.stretch) * min(1, dt * 14)
        if speed > 30 {
            let a = atan2(s.vel.y, s.vel.x)
            var da = a - s.stretchAngle
            while da > .pi { da -= 2 * .pi }
            while da < -.pi { da += 2 * .pi }
            s.stretchAngle += da * min(1, dt * 18)
        }
        states[i] = s
    }

    /// Packs the state for the shader: x, y, r, morph, kind, rotation, wobble, red, green, blue, stretch, stretchAngle per blob.
    func packed(time: Double) -> [Float] {
        var out: [Float] = []
        out.reserveCapacity(states.count * 12)
        for (i, s) in states.enumerated() {
            let metric = Metric(rawValue: i) ?? .heartRate
            let driftPhase = Double(i) * 1.3
            let dx = s.drift * Float(sin(time * 0.62 + driftPhase) + 0.6 * sin(time * 1.37 + driftPhase * 2))
            let dy = s.drift * Float(cos(time * 0.51 + driftPhase) + 0.6 * cos(time * 1.19 + driftPhase * 1.5))
            let rgb = Self.rgb(metric)
            out += [
                s.pos.x + dx, s.pos.y + dy, max(s.radius, 0), s.morph, metric.markKind, s.rotation, s.wobble,
                rgb.0, rgb.1, rgb.2, s.stretch, s.stretchAngle,
            ]
        }
        return out
    }

    static func rgb(_ m: Metric) -> (Float, Float, Float) {
        // The shader outputs sRGB values directly, so pass the sRGB components of the token.
        let h = m.hex
        return (Float((h >> 16) & 0xFF) / 255, Float((h >> 8) & 0xFF) / 255, Float(h & 0xFF) / 255)
    }
}
