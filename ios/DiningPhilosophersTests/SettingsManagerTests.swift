// SettingsManagerTests.swift
// Tests for SettingsManager
//
// Created by iOS Native Agent - Phase 7

import XCTest
@testable import DiningPhilosophers

final class SettingsManagerTests: XCTestCase {
    var sut: SettingsManager!
    var testDefaults: UserDefaults!

    override func setUp() {
        super.setUp()
        // Create isolated UserDefaults for testing
        testDefaults = UserDefaults(suiteName: "test.settings.\(UUID().uuidString)")!
        sut = SettingsManager(defaults: testDefaults)
    }

    override func tearDown() {
        // Clean up test defaults
        if let suiteName = testDefaults.persistentDomain(forName: "test.settings") {
            testDefaults.removePersistentDomain(forName: "test.settings")
        }
        sut = nil
        testDefaults = nil
        super.tearDown()
    }

    // MARK: - Default Values Tests

    func testDefaultValues() {
        XCTAssertFalse(sut.compactLayout, "Compact layout should default to false")
        XCTAssertTrue(sut.showTimestamps, "Show timestamps should default to true")
        XCTAssertTrue(sut.hapticFeedback, "Haptic feedback should default to true")
        XCTAssertTrue(sut.autoPlayMedia, "Auto play media should default to true")
        XCTAssertEqual(sut.textSize, .medium, "Text size should default to medium")
        XCTAssertFalse(sut.reducedMotion, "Reduced motion should default to false")
    }

    // MARK: - Persistence Tests

    func testCompactLayoutPersistence() {
        sut.compactLayout = true

        // Create new instance with same defaults
        let newManager = SettingsManager(defaults: testDefaults)

        XCTAssertTrue(newManager.compactLayout)
    }

    func testShowTimestampsPersistence() {
        sut.showTimestamps = false

        let newManager = SettingsManager(defaults: testDefaults)

        XCTAssertFalse(newManager.showTimestamps)
    }

    func testHapticFeedbackPersistence() {
        sut.hapticFeedback = false

        let newManager = SettingsManager(defaults: testDefaults)

        XCTAssertFalse(newManager.hapticFeedback)
    }

    func testAutoPlayMediaPersistence() {
        sut.autoPlayMedia = false

        let newManager = SettingsManager(defaults: testDefaults)

        XCTAssertFalse(newManager.autoPlayMedia)
    }

    func testTextSizePersistence() {
        sut.textSize = .large

        let newManager = SettingsManager(defaults: testDefaults)

        XCTAssertEqual(newManager.textSize, .large)
    }

    func testReducedMotionPersistence() {
        sut.reducedMotion = true

        let newManager = SettingsManager(defaults: testDefaults)

        XCTAssertTrue(newManager.reducedMotion)
    }

    // MARK: - Text Size Tests

    func testAllTextSizeOptions() {
        let allCases: [TextSizePreference] = [.small, .medium, .large, .extraLarge]

        for size in allCases {
            sut.textSize = size
            XCTAssertEqual(sut.textSize, size)
        }
    }

    func testTextSizeDisplayNames() {
        XCTAssertEqual(TextSizePreference.small.displayName, "Small")
        XCTAssertEqual(TextSizePreference.medium.displayName, "Medium")
        XCTAssertEqual(TextSizePreference.large.displayName, "Large")
        XCTAssertEqual(TextSizePreference.extraLarge.displayName, "Extra Large")
    }

    func testTextSizeRawValues() {
        XCTAssertEqual(TextSizePreference.small.rawValue, "small")
        XCTAssertEqual(TextSizePreference.medium.rawValue, "medium")
        XCTAssertEqual(TextSizePreference.large.rawValue, "large")
        XCTAssertEqual(TextSizePreference.extraLarge.rawValue, "extra_large")
    }

    // MARK: - Reset Tests

    func testResetToDefaults() {
        // Change all values
        sut.compactLayout = true
        sut.showTimestamps = false
        sut.hapticFeedback = false
        sut.autoPlayMedia = false
        sut.textSize = .extraLarge
        sut.reducedMotion = true

        // Reset
        sut.resetToDefaults()

        // Verify defaults
        XCTAssertFalse(sut.compactLayout)
        XCTAssertTrue(sut.showTimestamps)
        XCTAssertTrue(sut.hapticFeedback)
        XCTAssertTrue(sut.autoPlayMedia)
        XCTAssertEqual(sut.textSize, .medium)
        XCTAssertFalse(sut.reducedMotion)
    }

    func testResetPersistsToDefaults() {
        // Change all values
        sut.compactLayout = true
        sut.showTimestamps = false

        // Reset
        sut.resetToDefaults()

        // Create new instance and verify
        let newManager = SettingsManager(defaults: testDefaults)
        XCTAssertFalse(newManager.compactLayout)
        XCTAssertTrue(newManager.showTimestamps)
    }

    // MARK: - Edge Cases

    func testInvalidTextSizeRawValue() {
        // Set an invalid raw value directly in UserDefaults
        testDefaults.set("invalid_size", forKey: "settings_text_size")

        // Create new instance - should fall back to medium
        let newManager = SettingsManager(defaults: testDefaults)

        XCTAssertEqual(newManager.textSize, .medium)
    }

    func testMultipleChangesInSequence() {
        sut.compactLayout = true
        sut.compactLayout = false
        sut.compactLayout = true

        XCTAssertTrue(sut.compactLayout)

        let newManager = SettingsManager(defaults: testDefaults)
        XCTAssertTrue(newManager.compactLayout)
    }

    // MARK: - Preview Support

    func testPreviewInstanceIsolation() {
        let preview = SettingsManager.preview()

        // Modify preview instance
        preview.compactLayout = true

        // Verify shared instance is unaffected
        XCTAssertFalse(sut.compactLayout)
    }
}
