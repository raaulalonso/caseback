import XCTest

/// The pull that opens the conclusions sheet, driven with a real finger: a short pull falls back, a long one opens it, and a
/// pull down closes it again.
final class PullSheetTests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["-onboarding-reset", "YES", "-onboarding-done", "YES", "-today-state", "normal", "-AppleLanguages", "(en)"]
        app.launch()
    }

    private var sheet: XCUIElement { app.scrollViews["drawer.sheet"] }

    private func drag(from: CGFloat, to: CGFloat, hold: TimeInterval = 0.2) {
        let w = app.windows.firstMatch
        let start = w.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: from))
        let end = w.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: to))
        start.press(forDuration: hold, thenDragTo: end, withVelocity: .slow, thenHoldForDuration: 0.3)
    }

    func testShortPullFallsBackAndLongPullOpens() {
        XCTAssertTrue(app.buttons["drawer.grabber"].waitForExistence(timeout: 5))
        XCTAssertFalse(sheet.isHittable, "closed: the sheet is not interactive")

        // 14 pt is under the detent: it must fall back.
        drag(from: 0.60, to: 0.60 - 14.0 / 852.0)
        sleep(1)
        XCTAssertFalse(sheet.isHittable, "a short pull must not open the sheet")

        // 100 pt is past it: it opens.
        drag(from: 0.75, to: 0.75 - 100.0 / 852.0)
        let opened = sheet.waitForExistence(timeout: 3)
        XCTAssertTrue(opened)
        let predicate = NSPredicate(format: "isHittable == true")
        expectation(for: predicate, evaluatedWith: sheet)
        waitForExpectations(timeout: 3)
    }

    func testPullDownClosesIt() {
        app.buttons["drawer.grabber"].tap()
        let predicate = NSPredicate(format: "isHittable == true")
        expectation(for: predicate, evaluatedWith: sheet)
        waitForExpectations(timeout: 3)
        drag(from: 0.3, to: 0.3 + 400.0 / 852.0)
        expectation(for: NSPredicate(format: "isHittable == false"), evaluatedWith: sheet)
        waitForExpectations(timeout: 3)
    }

    func testSwipeBetweenPages() {
        let w = app.windows.firstMatch
        XCTAssertTrue(app.staticTexts["Now"].waitForExistence(timeout: 5))
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.9, dy: 0.35)).press(
            forDuration: 0.1, thenDragTo: w.coordinate(withNormalizedOffset: CGVector(dx: 0.1, dy: 0.35)))
        XCTAssertTrue(app.staticTexts["Last night"].waitForExistence(timeout: 3), "the title follows the page")
    }

    /// Scrolling the open sheet back up must never close it, even when the content reaches the top while the finger is still
    /// moving down.
    func testScrollingTheSheetBackUpDoesNotCloseIt() {
        app.buttons["drawer.grabber"].tap()
        expectation(for: NSPredicate(format: "isHittable == true"), evaluatedWith: sheet)
        waitForExpectations(timeout: 3)
        sheet.swipeUp()
        sleep(1)
        drag(from: 0.15, to: 0.95, hold: 0.05)
        sleep(1)
        XCTAssertTrue(sheet.isHittable, "scrolling back to the top must not close the sheet")
    }

    /// Leaving Today with the sheet open and coming back must show the sheet's content, not an empty sheet.
    func testSheetStillHasItsContentAfterChangingTab() {
        app.buttons["drawer.grabber"].tap()
        expectation(for: NSPredicate(format: "isHittable == true"), evaluatedWith: sheet)
        waitForExpectations(timeout: 3)
        app.buttons["Trends"].tap()
        sleep(1)
        app.buttons["Today"].tap()
        XCTAssertTrue(app.staticTexts["Your signals"].waitForExistence(timeout: 4))
        let visible = NSPredicate(format: "isHittable == true")
        expectation(for: visible, evaluatedWith: app.staticTexts["Your signals"])
        waitForExpectations(timeout: 3)
    }

    /// Trends: the range control changes the title, and a row picks the metric the big chart shows.
    func testTrendsRangeAndMetric() {
        app.buttons["Trends"].tap()
        XCTAssertTrue(app.staticTexts["Last 30 days"].waitForExistence(timeout: 4))
        app.buttons["Last 7 days"].tap()
        XCTAssertTrue(app.staticTexts["Last 7 days"].waitForExistence(timeout: 3))
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'HRV'")).firstMatch.tap()
        XCTAssertTrue(app.staticTexts["HRV (SDNN)"].waitForExistence(timeout: 3), "the big chart now shows HRV")
    }
}
