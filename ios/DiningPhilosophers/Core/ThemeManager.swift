// ThemeManager.swift
// Manages app-wide theme (light/dark/system) and language preferences
//
// Created by iOS Native Agent - Phase 7

import Foundation
import SwiftUI

/// App color scheme preference
enum AppTheme: String, CaseIterable, Identifiable {
    case system = "System"
    case light = "Light"
    case dark = "Dark"

    var id: String { rawValue }

    var displayName: String { rawValue }

    var systemImage: String {
        switch self {
        case .system: return "iphone"
        case .light: return "sun.max"
        case .dark: return "moon"
        }
    }

    /// Convert to SwiftUI ColorScheme (nil means use system)
    var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

/// Supported languages
enum AppLanguage: String, CaseIterable, Identifiable {
    case system = "system"
    case english = "en"
    case spanish = "es"
    case french = "fr"
    case german = "de"
    case japanese = "ja"
    case chinese = "zh"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .system: return "System Default"
        case .english: return "English"
        case .spanish: return "Español"
        case .french: return "Français"
        case .german: return "Deutsch"
        case .japanese: return "日本語"
        case .chinese: return "中文"
        }
    }

    var systemImage: String {
        return "globe"
    }
}

/// Manages app theme, language, and other UI preferences
@Observable
final class ThemeManager {
    /// Current theme selection
    var theme: AppTheme {
        didSet {
            UserDefaults.standard.set(theme.rawValue, forKey: "app_theme")
        }
    }

    /// Current language selection
    var language: AppLanguage {
        didSet {
            UserDefaults.standard.set(language.rawValue, forKey: "app_language")
            updateLanguage()
        }
    }

    /// Whether notifications are enabled (UI state - actual permission is system-managed)
    var notificationsEnabled: Bool {
        didSet {
            UserDefaults.standard.set(notificationsEnabled, forKey: "notifications_enabled")
        }
    }

    /// Whether to show typing indicators in chat
    var showTypingIndicators: Bool {
        didSet {
            UserDefaults.standard.set(showTypingIndicators, forKey: "show_typing_indicators")
        }
    }

    /// Whether to auto-scroll to new messages
    var autoScrollToNewMessages: Bool {
        didSet {
            UserDefaults.standard.set(autoScrollToNewMessages, forKey: "auto_scroll_messages")
        }
    }

    init() {
        // Load saved preferences
        let savedTheme = UserDefaults.standard.string(forKey: "app_theme") ?? AppTheme.system.rawValue
        self.theme = AppTheme(rawValue: savedTheme) ?? .system

        let savedLanguage = UserDefaults.standard.string(forKey: "app_language") ?? AppLanguage.system.rawValue
        self.language = AppLanguage(rawValue: savedLanguage) ?? .system

        self.notificationsEnabled = UserDefaults.standard.bool(forKey: "notifications_enabled")
        self.showTypingIndicators = UserDefaults.standard.object(forKey: "show_typing_indicators") as? Bool ?? true
        self.autoScrollToNewMessages = UserDefaults.standard.object(forKey: "auto_scroll_messages") as? Bool ?? true
    }

    /// Apply the selected color scheme to the app
    var preferredColorScheme: ColorScheme? {
        theme.colorScheme
    }

    /// Update the app's language (note: requires app restart for full effect)
    private func updateLanguage() {
        if language != .system {
            UserDefaults.standard.set([language.rawValue], forKey: "AppleLanguages")
        } else {
            UserDefaults.standard.removeObject(forKey: "AppleLanguages")
        }
    }

    /// Reset all preferences to defaults
    func resetToDefaults() {
        theme = .system
        language = .system
        notificationsEnabled = true
        showTypingIndicators = true
        autoScrollToNewMessages = true
    }
}
