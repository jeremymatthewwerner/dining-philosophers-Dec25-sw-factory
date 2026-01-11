// SettingsManager.swift
// User preferences persistence and management
//
// Created by iOS Native Agent - Phase 7

import Foundation
import SwiftUI

/// Keys for UserDefaults storage
private enum SettingsKey {
    static let compactLayout = "settings_compact_layout"
    static let showTimestamps = "settings_show_timestamps"
    static let hapticFeedback = "settings_haptic_feedback"
    static let autoPlayMedia = "settings_auto_play_media"
    static let textSize = "settings_text_size"
    static let reducedMotion = "settings_reduced_motion"
}

/// Text size preference
enum TextSizePreference: String, CaseIterable, Identifiable {
    case small = "small"
    case medium = "medium"
    case large = "large"
    case extraLarge = "extra_large"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .small: return "Small"
        case .medium: return "Medium"
        case .large: return "Large"
        case .extraLarge: return "Extra Large"
        }
    }

    var dynamicTypeSize: DynamicTypeSize {
        switch self {
        case .small: return .small
        case .medium: return .medium
        case .large: return .large
        case .extraLarge: return .xLarge
        }
    }
}

/// Manages user preferences with UserDefaults persistence
@Observable
final class SettingsManager: @unchecked Sendable {
    static let shared = SettingsManager()

    private let defaults: UserDefaults

    // MARK: - UI Preferences

    /// Use compact layout in message lists
    var compactLayout: Bool {
        didSet {
            defaults.set(compactLayout, forKey: SettingsKey.compactLayout)
        }
    }

    /// Show timestamps on messages
    var showTimestamps: Bool {
        didSet {
            defaults.set(showTimestamps, forKey: SettingsKey.showTimestamps)
        }
    }

    /// Enable haptic feedback
    var hapticFeedback: Bool {
        didSet {
            defaults.set(hapticFeedback, forKey: SettingsKey.hapticFeedback)
        }
    }

    /// Auto-play media in conversations
    var autoPlayMedia: Bool {
        didSet {
            defaults.set(autoPlayMedia, forKey: SettingsKey.autoPlayMedia)
        }
    }

    /// Text size preference
    var textSize: TextSizePreference {
        didSet {
            defaults.set(textSize.rawValue, forKey: SettingsKey.textSize)
        }
    }

    /// Reduce motion animations
    var reducedMotion: Bool {
        didSet {
            defaults.set(reducedMotion, forKey: SettingsKey.reducedMotion)
        }
    }

    // MARK: - Initialization

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults

        // Load saved preferences or use defaults
        self.compactLayout = defaults.object(forKey: SettingsKey.compactLayout) as? Bool ?? false
        self.showTimestamps = defaults.object(forKey: SettingsKey.showTimestamps) as? Bool ?? true
        self.hapticFeedback = defaults.object(forKey: SettingsKey.hapticFeedback) as? Bool ?? true
        self.autoPlayMedia = defaults.object(forKey: SettingsKey.autoPlayMedia) as? Bool ?? true
        self.reducedMotion = defaults.object(forKey: SettingsKey.reducedMotion) as? Bool ?? false

        let savedTextSize = defaults.string(forKey: SettingsKey.textSize) ?? TextSizePreference.medium.rawValue
        self.textSize = TextSizePreference(rawValue: savedTextSize) ?? .medium
    }

    // MARK: - Reset

    /// Reset all settings to defaults
    func resetToDefaults() {
        compactLayout = false
        showTimestamps = true
        hapticFeedback = true
        autoPlayMedia = true
        textSize = .medium
        reducedMotion = false
    }

    // MARK: - Haptic Feedback Helpers

    /// Trigger selection feedback if enabled
    func selectionFeedback() {
        guard hapticFeedback else { return }
        let generator = UISelectionFeedbackGenerator()
        generator.selectionChanged()
    }

    /// Trigger impact feedback if enabled
    func impactFeedback(style: UIImpactFeedbackGenerator.FeedbackStyle = .medium) {
        guard hapticFeedback else { return }
        let generator = UIImpactFeedbackGenerator(style: style)
        generator.impactOccurred()
    }

    /// Trigger notification feedback if enabled
    func notificationFeedback(type: UINotificationFeedbackGenerator.FeedbackType) {
        guard hapticFeedback else { return }
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(type)
    }
}

// MARK: - Preview Support

extension SettingsManager {
    /// Create a SettingsManager for previews with isolated storage
    static func preview() -> SettingsManager {
        let defaults = UserDefaults(suiteName: "preview") ?? .standard
        // Clear preview defaults
        defaults.removePersistentDomain(forName: "preview")
        return SettingsManager(defaults: defaults)
    }
}
