// SettingsManager.swift
// User preferences management with UserDefaults persistence
//
// Created by iOS Native Agent - Phase 7

import Foundation
import SwiftUI

/// Manages user preferences using UserDefaults for persistence
@Observable
final class SettingsManager {
    static let shared = SettingsManager()

    private let defaults = UserDefaults.standard

    // MARK: - Keys

    private enum Keys {
        static let themePreference = "theme_preference"
        static let notificationsEnabled = "notifications_enabled"
        static let notifyNewMessages = "notify_new_messages"
        static let notifyThinkerResponses = "notify_thinker_responses"
        static let analyticsEnabled = "analytics_enabled"
        static let compactLayout = "compact_layout"
        static let showTimestamps = "show_timestamps"
    }

    // MARK: - Theme Settings

    /// Current theme preference
    var themePreference: ThemePreference {
        get {
            let rawValue = defaults.integer(forKey: Keys.themePreference)
            return ThemePreference(rawValue: rawValue) ?? .system
        }
        set {
            defaults.set(newValue.rawValue, forKey: Keys.themePreference)
        }
    }

    /// Computed color scheme for SwiftUI
    var preferredColorScheme: ColorScheme? {
        switch themePreference {
        case .system:
            return nil // Use system default
        case .light:
            return .light
        case .dark:
            return .dark
        }
    }

    // MARK: - Notification Settings

    /// Whether push notifications are enabled
    var notificationsEnabled: Bool {
        get { defaults.bool(forKey: Keys.notificationsEnabled, defaultValue: true) }
        set { defaults.set(newValue, forKey: Keys.notificationsEnabled) }
    }

    /// Whether to show notifications for new messages
    var notifyNewMessages: Bool {
        get { defaults.bool(forKey: Keys.notifyNewMessages, defaultValue: true) }
        set { defaults.set(newValue, forKey: Keys.notifyNewMessages) }
    }

    /// Whether to show notifications for thinker responses
    var notifyThinkerResponses: Bool {
        get { defaults.bool(forKey: Keys.notifyThinkerResponses, defaultValue: true) }
        set { defaults.set(newValue, forKey: Keys.notifyThinkerResponses) }
    }

    // MARK: - Privacy Settings

    /// Whether to send anonymous usage analytics
    var analyticsEnabled: Bool {
        get { defaults.bool(forKey: Keys.analyticsEnabled, defaultValue: true) }
        set { defaults.set(newValue, forKey: Keys.analyticsEnabled) }
    }

    // MARK: - UI Preferences

    /// Whether to use compact list layout
    var compactLayout: Bool {
        get { defaults.bool(forKey: Keys.compactLayout, defaultValue: false) }
        set { defaults.set(newValue, forKey: Keys.compactLayout) }
    }

    /// Whether to show message timestamps
    var showTimestamps: Bool {
        get { defaults.bool(forKey: Keys.showTimestamps, defaultValue: true) }
        set { defaults.set(newValue, forKey: Keys.showTimestamps) }
    }

    // MARK: - Initialization

    private init() {
        // Register default values
        defaults.register(defaults: [
            Keys.themePreference: 0,
            Keys.notificationsEnabled: true,
            Keys.notifyNewMessages: true,
            Keys.notifyThinkerResponses: true,
            Keys.analyticsEnabled: true,
            Keys.compactLayout: false,
            Keys.showTimestamps: true
        ])
    }

    // MARK: - Reset

    /// Reset all settings to defaults
    func resetToDefaults() {
        themePreference = .system
        notificationsEnabled = true
        notifyNewMessages = true
        notifyThinkerResponses = true
        analyticsEnabled = true
        compactLayout = false
        showTimestamps = true
    }
}

// MARK: - UserDefaults Extension

private extension UserDefaults {
    func bool(forKey key: String, defaultValue: Bool) -> Bool {
        if object(forKey: key) == nil {
            return defaultValue
        }
        return bool(forKey: key)
    }
}

// MARK: - Theme Preference

/// User's preferred color scheme
enum ThemePreference: Int, CaseIterable, Identifiable {
    case system = 0
    case light = 1
    case dark = 2

    var id: Int { rawValue }

    var title: String {
        switch self {
        case .system:
            return "System"
        case .light:
            return "Light"
        case .dark:
            return "Dark"
        }
    }

    var icon: String {
        switch self {
        case .system:
            return "gear"
        case .light:
            return "sun.max"
        case .dark:
            return "moon"
        }
    }
}

// MARK: - Supported Languages

/// Languages supported by the app
enum SupportedLanguage: String, CaseIterable, Identifiable {
    case english = "en"
    case spanish = "es"
    case french = "fr"
    case german = "de"
    case italian = "it"
    case portuguese = "pt"
    case japanese = "ja"
    case chinese = "zh"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .english:
            return "English"
        case .spanish:
            return "Español"
        case .french:
            return "Français"
        case .german:
            return "Deutsch"
        case .italian:
            return "Italiano"
        case .portuguese:
            return "Português"
        case .japanese:
            return "日本語"
        case .chinese:
            return "中文"
        }
    }

    var flag: String {
        switch self {
        case .english:
            return "🇺🇸"
        case .spanish:
            return "🇪🇸"
        case .french:
            return "🇫🇷"
        case .german:
            return "🇩🇪"
        case .italian:
            return "🇮🇹"
        case .portuguese:
            return "🇧🇷"
        case .japanese:
            return "🇯🇵"
        case .chinese:
            return "🇨🇳"
        }
    }
}
