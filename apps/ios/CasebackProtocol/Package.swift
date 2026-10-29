// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "CasebackProtocol",
    // The package stays at iOS 16; the app target needs iOS 17 for SwiftData (decision D17).
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "CasebackProtocol", targets: ["CasebackProtocol"])
    ],
    targets: [
        .target(name: "CasebackProtocol"),
        .testTarget(
            name: "CasebackProtocolTests",
            dependencies: ["CasebackProtocol"],
            resources: [
                .copy("Fixtures")
            ]
        ),
    ]
)
