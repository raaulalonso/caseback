import XCTest

@testable import Caseback

final class DetailFactsTests: XCTestCase {
    func testSleepScorePartsAddUpToTheScore() {
        let b = TodayFixtures.sleep(minutes: 432)
        let parts = SleepScore.parts(segments: b.segments)!
        XCTAssertEqual(parts.score, b.score)
        XCTAssertTrue([parts.duration, parts.efficiency, parts.deep, parts.rem].allSatisfy { (0...1).contains($0) })
        let w = SleepScore.Parts.weights
        XCTAssertEqual(w.duration + w.efficiency + w.deep + w.rem, 1, accuracy: 1e-9)
    }

    func testSleepFactsCountTimeInBedAndAsleep() {
        let segments = [
            SleepSegment(start: 0, end: 100, stage: .light), SleepSegment(start: 100, end: 120, stage: .wake),
            SleepSegment(start: 120, end: 400, stage: .deep),
        ]
        let b = SleepBlock(minutes: 400, deltaMinutes: 0, segments: segments, from: "23:00", to: "05:40")
        let f = SleepFacts.make(b)!
        XCTAssertEqual(f.inBedMinutes, 400)
        XCTAssertEqual(f.asleepMinutes, 380)
        XCTAssertEqual(f.efficiency, 0.95, accuracy: 1e-9)
        XCTAssertNil(SleepFacts.make(SleepBlock(minutes: 0, deltaMinutes: 0, segments: [], from: "", to: "")))
    }

    func testStepsWeekLeavesTodayOut() {
        let days: [Double?] = (0..<30).map { _ in 8000 } + [1000]
        let w = StepsWeek.make(TrendSeries(values: days, calibratingNights: nil, lastIsPartial: true))!
        XCTAssertEqual(w.average, 8000)
        XCTAssertEqual(w.normal, 8000)
        XCTAssertNil(StepsWeek.make(TrendSeries(values: [5000, 6000, 7000], calibratingNights: nil, lastIsPartial: false)), "too few days")
    }

    func testPulseFactsReadTheDay() {
        let s = TodayFixtures.snapshot(.normal)
        let f = PulseFacts.make(s)!
        XCTAssertNotNil(f.lowest)
        XCTAssertLessThan(f.lowest!, f.highest!)
        XCTAssertEqual(f.resting, 58)
        XCTAssertLessThanOrEqual(f.hoursRead, f.hoursElapsed)
        XCTAssertNil(PulseFacts.make(TodaySnapshot()), "no day yet")
    }

    func testRangeTextNeverTouchesTwoSigns() {
        XCTAssertEqual(DetailCopy.rangeText(58...60, .restingHR), "58–60")
        XCTAssertEqual(DetailCopy.rangeText(96...96.2, .spo2), "96")
        let t = DetailCopy.rangeText(-0.1...0.1, .skinTemp)
        XCTAssertFalse(t.contains("−+"))
        XCTAssertTrue(t.contains("−0.1") && t.contains("+0.1"), t)
    }

    func testEveryScreenHasItsThreeAffectsLines() {
        for d in TodayDestination.allKnown {
            let lines = DetailCopy.affects(d)
            XCTAssertEqual(lines.count, 3)
            for (i, l) in lines.enumerated() { XCTAssertFalse(l.hasPrefix("detail.affects"), "missing text for \(d) #\(i + 1)") }
        }
    }

    func testTheDayAndThePulseShareTheirLines() {
        XCTAssertEqual(DetailCopy.affects(.day), DetailCopy.affects(.pulse))
    }
}

@MainActor
final class DetailNavigationTests: XCTestCase {
    func testNavigateKeepsTheOriginAndChangesTheScreen() {
        let m = TodayModel(snapshot: TodayFixtures.snapshot(.normal))
        let origin = CGRect(x: 10, y: 20, width: 100, height: 80)
        m.open(.readiness, from: origin)
        m.navigate(.hrv)
        XCTAssertEqual(m.selected, .hrv)
        XCTAssertEqual(m.origin, origin)
        m.close()
        XCTAssertNil(m.selected)
    }

    func testEveryTrendMetricOpensAScreen() {
        for m in TrendMetric.allCases { XCTAssertTrue(TodayDestination.allKnown.contains(m.destination), "\(m)") }
    }
}

final class DetailCaveatTests: XCTestCase {
    func testEveryScreenHasItsCaveatBehindTheInfo() {
        for d in TodayDestination.allKnown {
            let c = DetailCopy.caveat(d)
            XCTAssertFalse(c.contains("detail.caveat"), "missing caveat for \(d)")
            XCTAssertTrue(c.hasSuffix(L("detail.footer")))
        }
    }

    /// The limits of the device are said once, in the "i", and never as lines of the screen itself.
    func testTheLinesOnTheScreenDoNotTalkAboutTheDeviceFailing() {
        let words = ["loose", "flojo", "unreliable", "fiable", "fail", "fallar", "estimat", "estimaci"]
        for d in TodayDestination.allKnown {
            for line in DetailCopy.affects(d) {
                let l = line.lowercased()
                XCTAssertFalse(words.contains { l.contains($0) }, "\(d): \(line)")
            }
        }
    }
}
