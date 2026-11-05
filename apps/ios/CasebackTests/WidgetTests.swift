import XCTest

@testable import Caseback

final class WidgetFreshnessTests: XCTestCase {
    private var cal: Calendar {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(secondsFromGMT: 0)!
        return c
    }

    private func date(_ day: Int, _ hour: Int, _ minute: Int = 0) -> Date {
        cal.date(from: DateComponents(year: 2026, month: 10, day: day, hour: hour, minute: minute))!
    }

    func testFreshUnderSixHours() {
        XCTAssertEqual(WidgetFreshness.of(updatedAt: date(3, 9), now: date(3, 14, 59), calendar: cal), .fresh)
    }

    func testAgingTheSameDayAfterSixHours() {
        XCTAssertEqual(WidgetFreshness.of(updatedAt: date(3, 6), now: date(3, 15), calendar: cal), .aging(hours: 9))
    }

    func testStaleOnceTheDayChanges() {
        // 23:00 then 00:30 is under six hours but already yesterday's numbers.
        XCTAssertEqual(WidgetFreshness.of(updatedAt: date(2, 23), now: date(3, 0, 30), calendar: cal), .stale(days: 1))
        XCTAssertEqual(WidgetFreshness.of(updatedAt: date(1, 20), now: date(3, 8), calendar: cal), .stale(days: 2))
    }

    func testExpiredAfterThreeDaysAndNumbersHidden() {
        let f = WidgetFreshness.of(updatedAt: date(1, 8), now: date(4, 9), calendar: cal)
        XCTAssertEqual(f, .expired)
        XCTAssertFalse(f.showsNumbers)
        XCTAssertTrue(f.isDim)
        XCTAssertTrue(WidgetFreshness.stale(days: 1).showsNumbers)
        XCTAssertTrue(WidgetFreshness.stale(days: 1).isDim)
        XCTAssertFalse(WidgetFreshness.fresh.isDim)
    }

    func testChangeDatesAreFutureAndSorted() {
        let updated = date(3, 6)
        let dates = WidgetFreshness.changeDates(updatedAt: updated, after: updated, calendar: cal)
        XCTAssertEqual(dates.count, 3)
        XCTAssertEqual(dates, dates.sorted())
        XCTAssertEqual(dates[0], date(3, 12), "six hours")
        XCTAssertEqual(dates[1], date(4, 0), "midnight")
        XCTAssertGreaterThan(dates[2], date(6, 6), "three days")
        // Past moments are dropped.
        XCTAssertEqual(WidgetFreshness.changeDates(updatedAt: updated, after: date(3, 13), calendar: cal).count, 2)
        XCTAssertTrue(WidgetFreshness.changeDates(updatedAt: updated, after: date(10, 0), calendar: cal).isEmpty)
    }
}

final class WidgetSnapshotTests: XCTestCase {
    private let synced = Date(timeIntervalSince1970: 1_790_000_000)

    func testMakeFromTodayCarriesTheScores() {
        let today = TodayFixtures.snapshot(.normal)
        let w = WidgetSnapshot.make(from: today, syncedAt: synced)
        XCTAssertTrue(w.paired)
        XCTAssertEqual(w.updatedAt, synced)
        XCTAssertNotNil(w.sleepScore)
        XCTAssertNotNil(w.recoveryScore)
        XCTAssertTrue(w.hasAnyData)
    }

    func testUnpairedHasNothingToShow() {
        let w = WidgetSnapshot.make(from: TodayFixtures.snapshot(.unpaired), syncedAt: synced)
        XCTAssertFalse(w.paired)
        for k in WidgetMetricKind.allCases {
            XCTAssertEqual(w.placeholder(for: k, freshness: .fresh), .unpaired)
        }
    }

    func testCalibratingRecoveryAsksForTheDay() {
        let w = WidgetSnapshot.make(from: TodayFixtures.snapshot(.calibrating), syncedAt: synced)
        XCTAssertNil(w.recoveryScore)
        guard case .calibrating(let day)? = w.placeholder(for: .readiness, freshness: .fresh) else { return XCTFail("expected calibrating") }
        XCTAssertEqual(day, w.recoveryCalibratingDay)
        XCTAssertNil(w.placeholder(for: .sleep, freshness: .fresh), "sleep has its own data")
    }

    func testExpiredWinsOverEverything() {
        let w = WidgetSnapshot.make(from: TodayFixtures.snapshot(.normal), syncedAt: synced)
        for k in WidgetMetricKind.allCases { XCTAssertEqual(w.placeholder(for: k, freshness: .expired), .expired) }
    }

    func testCodableRoundTripThroughTheStoreEncoding() throws {
        let w = WidgetSnapshot.make(from: TodayFixtures.snapshot(.normal), syncedAt: synced)
        let e = JSONEncoder(); e.dateEncodingStrategy = .iso8601
        let d = JSONDecoder(); d.dateDecodingStrategy = .iso8601
        let back = try d.decode(WidgetSnapshot.self, from: e.encode(w))
        XCTAssertEqual(back, w)
    }

    func testAlertsAreCodableAndTextual() throws {
        var w = WidgetSnapshot(updatedAt: synced, paired: true)
        XCTAssertNil(w.alertText())
        w.alert = .batteryCritical(4)
        XCTAssertNotNil(w.alertText())
        XCTAssertTrue(w.alertText()!.contains("4"))
        w.alert = .bondLost
        let back = try JSONDecoder().decode(WidgetSnapshot.self, from: JSONEncoder().encode(w))
        XCTAssertEqual(back.alert, .bondLost)
    }

    func testStoreRoundTrip() {
        WidgetStore.clear()
        XCTAssertNil(WidgetStore.read())
        let w = WidgetSnapshot.make(from: TodayFixtures.snapshot(.normal), syncedAt: Date(timeIntervalSince1970: 1_790_000_000))
        // An unsigned simulator build has no group container; the fallback has to hold it all the same.
        if WidgetStore.write(w) { XCTAssertEqual(WidgetStore.read(), w) }
        WidgetStore.clear()
        XCTAssertNil(WidgetStore.read())
    }
}

final class WidgetLinkTests: XCTestCase {
    func testEveryMetricLinkRoundTrips() {
        for k in WidgetMetricKind.allCases {
            let link = WidgetLink.metric(k.destination)
            XCTAssertEqual(WidgetLink(url: link.url), link, "\(k)")
        }
        XCTAssertEqual(WidgetLink(url: WidgetLink.today.url), .today)
        XCTAssertEqual(WidgetLink(url: WidgetLink.setup.url), .setup)
    }

    func testForeignOrBrokenLinksAreIgnored() {
        XCTAssertNil(WidgetLink(url: URL(string: "https://example.com/metric/sleep")!))
        XCTAssertNil(WidgetLink(url: URL(string: "caseback://metric/nonsense")!))
        XCTAssertNil(WidgetLink(url: URL(string: "caseback://elsewhere")!))
    }
}

final class WidgetFigureTests: XCTestCase {
    private let w = WidgetSnapshot.make(from: TodayFixtures.snapshot(.normal), syncedAt: Date())

    func testScoresReadAsScoresAndTrendOnlyStaysPlain() {
        XCTAssertTrue(WidgetFigure.make(.sleep, w)?.scoreColor == true)
        XCTAssertTrue(WidgetMetricKind.spo2.trendOnly)
        XCTAssertTrue(WidgetMetricKind.skinTemp.trendOnly)
        XCTAssertFalse(WidgetMetricKind.hrv.trendOnly)
    }

    func testAnEmptySnapshotGivesNoFigure() {
        let empty = WidgetSnapshot(updatedAt: Date(), paired: true)
        XCTAssertFalse(empty.hasAnyData)
        for k in WidgetMetricKind.allCases { XCTAssertNil(WidgetFigure.make(k, empty), "\(k)") }
    }
}
