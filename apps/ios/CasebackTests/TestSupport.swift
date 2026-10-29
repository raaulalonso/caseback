import Foundation
import XCTest

@testable import Caseback

/// Polls until `condition` holds (main actor), failing the test after `seconds`.
@MainActor
func waitUntil(
    _ message: String = "condition", seconds: Double = 3, file: StaticString = #filePath, line: UInt = #line,
    _ condition: @MainActor () -> Bool
) async {
    let deadline = Date().addingTimeInterval(seconds)
    while Date() < deadline {
        if condition() { return }
        try? await Task.sleep(for: .milliseconds(5))
    }
    XCTFail("timed out waiting for \(message)", file: file, line: line)
}

func isolatedDefaults() -> UserDefaults {
    let name = "caseback.tests.\(UUID().uuidString)"
    let d = UserDefaults(suiteName: name)!
    d.removePersistentDomain(forName: name)
    return d
}
