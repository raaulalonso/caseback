import XCTest

final class PilotScreenTests: XCTestCase {
    func testPhysicalBenchDoesNotPresentSampleReadingsWithoutDisc() {
        let app = XCUIApplication()
        app.launchArguments = ["-bench-radio"]
        app.launch()
        XCTAssertTrue(app.navigationBars["Caseback"].waitForExistence(timeout: 12))
        XCTAssertTrue(app.buttons["Buscar discos"].exists)
        XCTAssertFalse(app.buttons["Preparar CSV"].exists)
        XCTAssertFalse(app.staticTexts["Terminal BAT"].exists)
        XCTAssertFalse(app.buttons["Estimar pulso ahora"].exists)
        XCTAssertFalse(app.staticTexts["pilot.restPulse"].exists)
    }
}
