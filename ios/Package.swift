// swift-tools-version: 5.9
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "DiningPhilosophers",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "DiningPhilosophers",
            targets: ["DiningPhilosophers"]
        ),
    ],
    dependencies: [
        // Add dependencies here as needed
        // .package(url: "https://github.com/...", from: "1.0.0"),
    ],
    targets: [
        .target(
            name: "DiningPhilosophers",
            dependencies: [],
            path: "DiningPhilosophers"
        ),
        .testTarget(
            name: "DiningPhilosophersTests",
            dependencies: ["DiningPhilosophers"],
            path: "DiningPhilosophersTests"
        ),
    ]
)
