// SettingsManagerTests.swift
// Tests for SettingsManager
//
// Created by iOS Native Agent - Phase 7

import XCTest
@testable import DiningPhilosophers

/// Tests for SettingsManager preferences persistence
final class SettingsManagerTests: XCTestCase {

    private var settingsManager: SettingsManager!
    private let testDefaults = UserDefaults(suiteName: "com.diningphilosophers.tests")!

    override func setUp() {
        super.setUp()
        // Clear test defaults before each test
        testDefaults.removePersistentDomain(forName: "com.diningphilosophers.tests")
    }

    override func tearDown() {
        // Clean up test defaults
        testDefaults.removePersistentDomain(forName: "com.diningphilosophers.tests")
        super.tearDown()
    }

    // MARK: - Theme Preference Tests

    func testThemePreferenceValues() {
        XCTAssertEqual(ThemePreference.system.rawValue, 0)
        XCTAssertEqual(ThemePreference.light.rawValue, 1)
        XCTAssertEqual(ThemePreference.dark.rawValue, 2)
    }

    func testThemePreferenceTitles() {
        XCTAssertEqual(ThemePreference.system.title, "System")
        XCTAssertEqual(ThemePreference.light.title, "Light")
        XCTAssertEqual(ThemePreference.dark.title, "Dark")
    }

    func testThemePreferenceIcons() {
        XCTAssertEqual(ThemePreference.system.icon, "gear")
        XCTAssertEqual(ThemePreference.light.icon, "sun.max")
        XCTAssertEqual(ThemePreference.dark.icon, "moon")
    }

    func testThemePreferenceAllCases() {
        let allCases = ThemePreference.allCases
        XCTAssertEqual(allCases.count, 3)
        XCTAssertTrue(allCases.contains(.system))
        XCTAssertTrue(allCases.contains(.light))
        XCTAssertTrue(allCases.contains(.dark))
    }

    func testThemePreferenceIdentifiable() {
        XCTAssertEqual(ThemePreference.system.id, 0)
        XCTAssertEqual(ThemePreference.light.id, 1)
        XCTAssertEqual(ThemePreference.dark.id, 2)
    }

    // MARK: - Supported Language Tests

    func testSupportedLanguageRawValues() {
        XCTAssertEqual(SupportedLanguage.english.rawValue, "en")
        XCTAssertEqual(SupportedLanguage.spanish.rawValue, "es")
        XCTAssertEqual(SupportedLanguage.french.rawValue, "fr")
        XCTAssertEqual(SupportedLanguage.german.rawValue, "de")
        XCTAssertEqual(SupportedLanguage.italian.rawValue, "it")
        XCTAssertEqual(SupportedLanguage.portuguese.rawValue, "pt")
        XCTAssertEqual(SupportedLanguage.japanese.rawValue, "ja")
        XCTAssertEqual(SupportedLanguage.chinese.rawValue, "zh")
    }

    func testSupportedLanguageDisplayNames() {
        XCTAssertEqual(SupportedLanguage.english.displayName, "English")
        XCTAssertEqual(SupportedLanguage.spanish.displayName, "Espa\u{00F1}ol")
        XCTAssertEqual(SupportedLanguage.french.displayName, "Fran\u{00E7}ais")
        XCTAssertEqual(SupportedLanguage.german.displayName, "Deutsch")
        XCTAssertEqual(SupportedLanguage.italian.displayName, "Italiano")
        XCTAssertEqual(SupportedLanguage.portuguese.displayName, "Portugu\u{00EA}s")
        XCTAssertEqual(SupportedLanguage.japanese.displayName, "\u{65E5}\u{672C}\u{8A9E}")
        XCTAssertEqual(SupportedLanguage.chinese.displayName, "\u{4E2D}\u{6587}")
    }

    func testSupportedLanguageFlags() {
        XCTAssertFalse(SupportedLanguage.english.flag.isEmpty)
        XCTAssertFalse(SupportedLanguage.spanish.flag.isEmpty)
        XCTAssertFalse(SupportedLanguage.french.flag.isEmpty)
        XCTAssertFalse(SupportedLanguage.german.flag.isEmpty)
        XCTAssertFalse(SupportedLanguage.italian.flag.isEmpty)
        XCTAssertFalse(SupportedLanguage.portuguese.flag.isEmpty)
        XCTAssertFalse(SupportedLanguage.japanese.flag.isEmpty)
        XCTAssertFalse(SupportedLanguage.chinese.flag.isEmpty)
    }

    func testSupportedLanguageAllCases() {
        let allCases = SupportedLanguage.allCases
        XCTAssertEqual(allCases.count, 8)
    }

    func testSupportedLanguageIdentifiable() {
        XCTAssertEqual(SupportedLanguage.english.id, "en")
        XCTAssertEqual(SupportedLanguage.japanese.id, "ja")
    }

    func testSupportedLanguageInitFromRawValue() {
        XCTAssertEqual(SupportedLanguage(rawValue: "en"), .english)
        XCTAssertEqual(SupportedLanguage(rawValue: "ja"), .japanese)
        XCTAssertNil(SupportedLanguage(rawValue: "invalid"))
    }

    // MARK: - SettingsManager Singleton Tests

    func testSettingsManagerSharedInstance() {
        let instance1 = SettingsManager.shared
        let instance2 = SettingsManager.shared
        XCTAssertTrue(instance1 === instance2, "Shared instance should be the same object")
    }

    // MARK: - SettingsManager Default Values Tests

    func testDefaultThemePreferenceIsSystem() {
        // The shared instance should default to system theme
        // Note: This may vary based on previous test runs in the same session
        let settings = SettingsManager.shared
        settings.resetToDefaults()
        XCTAssertEqual(settings.themePreference, .system)
    }

    func testDefaultNotificationsEnabled() {
        let settings = SettingsManager.shared
        settings.resetToDefaults()
        XCTAssertTrue(settings.notificationsEnabled)
        XCTAssertTrue(settings.notifyNewMessages)
        XCTAssertTrue(settings.notifyThinkerResponses)
    }

    func testDefaultUIPreferences() {
        let settings = SettingsManager.shared
        settings.resetToDefaults()
        XCTAssertFalse(settings.compactLayout)
        XCTAssertTrue(settings.showTimestamps)
    }

    func testDefaultAnalyticsEnabled() {
        let settings = SettingsManager.shared
        settings.resetToDefaults()
        XCTAssertTrue(settings.analyticsEnabled)
    }

    // MARK: - Theme Preference Change Tests

    func testThemePreferenceChange() {
        let settings = SettingsManager.shared

        settings.themePreference = .light
        XCTAssertEqual(settings.themePreference, .light)

        settings.themePreference = .dark
        XCTAssertEqual(settings.themePreference, .dark)

        settings.themePreference = .system
        XCTAssertEqual(settings.themePreference, .system)
    }

    func testPreferredColorScheme() {
        let settings = SettingsManager.shared

        settings.themePreference = .system
        XCTAssertNil(settings.preferredColorScheme)

        settings.themePreference = .light
        XCTAssertNotNil(settings.preferredColorScheme)

        settings.themePreference = .dark
        XCTAssertNotNil(settings.preferredColorScheme)
    }

    // MARK: - Notification Settings Change Tests

    func testNotificationSettingsChange() {
        let settings = SettingsManager.shared

        settings.notificationsEnabled = false
        XCTAssertFalse(settings.notificationsEnabled)

        settings.notifyNewMessages = false
        XCTAssertFalse(settings.notifyNewMessages)

        settings.notifyThinkerResponses = false
        XCTAssertFalse(settings.notifyThinkerResponses)

        // Reset for other tests
        settings.resetToDefaults()
    }

    // MARK: - UI Preferences Change Tests

    func testUIPreferencesChange() {
        let settings = SettingsManager.shared

        settings.compactLayout = true
        XCTAssertTrue(settings.compactLayout)

        settings.showTimestamps = false
        XCTAssertFalse(settings.showTimestamps)

        // Reset for other tests
        settings.resetToDefaults()
    }

    // MARK: - Reset to Defaults Tests

    func testResetToDefaults() {
        let settings = SettingsManager.shared

        // Change all settings
        settings.themePreference = .dark
        settings.notificationsEnabled = false
        settings.notifyNewMessages = false
        settings.notifyThinkerResponses = false
        settings.analyticsEnabled = false
        settings.compactLayout = true
        settings.showTimestamps = false

        // Reset to defaults
        settings.resetToDefaults()

        // Verify all are back to defaults
        XCTAssertEqual(settings.themePreference, .system)
        XCTAssertTrue(settings.notificationsEnabled)
        XCTAssertTrue(settings.notifyNewMessages)
        XCTAssertTrue(settings.notifyThinkerResponses)
        XCTAssertTrue(settings.analyticsEnabled)
        XCTAssertFalse(settings.compactLayout)
        XCTAssertTrue(settings.showTimestamps)
    }

    // MARK: - Persistence Tests

    func testSettingsPersistence() {
        let settings = SettingsManager.shared

        // Set a value
        let uniqueTheme: ThemePreference = .dark
        settings.themePreference = uniqueTheme

        // The setting should persist in UserDefaults
        let rawValue = UserDefaults.standard.integer(forKey: "theme_preference")
        XCTAssertEqual(rawValue, uniqueTheme.rawValue)

        // Reset for other tests
        settings.resetToDefaults()
    }
}
