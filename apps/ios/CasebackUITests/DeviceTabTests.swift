import XCTest

/// The Device tab: the sentence at the top, a row that opens its sheet, and the forget flow that needs a deliberate tap.
final class DeviceTabTests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = [
            "-onboarding-reset", "YES", "-onboarding-done", "YES", "-tab", "device", "-device-state", "updateAvailable",
            "-caseback-fast", "YES", "-AppleLanguages", "(en)",
        ]
        app.launch()
    }

    func testStatusAndRowsAreThere() {
        XCTAssertTrue(app.staticTexts["Connected"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["Update, Available"].exists)
        XCTAssertTrue(app.buttons["Recording, Night"].exists)
    }

    func testUpdateRunsFromItsSheet() {
        app.buttons["device.row.update"].tap()
        let start = app.buttons["Update"]
        XCTAssertTrue(start.waitForExistence(timeout: 5))
        start.tap()
        XCTAssertTrue(app.staticTexts["Updated to 0.3.0."].waitForExistence(timeout: 5))
    }

    func testTappingAModeChangesItAtOnce() {
        app.buttons["device.row.mode"].tap()
        let day = app.buttons["device.mode.day"]
        XCTAssertTrue(day.waitForExistence(timeout: 5))
        day.tap()
        app.swipeDown()
        XCTAssertTrue(app.buttons["Recording, Day"].waitForExistence(timeout: 5))
    }

    /// A sheet opened by a launch argument is opened once: leaving the tab and coming back must not bring it back.
    func testASheetDoesNotReopenWhenComingBackToTheTab() {
        app.terminate()
        app.launchArguments += ["-device-sheet", "update"]
        app.launch()
        XCTAssertTrue(app.buttons["Update"].waitForExistence(timeout: 5))
        let w = app.windows.firstMatch
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.55)).press(
            forDuration: 0.1, thenDragTo: w.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.97)))
        XCTAssertTrue(app.buttons["Update"].waitForNonExistence(timeout: 5), "the sheet closed")
        app.buttons["Trends"].tap()
        app.buttons["Device"].tap()
        XCTAssertTrue(app.buttons["device.row.update"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Update"].waitForExistence(timeout: 1.5))
    }
}
