import SwiftUI

@main
struct PilotApp: App {
    var body: some Scene {
        WindowGroup { PilotView(factoryTools: true).preferredColorScheme(.dark) }
    }
}
