// ThemeManagerTests.swift
// Tests for ThemeManager preferences persistence
//
// Created by iOS Native Agent - Phase 7

import XCTest
@testable import DiningPhilosophers

final class ThemeManagerTests: XCTestCase {

    var themeManager: ThemeManager!

    override func setUp() {
        super.setUp()
        // Clear UserDefaults before each test
        UserDefaults.standard.removeObject(forKey: "app_theme")
        UserDefaults.standard.removeObject(forKey: "app_language")
        UserDefaults.standard.removeObject(forKey: "notifications_enabled")
        UserDefaults.standard.removeObject(forKey: "show_typing_indicators")
        UserDefaults.standard.removeObject(forKey: "auto_scroll_messages")

        themeManager = ThemeManager()
    }

    override func tearDown() {
        themeManager = nil
        super.tearDown()
    }

    // MARK: - Theme Tests

    func testDefaultThemeIsSystem() {
        XCTAssertEqual(themeManager.theme, .system)
    }

    func testThemePersistence() {
        themeManager.theme = .dark
        XCTAssertEqual(themeManager.theme, .dark)

        // Create new instance to verify persistence
        let newManager = ThemeManager()
        XCTAssertEqual(newManager.theme, .dark)
    }

    func testLightThemeColorScheme() {
        let light = AppTheme.light
        XCTAssertNotNil(light.colorScheme)
        XCTAssertEqual(light.colorScheme, .light)
    }

    func testDarkThemeColorScheme() {
        let dark = AppTheme.dark
        XCTAssertNotNil(dark.colorScheme)
        XCTAssertEqual(dark.colorScheme, .dark)
    }

    func testSystemThemeColorSchemeIsNil() {
        let system = AppTheme.system
        XCTAssertNil(system.colorScheme)
    }

    func testAllThemesHaveDisplayNames() {
        for theme in AppTheme.allCases {
            XCTAssertFalse(theme.displayName.isEmpty)
        }
    }

    func testAllThemesHaveSystemImages() {
        for theme in AppTheme.allCases {
            XCTAssertFalse(theme.systemImage.isEmpty)
        }
    }

    // MARK: - Language Tests

    func testDefaultLanguageIsSystem() {
        XCTAssertEqual(themeManager.language, .system)
    }

    func testLanguagePersistence() {
        themeManager.language = .spanish
        XCTAssertEqual(themeManager.language, .spanish)

        // Create new instance to verify persistence
        let newManager = ThemeManager()
        XCTAssertEqual(newManager.language, .spanish)
    }

    func testAllLanguagesHaveDisplayNames() {
        for language in AppLanguage.allCases {
            XCTAssertFalse(language.displayName.isEmpty)
        }
    }

    func testLanguageIdentifiers() {
        XCTAssertEqual(AppLanguage.english.rawValue, "en")
        XCTAssertEqual(AppLanguage.spanish.rawValue, "es")
        XCTAssertEqual(AppLanguage.french.rawValue, "fr")
        XCTAssertEqual(AppLanguage.german.rawValue, "de")
        XCTAssertEqual(AppLanguage.japanese.rawValue, "ja")
        XCTAssertEqual(AppLanguage.chinese.rawValue, "zh")
    }

    // MARK: - Chat Preferences Tests

    func testDefaultShowTypingIndicatorsIsTrue() {
        XCTAssertTrue(themeManager.showTypingIndicators)
    }

    func testDefaultAutoScrollIsTrue() {
        XCTAssertTrue(themeManager.autoScrollToNewMessages)
    }

    func testTypingIndicatorsPersistence() {
        themeManager.showTypingIndicators = false
        XCTAssertFalse(themeManager.showTypingIndicators)

        let newManager = ThemeManager()
        XCTAssertFalse(newManager.showTypingIndicators)
    }

    func testAutoScrollPersistence() {
        themeManager.autoScrollToNewMessages = false
        XCTAssertFalse(themeManager.autoScrollToNewMessages)

        let newManager = ThemeManager()
        XCTAssertFalse(newManager.autoScrollToNewMessages)
    }

    // MARK: - Reset Tests

    func testResetToDefaults() {
        // Set custom values
        themeManager.theme = .dark
        themeManager.language = .japanese
        themeManager.showTypingIndicators = false
        themeManager.autoScrollToNewMessages = false

        // Reset
        themeManager.resetToDefaults()

        // Verify defaults
        XCTAssertEqual(themeManager.theme, .system)
        XCTAssertEqual(themeManager.language, .system)
        XCTAssertTrue(themeManager.showTypingIndicators)
        XCTAssertTrue(themeManager.autoScrollToNewMessages)
    }

    // MARK: - Preferred Color Scheme Tests

    func testPreferredColorSchemeFollowsTheme() {
        themeManager.theme = .system
        XCTAssertNil(themeManager.preferredColorScheme)

        themeManager.theme = .light
        XCTAssertEqual(themeManager.preferredColorScheme, .light)

        themeManager.theme = .dark
        XCTAssertEqual(themeManager.preferredColorScheme, .dark)
    }
}
