import XCTest

/// Drives the Simulator's own Home Screen, in English: testLayout, then testSmallWidgetSleep, then testWallpaper (home_screen.sh runs
/// them in that order). Each one leaves the simulator in the state the next one starts from.
final class HomeScreenTests: XCTestCase {
    private let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")

    override func setUp() { continueAfterFailure = false }

    /// Writes what SpringBoard shows to $DUMP_DIR/<name>.txt (TEST_RUNNER_DUMP_DIR on the xcodebuild line).
    private func dump(_ name: String) {
        guard let dir = ProcessInfo.processInfo.environment["DUMP_DIR"] else { return }
        try? springboard.debugDescription.write(toFile: "\(dir)/\(name).txt", atomically: true, encoding: .utf8)
    }

    // MARK: helpers

    private func jiggle() {
        XCUIDevice.shared.press(.home)
        sleep(1)
        XCUIDevice.shared.press(.home)
        sleep(2)
        if springboard.buttons["Done"].exists { return }
        springboard.windows.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.62)).press(forDuration: 1.6)
        sleep(2)
        XCTAssertTrue(springboard.buttons["Done"].waitForExistence(timeout: 5), "the Home Screen did not enter edit mode")
    }

    /// Takes out the widgets Apple puts on a fresh Home Screen.
    private func removeStockWidgets() {
        for _ in 0..<4 {
            let widget = springboard.icons.matching(NSPredicate(format: "value CONTAINS 'Widget'")).firstMatch
            guard widget.exists else { return }
            widget.buttons["DeleteButton"].tap()
            let remove = springboard.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Remove'")).firstMatch
            XCTAssertTrue(remove.waitForExistence(timeout: 3))
            remove.tap()
            sleep(2)
        }
    }

    /// Opens the widget gallery on Caseback's page and adds the widget at the given size page (0 small, 1 medium).
    private func addCaseback(page: Int) {
        springboard.buttons["Edit"].tap()
        springboard.buttons["Add Widget"].tap()
        let search = springboard.searchFields.firstMatch
        XCTAssertTrue(search.waitForExistence(timeout: 5))
        search.tap()
        search.typeText("Caseback")
        let cell = springboard.cells["Caseback"].firstMatch
        XCTAssertTrue(cell.waitForExistence(timeout: 5))
        cell.tap()
        sleep(2)
        for _ in 0..<page { springboard.windows.firstMatch.swipeLeft(); sleep(1) }
        // the button's label starts with the "+" glyph, so it is " Add Widget"
        springboard.buttons.matching(NSPredicate(format: "label CONTAINS 'Add Widget'")).firstMatch.tap()
        sleep(3)
    }

    // MARK: steps

    /// Takes out the stock widgets and adds Caseback's: two small ones, then the medium one, which lands on top.
    func testLayout() {
        jiggle()
        removeStockWidgets()
        addCaseback(page: 0)
        addCaseback(page: 0)
        addCaseback(page: 1)
        dump("10-layout")
    }

    /// The second small widget (right half of the second row) shows Sleep instead of Recovery.
    func testSmallWidgetSleep() {
        jiggle()
        springboard.windows.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.72, dy: 0.42)).tap()
        let metric = springboard.cells.buttons["Recovery"].firstMatch
        XCTAssertTrue(metric.waitForExistence(timeout: 5), "the configuration sheet did not open")
        metric.tap()
        let sleepItem = springboard.descendants(matching: .any).matching(NSPredicate(format: "label == 'Sleep'")).firstMatch
        XCTAssertTrue(sleepItem.waitForExistence(timeout: 5), "no Sleep in the metric menu")
        sleepItem.tap()
        sleep(1)
        // closes the sheet by tapping outside it
        springboard.windows.firstMatch.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.1)).tap()
        sleep(2)
    }

    /// Sets the Home Screen wallpaper to a dark steel-grey gradient. A photo does not work here: the Simulator draws photo wallpapers
    /// black, so the colour of a gradient is typed in by hand in the system's colour picker.
    func testWallpaper() {
        jiggle()
        springboard.buttons["Edit"].tap()
        springboard.buttons["Edit Wallpaper"].tap()
        sleep(3)
        let w = springboard.windows.firstMatch
        springboard.buttons["Gradient"].tap()
        sleep(3)
        springboard.buttons["Gradient"].tap()  // a second tap opens the choice of colour
        sleep(3)
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.12, dy: 0.66)).tap()  // the colour wheel: the full colour picker
        sleep(3)
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.79, dy: 0.47)).tap()  // its Sliders tab, which has the hex field
        sleep(2)
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.823, dy: 0.786)).tap()
        sleep(1)
        for _ in 0..<8 { springboard.typeText(XCUIKeyboardKey.delete.rawValue) }
        springboard.typeText("4A4F55")
        springboard.typeText("\n")
        sleep(2)
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.915, dy: 0.422)).tap()  // closes the colour picker
        sleep(2)
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.14)).tap()  // closes the choice of colour
        sleep(2)
        w.coordinate(withNormalizedOffset: CGVector(dx: 0.818, dy: 0.0375)).tap()  // Done in the wallpaper editor
        sleep(4)
        if springboard.buttons["Done"].exists { springboard.buttons["Done"].tap(); sleep(2) }
    }

    /// Takes the first page of the Home Screen at three moments after the last sync (just now, the next day, four days later): the
    /// app is launched with -widget-age-hours, which stores a snapshot of that age and asks the widgets to draw it again.
    /// Needs CAPTURE_DIR (and CAPTURE_LANG, en or es) in the environment: TEST_RUNNER_CAPTURE_DIR on the xcodebuild line.
    func testCapture() throws {
        let env = ProcessInfo.processInfo.environment
        let dir = try XCTUnwrap(env["CAPTURE_DIR"], "CAPTURE_DIR is not set")
        let lang = env["CAPTURE_LANG"] ?? "en"
        try FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        for (name, hours) in [("fresh", "0.2"), ("day", "30"), ("days", "100")] {
            let app = XCUIApplication(bundleIdentifier: "com.raaulalonso.caseback")
            app.launchArguments = ["-AppleLanguages", "(\(lang))", "-AppleLocale", lang == "es" ? "es_ES" : "en_US",
                                   "-onboarding-done", "YES", "-today-state", "normal", "-widget-age-hours", hours]
            app.launch()
            sleep(8)
            app.terminate()
            // closing an app goes back to the page of its icon; a second Home goes to the first page
            XCUIDevice.shared.press(.home)
            sleep(1)
            XCUIDevice.shared.press(.home)
            sleep(8)
            try XCUIScreen.main.screenshot().pngRepresentation.write(to: URL(fileURLWithPath: "\(dir)/widgets_home_\(name).png"))
        }
    }
}
