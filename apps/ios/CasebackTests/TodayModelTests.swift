import XCTest

@testable import Caseback

final class TodaySentenceTests: XCTestCase {
    func testSleepAndHrvAboveShareOnePredicate() {
        let s = ReadinessSentence.make(ReadinessComponents(sleep: 1.0, hrv: 1.1, rhr: -0.6, temp: 0))
        XCTAssertEqual(s, L("today.merge.above", ReadinessSentence.name(.sleep).prefix(1).uppercased() + ReadinessSentence.name(.sleep).dropFirst(), ReadinessSentence.name(.hrv)))
    }

    func testRestingHeartRateWordsFollowTheHeartRateNotTheSign() {
        // A positive z for resting HR means a lower heart rate.
        XCTAssertEqual(ReadinessSentence.phrase(.rhr, .above), L("today.phrase.rhr.above"))
        XCTAssertEqual(ReadinessSentence.phrase(.rhr, .below), L("today.phrase.rhr.below"))
        let s = ReadinessSentence.make(ReadinessComponents(sleep: 0.1, hrv: -0.1, rhr: 1.4, temp: nil))
        XCTAssertTrue(s.lowercased().contains(L("today.phrase.rhr.above").lowercased()), s)
    }

    func testOnlyTheTwoLargestAreNamedAndAThirdNearUsualIsAdded() {
        let c = ReadinessComponents(sleep: 0.2, hrv: 1.5, rhr: -1.2, temp: 0)
        let s = ReadinessSentence.make(c)
        XCTAssertTrue(s.lowercased().contains(L("today.phrase.hrv.above").lowercased()), s)
        XCTAssertTrue(s.lowercased().contains(L("today.phrase.rhr.below").lowercased()), s)
        XCTAssertTrue(s.contains(L("today.sentence.near", "Sueño")) || s.lowercased().contains(ReadinessSentence.name(.sleep)), s)
    }

    func testSkinTemperatureIsOnlyMentionedWhenOff() {
        let near = ReadinessSentence.make(ReadinessComponents(sleep: 0.9, hrv: 0.1, rhr: 0.0, temp: 0))
        XCTAssertFalse(near.lowercased().contains(L("today.phrase.temp.below").lowercased()))
        let off = ReadinessSentence.make(ReadinessComponents(sleep: 0.1, hrv: 0.1, rhr: 0.0, temp: -1.6))
        XCTAssertTrue(off.lowercased().contains(L("today.phrase.temp.below").lowercased()), off)
    }

    func testMissingSignalsAreCounted() {
        let s = ReadinessSentence.make(ReadinessComponents(sleep: 0.6, hrv: 0.4, rhr: 0.3, temp: nil))
        XCTAssertTrue(s.hasSuffix(L("today.sentence.signals", 3, 4)), s)
        XCTAssertFalse(ReadinessSentence.make(ReadinessComponents(sleep: 0.6, hrv: 0.4, rhr: 0.3, temp: 0)).contains(L("today.sentence.signals", 3, 4)))
    }

    func testNoComponentsNoSentence() {
        XCTAssertEqual(ReadinessSentence.make(ReadinessComponents()), "")
    }
}

final class TodayFormatTests: XCTestCase {
    func testDurationAndDeltas() {
        XCTAssertEqual(TodayFormat.duration(minutes: 432).value, "7 h 12")
        XCTAssertEqual(TodayFormat.duration(minutes: 45).unit, "min")
        XCTAssertEqual(TodayFormat.sleepDelta(minutes: 25), "+25 min")
        XCTAssertEqual(TodayFormat.sleepDelta(minutes: -76), "−1 h 16")
        XCTAssertEqual(TodayFormat.signed(-4), "−4")
        XCTAssertEqual(TodayFormat.signed(0), "0")
        XCTAssertEqual(TodayFormat.ageShort(minutes: 9), "9 min")
        XCTAssertEqual(TodayFormat.ageShort(minutes: 192), "3 h")
    }
}

final class PullResistanceTests: XCTestCase {
    func testTheSheetResistsBeforeTheDetentAndRunsAheadAfterIt() {
        let d = PullResistance.detent
        XCTAssertEqual(PullResistance.displacement(0), 0)
        XCTAssertEqual(PullResistance.displacement(d / 2), d / 2 * PullResistance.resisted, accuracy: 0.001)
        // Continuous at the detent, then faster than the finger.
        XCTAssertEqual(PullResistance.displacement(d), d * PullResistance.resisted, accuracy: 0.001)
        XCTAssertGreaterThan(PullResistance.displacement(d + 100), PullResistance.displacement(d) + 100)
        XCTAssertEqual(PullResistance.displacement(-30), 0, "never moves the wrong way")
    }

    func testDisplacementNeverDecreases() {
        var last: CGFloat = 0
        for t in stride(from: CGFloat(0), through: 600, by: 3) {
            let d = PullResistance.displacement(t)
            XCTAssertGreaterThanOrEqual(d, last)
            last = d
        }
    }

    func testCommitNeedsTheDetentOrAFlick() {
        XCTAssertFalse(PullResistance.committed(travel: PullResistance.detent - 1, velocity: 100))
        XCTAssertTrue(PullResistance.committed(travel: PullResistance.detent, velocity: 0))
        XCTAssertTrue(PullResistance.committed(travel: 10, velocity: PullResistance.flick + 1))
        // A gentle pull that is clearly meant counts too.
        XCTAssertTrue(PullResistance.committed(travel: PullResistance.gentle.travel, velocity: PullResistance.gentle.velocity + 1))
        XCTAssertFalse(PullResistance.committed(travel: 10, velocity: PullResistance.gentle.velocity + 1))
    }
}

@MainActor
final class DrawerControllerTests: XCTestCase {
    func testOnlyAMostlyVerticalUpwardPullStartsWhenClosed() {
        let c = DrawerController()
        XCTAssertTrue(c.accepts(dx: 4, dy: -30))
        XCTAssertFalse(c.accepts(dx: 40, dy: -30), "a sideways swipe belongs to the pages")
        XCTAssertTrue(c.accepts(dx: 20, dy: -30), "a slightly diagonal pull still counts")
        XCTAssertFalse(c.accepts(dx: 0, dy: 30), "a downward pull does nothing while closed")
    }

    func testFollowsThePullWithResistanceAndFallsBackWhenShort() {
        let c = DrawerController()
        c.distance = 600
        c.begin()
        c.drag(travel: 16)
        XCTAssertEqual(c.progress, PullResistance.displacement(16) / 600, accuracy: 0.0001)
        XCTAssertGreaterThan(c.progress, 0)
        XCTAssertLessThan(c.progress, 0.05)
        c.end(travel: 16, velocity: 0)
        XCTAssertFalse(c.isOpen)
        XCTAssertFalse(c.isDragging)
    }

    func testOpensPastTheDetentAndClosesWithAPullDownAtTheTop() {
        let c = DrawerController()
        c.distance = 600
        c.begin()
        c.drag(travel: 300)
        XCTAssertGreaterThan(c.progress, 0.3)
        c.end(travel: 300, velocity: 0)
        XCTAssertTrue(c.isOpen)

        c.scrollAtTop = false
        XCTAssertFalse(c.accepts(dx: 0, dy: 40), "scrolled content is not closed by a pull down")
        c.scrollAtTop = true
        XCTAssertTrue(c.accepts(dx: 0, dy: 40))
        c.begin()
        c.drag(travel: 20)
        XCTAssertLessThan(c.progress, 1)
        c.end(travel: 200, velocity: 0)
        XCTAssertFalse(c.isOpen)
    }

    func testAFlickOpensEvenBeforeTheDetent() {
        let c = DrawerController()
        c.distance = 600
        c.begin()
        c.drag(travel: 20)
        c.end(travel: 20, velocity: 1500)
        XCTAssertTrue(c.isOpen)
    }
}

final class InsightsTests: XCTestCase {
    func testSignalsComeInTheOrderTheScoreWeighsThem() {
        let ids = TodayInsights.signals(TodayFixtures.snapshot(.normal)).map(\.id)
        XCTAssertEqual(ids, ["hrv", "rhr", "sleep", "temp"])
    }

    func testEverySignalStatesANumberAndNeverGivesAdvice() {
        for s in TodayInsights.signals(TodayFixtures.snapshot(.normal)) {
            XCTAssertTrue((s.value ?? s.detail).contains { $0.isNumber }, "\(s.id)")
            XCTAssertFalse(s.detail.contains("!"))
        }
    }

    func testStatusFollowsTheNumberAgainstTheMedian() {
        XCTAssertEqual(TodayInsights.status(delta: 6, baseline: 35, inverse: false), .above)
        XCTAssertEqual(TodayInsights.status(delta: -6, baseline: 35, inverse: false), .below)
        XCTAssertEqual(TodayInsights.status(delta: 1, baseline: 62, inverse: false), .near)
        // Resting heart rate is never "above": lower or higher.
        XCTAssertEqual(TodayInsights.status(delta: -4, baseline: 62, inverse: true), .lower)
        XCTAssertEqual(TodayInsights.status(delta: 8, baseline: 62, inverse: true), .higher)
    }

    func testRestingHeartRateDirectionFollowsTheNumber() {
        var s = TodayFixtures.snapshot(.normal)
        s.restingHR = SeriesBlock(value: "66", unit: "bpm", delta: nil, series: [60, 61, 60, 62, 61, 60, 66], baseline: 62)
        let rhr = TodayInsights.signals(s).first { $0.id == "rhr" }!
        XCTAssertEqual(rhr.status, .higher)
        XCTAssertTrue(rhr.detail.hasPrefix("+4"))
    }

    func testSkinTemperatureIsCalibratingNotMissing() {
        let t = TodayInsights.signals(TodayFixtures.snapshot(.normal)).first { $0.id == "temp" }!
        XCTAssertEqual(t.status, .calibrating(night: 3))
        XCTAssertNil(t.value)
    }

    func testMissingSignalsAreListedAndAPeekAlwaysExists() {
        let partial = TodayFixtures.snapshot(.partial)
        XCTAssertTrue(TodayInsights.signals(partial).contains { $0.id == "missing-temp" || $0.id == "temp" })
        for scenario in TodayScenario.allCases where scenario != .unpaired {
            XCTAssertFalse(TodayInsights.peek(TodayFixtures.snapshot(scenario)).isEmpty, "\(scenario)")
        }
    }

    func testSleepSummaryAddsUpToTheNight() {
        let s = TodayFixtures.snapshot(.normal)
        let summary = TodayInsights.sleepSummary(s)!
        XCTAssertEqual(summary.stages.map(\.stage), [.deep, .rem, .light, .wake])
        XCTAssertEqual(summary.stages.reduce(0) { $0 + $1.minutes }, s.sleep!.minutes)
    }

    func testDaySummaryOnlyCountsWhatHappened() {
        let d = TodayInsights.daySummary(TodayFixtures.snapshot(.normal))!
        XCTAssertEqual(d.steps, 4210)
        XCTAssertEqual(d.hoursElapsed, 9)
        XCTAssertLessThanOrEqual(d.hoursRead, d.hoursElapsed)
        XCTAssertNotNil(d.heartRate)
    }

    func testNoDataHasNoNightConclusions() {
        let s = TodayFixtures.snapshot(.noData)
        let ids = TodayInsights.signals(s).map(\.id)
        XCTAssertFalse(ids.contains("sleep")); XCTAssertFalse(ids.contains("rhr"))
        XCTAssertNil(TodayInsights.sleepSummary(s))
    }
}

@MainActor
final class TodayModelTests: XCTestCase {
    func testEveryScenarioBuildsASnapshot() {
        for scenario in TodayScenario.allCases {
            let s = TodayFixtures.snapshot(scenario)
            XCTAssertEqual(s.tape.columns.count, 96, "\(scenario)")
            XCTAssertEqual(s.paired, scenario != .unpaired)
        }
    }

    func testOnlyRealProblemsInterruptThePanel() {
        XCTAssertNil(TodayFixtures.snapshot(.normal).alert)
        XCTAssertNil(TodayFixtures.snapshot(.outOfRange).alert, "out of range is normal")
        XCTAssertEqual(TodayFixtures.snapshot(.bondLost).alert, .bondLost)
        XCTAssertEqual(TodayFixtures.snapshot(.lowBattery).alert, .batteryCritical(4))
        XCTAssertEqual(TodayFixtures.snapshot(.bluetoothOff).alert, .bluetoothOff)
    }

    func testCalibratingHasNoScore() {
        guard case .calibrating(let day) = TodayFixtures.snapshot(.calibrating).readiness else { return XCTFail() }
        XCTAssertEqual(day, 3)
    }

    func testNoDataHasNoNight() {
        let s = TodayFixtures.snapshot(.noData)
        XCTAssertEqual(s.readiness, .noData)
        XCTAssertNil(s.sleep)
        XCTAssertNil(s.restingHR?.value)
    }

    func testTapeHasHolesAndNeverDrawsTheFuture() {
        let t = TodayFixtures.snapshot(.normal).tape
        XCTAssertTrue(t.columns.contains { $0.hrMin == nil && $0.hrMax == nil })
        XCTAssertTrue(t.columns.enumerated().allSatisfy { $0.offset * 15 < t.nowMinute || $0.element.hrMin == nil })
        XCTAssertEqual(t.hourly.count, 24)
        XCTAssertNil(t.hourly[23], "an hour that has not happened is empty")
    }

    func testBackfillingTapeOnlyHasWhatArrived() {
        let t = TodayFixtures.snapshot(.backfilling).tape
        XCTAssertTrue(t.columns.enumerated().allSatisfy { $0.offset * 15 < 180 || $0.element.hrMin == nil })
    }

    func testSleepStagesCoverTheNightWithoutGaps() {
        let b = TodayFixtures.sleep(minutes: 432)
        XCTAssertEqual(b.segments.first?.start, 0)
        XCTAssertEqual(b.segments.last?.end, 432)
        for (a, c) in zip(b.segments, b.segments.dropFirst()) { XCTAssertEqual(a.end, c.start) }
    }

    func testTappingABlockRemembersWhereItWas() {
        let m = TodayModel(snapshot: TodayFixtures.snapshot(.normal))
        m.open(.sleep, from: CGRect(x: 10, y: 20, width: 100, height: 80))
        XCTAssertEqual(m.selected, .sleep)
        XCTAssertEqual(m.origin.midX, 60)
        m.close()
        XCTAssertNil(m.selected)
    }
}
