import XCTest

@testable import Caseback

final class TrendMathTests: XCTestCase {
    func testQuantilesInterpolate() {
        XCTAssertEqual(TrendMath.quantile([4, 1, 3, 2], 0.5), 2.5)
        XCTAssertEqual(TrendMath.quantile([1, 2, 3, 4, 5], 0.25), 2)
        XCTAssertEqual(TrendMath.quantile([5], 0.75), 5)
        XCTAssertNil(TrendMath.quantile([], 0.5))
    }

    func testWindowIsTheLastDaysAndTheNormalIsAlwaysThirty() {
        let values: [Double?] = (0..<90).map { Double($0) }
        let s = TrendSeries(values: values)
        XCTAssertEqual(TrendMath.reading(s, range: .week).window.count, 7)
        XCTAssertEqual(TrendMath.reading(s, range: .quarter).window.count, 90)
        // The median is that of the last 30 days whatever the range: 60...89.
        for r in TrendRange.allCases { XCTAssertEqual(TrendMath.reading(s, range: r).median, 74.5, "\(r)") }
        let m = TrendMath.reading(s, range: .week)
        XCTAssertEqual(m.latest, 89)
        XCTAssertEqual(m.delta, 89 - 74.5)
        XCTAssertEqual(m.usual, 67.25...81.75)
    }

    func testNoNormalBeforeSevenValues() {
        let s = TrendSeries(values: [60, 61, 59, 62, 60, 61])
        let r = TrendMath.reading(s, range: .month)
        XCTAssertNil(r.median); XCTAssertNil(r.usual); XCTAssertNil(r.delta)
        XCTAssertEqual(r.latest, 61, "there is still a latest value")
        XCTAssertNotNil(TrendMath.reading(TrendSeries(values: s.values + [60]), range: .month).median)
    }

    func testGapsAreSkippedNotFilled() {
        let s = TrendSeries(values: [60, nil, 62, nil, nil, 58, 59, 61, 60])
        let r = TrendMath.reading(s, range: .week)
        XCTAssertEqual(r.window.count, 7)
        XCTAssertEqual(r.low?.value, 58)
        XCTAssertEqual(r.high?.value, 62)
        XCTAssertEqual(r.window[2], nil)
    }

    func testADayThatIsNotOverIsNeitherInTheNormalNorCompared() {
        var s = TrendSeries(values: Array(repeating: 8000, count: 29).map { Double?($0) } + [4210])
        s.lastIsPartial = true
        let r = TrendMath.reading(s, range: .week)
        XCTAssertEqual(r.median, 8000)
        XCTAssertEqual(r.latest, 4210)
        XCTAssertNil(r.delta, "4,210 steps so far is not 3,790 fewer than usual")
        XCTAssertEqual(r.low?.value, 8000, "today so far is not the lowest day")
    }

    func testDatesCountBackFromTheLastDay() {
        let end = Calendar.current.date(from: DateComponents(year: 2026, month: 10, day: 2))!
        XCTAssertEqual(TrendMath.date(index: 6, count: 7, end: end), end)
        XCTAssertEqual(Calendar.current.component(.day, from: TrendMath.date(index: 0, count: 7, end: end)), 26)
    }

    func testMinimumSpanKeepsSmallNoiseSmall() {
        XCTAssertEqual(TrendMetric.restingHR.padding(for: [57, 60]).count, 2)
        XCTAssertEqual(TrendMetric.restingHR.padding(for: [57, 60]).max()!, 58.5 + 4, accuracy: 0.001)
        XCTAssertTrue(TrendMetric.restingHR.padding(for: [50, 70]).isEmpty, "a wide series needs no help")
        XCTAssertTrue(TrendMetric.sleep.padding(for: [400, 410]).isEmpty, "bars start at zero")
    }
}

final class TrendFormatTests: XCTestCase {
    func testValuesAndChangesUseRealMinusSigns() {
        XCTAssertEqual(TrendFormat.parts(58.4, .restingHR).value, "58")
        XCTAssertEqual(TrendFormat.parts(432, .sleep).value, "7 h 12")
        XCTAssertEqual(TrendFormat.parts(-0.3, .skinTemp).value, "−0.3")
        XCTAssertEqual(TrendFormat.parts(0.2, .skinTemp).unit, "°C")
        XCTAssertEqual(TrendFormat.delta(-4, .restingHR), "−4")
        XCTAssertEqual(TrendFormat.delta(25, .sleep), "+25 min")
        XCTAssertEqual(TrendFormat.delta(0.2, .skinTemp), "+0.2")
    }

    func testOnlyTotalsAreBarsAndOnlyUncertainMetricsAreDashed() {
        XCTAssertEqual(TrendMetric.allCases.filter(\.isBars), [.steps, .sleep])
        XCTAssertEqual(TrendMetric.allCases.filter(\.trendOnly), [.skinTemp, .spo2])
    }
}

@MainActor
final class TrendsModelTests: XCTestCase {
    func testEveryScenarioHasEverySeries() {
        for scenario in TrendsScenario.allCases {
            let s = TrendsFixtures.snapshot(scenario)
            for m in TrendMetric.allCases { XCTAssertNotNil(s.series[m], "\(scenario) \(m)") }
        }
    }

    func testFixturesAgreeWithToday() {
        let t = TrendsFixtures.snapshot(.normal)
        XCTAssertEqual(t.series[.restingHR]?.values.last ?? nil, 58)
        XCTAssertEqual(t.series[.hrv]?.values.last ?? nil, 41)
        XCTAssertEqual(t.series[.sleep]?.values.last ?? nil, 432)
        XCTAssertEqual(t.series[.steps]?.values.last ?? nil, 4210)
        XCTAssertEqual(t.series[.skinTemp]?.calibratingNights, 3, "Today says skin temperature is on night 3 of 5")
    }

    func testFixturesAreRepeatable() {
        let day = Calendar.current.startOfDay(for: .now)
        XCTAssertEqual(TrendsFixtures.snapshot(.full, today: day), TrendsFixtures.snapshot(.full, today: day))
    }

    func testTooFewNightsMeansNoTrends() {
        XCTAssertFalse(TrendsModel(snapshot: TrendsFixtures.snapshot(.empty)).hasTrends)
        XCTAssertTrue(TrendsModel(snapshot: TrendsFixtures.snapshot(.young)).hasTrends)
        XCTAssertNil(TrendsModel(snapshot: TrendsFixtures.snapshot(.young)).reading(.restingHR).median, "five nights: no usual range yet")
        XCTAssertNotNil(TrendsModel(snapshot: TrendsFixtures.snapshot(.normal)).reading(.restingHR).median)
    }

    func testRangeChangesTheWindowOnly() {
        let m = TrendsModel(snapshot: TrendsFixtures.snapshot(.full))
        let month = m.reading(.hrv)
        m.range = .week
        XCTAssertEqual(m.reading(.hrv).window.count, 7)
        XCTAssertEqual(m.reading(.hrv).median, month.median, "your normal does not depend on the range")
    }
}

final class ScoreTests: XCTestCase {
    func testZonesFollowTheThresholds() {
        XCTAssertEqual(ScoreZone.of(67, .recovery), .high)
        XCTAssertEqual(ScoreZone.of(66, .recovery), .moderate)
        XCTAssertEqual(ScoreZone.of(33, .recovery), .moderate)
        XCTAssertEqual(ScoreZone.of(32, .recovery), .low)
        XCTAssertEqual(ScoreZone.of(80, .sleep), .high)
        XCTAssertEqual(ScoreZone.of(79, .sleep), .moderate)
        XCTAssertEqual(ScoreZone.of(59, .sleep), .low)
    }

    func testTheSleepScoreMatchesThePythonOne() {
        // The fixture night of 432 minutes: `sleep_score` in sleep.py gives 94.4 for the same stages.
        let score = SleepScore.make(segments: TodayFixtures.sleep(minutes: 432).segments)
        XCTAssertEqual(score, 94)
    }

    func testSleepScoreRewardsLongerNightsAndPunishesWakefulness() {
        let long = SleepScore.make(segments: [SleepSegment(start: 0, end: 480, stage: .light)])!
        let short = SleepScore.make(segments: [SleepSegment(start: 0, end: 240, stage: .light)])!
        XCTAssertGreaterThan(long, short)
        let awake = SleepScore.make(segments: [SleepSegment(start: 0, end: 240, stage: .light), SleepSegment(start: 240, end: 480, stage: .wake)])!
        XCTAssertLessThan(awake, long)
        XCTAssertNil(SleepScore.make(segments: []))
    }
}

final class TrendConclusionTests: XCTestCase {
    private func reading(_ values: [Double?]) -> (TrendSeries, TrendReading) {
        let s = TrendSeries(values: values)
        return (s, TrendMath.reading(s, range: .quarter))
    }

    func testScoresCountDaysInEachZone() {
        let c = TrendConclusion.zoneCounts([80, 70, 67, 50, 33, 20, nil], .recovery)
        XCTAssertEqual(c.high, 3); XCTAssertEqual(c.moderate, 2); XCTAssertEqual(c.low, 1)
        let (s, r) = reading([80, 70, 40, nil])
        XCTAssertEqual(TrendConclusion.text(.readiness, series: s, reading: r), L("trends.concl.zones", 2, 3, 1, 0))
    }

    func testSignalsSayWhetherTheyEndedHigherLowerOrTheSame() {
        let down = TrendConclusion.change([62, 62, 61, 60, 59, 58].map { Double?($0) })
        XCTAssertEqual(down, -3.5, "median of the first two against the last two")
        let (s, r) = reading([64, 63, 62, 61, 60, 59, 58, 57, 56].map { Double?($0) })
        XCTAssertEqual(TrendConclusion.text(.restingHR, series: s, reading: r), L("trends.concl.down", "−6"))
        let (s2, r2) = reading([60, 60.5, 60, 60.4, 60.2, 60.1].map { Double?($0) })
        XCTAssertEqual(TrendConclusion.text(.restingHR, series: s2, reading: r2), L("trends.concl.stable"))
    }

    func testTooFewValuesSayNothing() {
        let (s, r) = reading([60, 61, 62])
        XCTAssertNil(TrendConclusion.text(.restingHR, series: s, reading: r))
    }

    func testTheListLeadsWithTheScoresAndKeepsEveryMetric() {
        XCTAssertEqual(TrendMetric.summary, [.readiness, .sleepScore, .steps])
        XCTAssertEqual(Set(TrendMetric.summary + TrendMetric.signals), Set(TrendMetric.allCases))
        XCTAssertEqual(TrendMetric.allCases.count, TrendMetric.summary.count + TrendMetric.signals.count)
        XCTAssertEqual(TrendMetric.allCases.filter { $0.scoreKind != nil }, [.readiness, .sleepScore])
    }

    func testScoreChartsAlwaysShowTheirZones() {
        let pad = TrendMetric.sleepScore.padding(for: [75, 90])
        XCTAssertEqual(pad.max(), 100)
        XCTAssertLessThanOrEqual(pad.min()!, 48, "the lowest limit (60) stays in view")
    }
}

