import XCTest

/// The screen of a metric: it opens from Today and from Trends, and goes back with the chevron or from the left edge.
final class MetricDetailTests: XCTestCase {
    private var app: XCUIApplication!

    private func launch(_ extra: [String]) {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["-onboarding-reset", "YES", "-onboarding-done", "YES", "-trends-state", "full", "-AppleLanguages", "(en)"] + extra
        app.launch()
    }

    func testTappingASectionOpensItsScreenAndBackClosesIt() {
        launch([])
        let recovery = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Recovery'")).firstMatch
        XCTAssertTrue(recovery.waitForExistence(timeout: 5))
        recovery.tap()
        XCTAssertTrue(app.buttons["detail.back"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Signals behind the score"].waitForExistence(timeout: 5))
        app.buttons["detail.back"].tap()
        XCTAssertTrue(app.buttons["detail.back"].waitForNonExistence(timeout: 5))
    }

    func testSwipeFromTheLeftEdgeGoesBack() {
        launch(["-today-open", "sleep"])
        XCTAssertTrue(app.buttons["detail.back"].waitForExistence(timeout: 5))
        let w = app.windows.firstMatch
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.01, dy: 0.5)).press(
            forDuration: 0.05, thenDragTo: w.coordinate(withNormalizedOffset: CGVector(dx: 0.6, dy: 0.5)))
        XCTAssertTrue(app.buttons["detail.back"].waitForNonExistence(timeout: 5))
    }

    func testTheRangeAndTheSleepToggleChangeTheChart() {
        launch(["-today-open", "sleep"])
        XCTAssertTrue(app.buttons["Score"].waitForExistence(timeout: 5))
        app.buttons["Hours"].tap()
        XCTAssertTrue(app.buttons["Hours"].isSelected)
        app.buttons["Last 7 days"].tap()
        XCTAssertTrue(app.buttons["Last 7 days"].isSelected)
    }

    func testASignalBehindTheScoreOpensItsOwnScreen() {
        launch(["-today-open", "readiness"])
        let hrv = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'HRV'")).firstMatch
        XCTAssertTrue(hrv.waitForExistence(timeout: 5))
        hrv.tap()
        XCTAssertTrue(app.staticTexts["Your normal"].waitForExistence(timeout: 5))
    }

    func testAMetricScreenOpensFromTheChosenRowOfTrends() {
        launch(["-tab", "trends", "-trends-metric", "hrv"])
        let row = app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'HRV'")).firstMatch
        XCTAssertTrue(row.waitForExistence(timeout: 5))
        row.tap()
        XCTAssertTrue(app.buttons["detail.back"].waitForExistence(timeout: 5))
    }

    func testASheetOpenedByLaunchArgumentDoesNotReturnWithTheTab() {
        launch(["-today-open", "steps"])
        XCTAssertTrue(app.buttons["detail.back"].waitForExistence(timeout: 5))
        app.buttons["detail.back"].tap()
        XCTAssertTrue(app.buttons["detail.back"].waitForNonExistence(timeout: 5))
        app.buttons["Trends"].tap()
        app.buttons["Today"].tap()
        XCTAssertFalse(app.buttons["detail.back"].waitForExistence(timeout: 1.5))
    }
}
