import XCTest

@testable import Caseback

final class BlobSimulatorTests: XCTestCase {
    private let size = CGSize(width: 390, height: 844)

    private func run(_ sim: BlobSimulator, seconds: Double, from start: Double = 0) -> Double {
        var t = start
        while t < start + seconds {
            sim.advance(to: t, size: size)
            t += 1.0 / 60
        }
        return t
    }

    func testBlobsSwellOutOfOnePoint() {
        let sim = BlobSimulator()
        sim.advance(to: 0, size: size)
        XCTAssertTrue(sim.states.allSatisfy { $0.radius == 0 }, "the field starts as a point")
        _ = run(sim, seconds: 2)
        XCTAssertTrue(sim.states.allSatisfy { $0.radius > 5 })
    }

    func testRadiusAndMorphNeverLeaveTheirRange() {
        let sim = BlobSimulator()
        var t = 0.0
        let poses: [BlobPose] = [.welcome, .bluetooth, .mount, .searching, .fused, .burst, .marks, .flood, .settle, .welcome]
        for pose in poses {
            sim.setPose(pose, at: t, size: size)
            t = run(sim, seconds: 1.2, from: t)
            for s in sim.states {
                XCTAssertGreaterThanOrEqual(s.radius, 0, "pose \(pose)")
                XCTAssertTrue((0...1).contains(s.morph), "pose \(pose) morph \(s.morph)")
                XCTAssertTrue(s.pos.x.isFinite && s.pos.y.isFinite, "pose \(pose)")
            }
        }
    }

    func testBlobsConvergeOnTheMarksRow() {
        let sim = BlobSimulator()
        sim.setPose(.marks, at: 0, size: size)
        _ = run(sim, seconds: 4)
        for (i, s) in sim.states.enumerated() {
            let t = BlobScenes.target(.marks, index: i, size: size, time: 4, stage: nil)
            XCTAssertEqual(CGFloat(s.pos.x), t.x, accuracy: 6)
            XCTAssertEqual(s.morph, 1, accuracy: 0.02)
        }
    }

    func testMarksAreCrispAndBlobsFuse() {
        let sim = BlobSimulator()
        sim.setPose(.fused, at: 0, size: size)
        _ = run(sim, seconds: 3)
        let fused = sim.smoothness
        sim.setPose(.marks, at: 3, size: size)
        _ = run(sim, seconds: 4, from: 3)
        XCTAssertGreaterThan(fused, 5, "the blobs of the disc need a neck to join")
        XCTAssertLessThan(sim.smoothness, 3, "marks must stay separate crisp shapes")
    }

    func testReduceMotionDoesNotOvershootOrDrift() {
        let sim = BlobSimulator()
        sim.reduceMotion = true
        sim.setPose(.marks, at: 0, size: size)
        var t = 0.0
        var maxX: Float = 0
        while t < 3 {
            sim.advance(to: t, size: size)
            maxX = max(maxX, sim.states[6].pos.x)
            t += 1.0 / 60
        }
        let target = Float(BlobScenes.target(.marks, index: 6, size: size, time: 0, stage: nil).x)
        XCTAssertLessThanOrEqual(maxX, target + 0.5, "eases straight to the target")
        XCTAssertTrue(sim.states.allSatisfy { $0.wobble == 0 && $0.drift == 0 && $0.stretch == 0 })
    }

    func testPackedLayoutMatchesTheShaderStride() {
        let sim = BlobSimulator()
        sim.advance(to: 0, size: size)
        XCTAssertEqual(sim.packed(time: 0).count, BlobScenes.count * 12)
    }

    func testStageKeepsBlobsOutOfTheTitle() {
        // A short stage (small phone): nothing in the welcome mass may reach above the stage's top edge by much.
        let stage = BlobStage(minY: 300, maxY: 480)
        for i in 0..<BlobScenes.count {
            let t = BlobScenes.target(.welcome, index: i, size: CGSize(width: 375, height: 667), time: 0, stage: stage)
            XCTAssertGreaterThan(t.y - t.radius, stage.minY - 30, "blob \(i) top \(t.y - t.radius)")
            XCTAssertLessThan(t.y + t.radius, stage.maxY + 30, "blob \(i) bottom \(t.y + t.radius)")
        }
    }

    func testBeatPulseDecays() {
        let sim = BlobSimulator()
        sim.advance(to: 0, size: size)
        sim.pulseBeat()
        XCTAssertEqual(sim.beatPulse, 1)
        _ = run(sim, seconds: 0.5)
        XCTAssertEqual(sim.beatPulse, 0, accuracy: 0.001)
    }
}

final class Watch3DTests: XCTestCase {
    private let size = CGSize(width: 390, height: 844)
    private let stage = BlobStage(minY: 280, maxY: 640)

    func testTheWatchFitsTheFreeBand() {
        // The whole watch with its straps is about `extent` units tall and must stay inside the band.
        let top = Watch3D.project(SIMD3(0, 2.45, 0), at: 9, size: size, stage: stage).point
        let bottom = Watch3D.project(SIMD3(0, -2.62, 0), at: 9, size: size, stage: stage).point
        XCTAssertGreaterThan(top.y, stage.minY - 20)
        XCTAssertLessThan(bottom.y, stage.maxY + 20)
    }

    func testTheCentreOfTheDialIsTheCentreOfTheBand() {
        let p = Watch3D.project(SIMD3(0, 0, 0), at: 9, size: size, stage: stage).point
        XCTAssertEqual(p.x, size.width / 2, accuracy: 0.5)
        XCTAssertEqual(p.y, stage.midY, accuracy: 0.5)
    }

    func testTheBlobsEndOnTheBackOfTheCaseAndStayInsideTheScreen() {
        for i in 0..<BlobScenes.count {
            for e in stride(from: 0.0, through: 9.0, by: 0.25) {
                let t = BlobScenes.target(.mount, index: i, size: size, time: e, stage: stage, elapsed: e)
                XCTAssertTrue((-20...(size.width + 20)) ~= t.x, "blob \(i) at \(e) s: x \(t.x)")
                XCTAssertTrue((stage.minY - 40)...(stage.maxY + 40) ~= t.y, "blob \(i) at \(e) s: y \(t.y)")
            }
            let end = BlobScenes.target(.mount, index: i, size: size, time: 9, stage: stage, elapsed: 9)
            let centre = Watch3D.project(SIMD3(0, 0, Watch3D.discZ), at: 9, size: size, stage: stage)
            XCTAssertLessThan(hypot(end.x - centre.point.x, end.y - centre.point.y), centre.k * 1.0, "the disc is on the back")
        }
    }

    func testTheWatchTurnsOverBeforeTheBlobsLeave() {
        XCTAssertLessThan(Watch3D.turnStart, Watch3D.flyStart)
        XCTAssertLessThan(Watch3D.flyStart, Watch3D.turnEnd)
        XCTAssertLessThan(cos(Watch3D.pose(9).yaw), -0.7, "the back faces the camera when it has turned")
    }
}
