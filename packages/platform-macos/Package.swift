// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "FalconPlatformMacOS",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "falcon-recorder", targets: ["FalconRecorder"]),
    ],
    targets: [
        .executableTarget(
            name: "FalconRecorder",
            linkerSettings: [
                .linkedFramework("ApplicationServices"),
                .linkedFramework("AppKit"),
                .linkedFramework("Carbon"),
            ]
        ),
    ]
)
