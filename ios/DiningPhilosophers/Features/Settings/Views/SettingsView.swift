// SettingsView.swift
// User settings and preferences
//
// Created by iOS Native Agent
// Updated by iOS Native Agent - Phase 7

import SwiftUI
import UserNotifications

/// Settings view
struct SettingsView: View {
    @Environment(AuthManager.self) private var authManager
    @Environment(ThemeManager.self) private var themeManager
    @State private var isShowingLogoutConfirmation = false
    @State private var isShowingResetConfirmation = false
    @State private var isShowingEditProfile = false
    @State private var isShowingChangePassword = false
    @State private var isShowingLanguageSelection = false

    var body: some View {
        NavigationStack {
            List {
                // User info section
                if let user = authManager.currentUser {
                    accountSection(user: user)
                    securitySection
                    usageSection(user: user)
                }

                // Appearance section
                appearanceSection

                // Preferences section
                preferencesSection

                // Chat section
                chatSection

                // About section
                aboutSection

                // Logout section
                logoutSection
            }
            .navigationTitle("Settings")
            .confirmationDialog(
                "Sign Out",
                isPresented: $isShowingLogoutConfirmation,
                titleVisibility: .visible
            ) {
                Button("Sign Out", role: .destructive) {
                    Task {
                        await authManager.logout()
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Are you sure you want to sign out?")
            }
            .confirmationDialog(
                "Reset Preferences",
                isPresented: $isShowingResetConfirmation,
                titleVisibility: .visible
            ) {
                Button("Reset to Defaults", role: .destructive) {
                    themeManager.resetToDefaults()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will reset all preferences to their default values.")
            }
            .sheet(isPresented: $isShowingEditProfile) {
                NavigationStack {
                    EditProfileView()
                }
            }
            .sheet(isPresented: $isShowingChangePassword) {
                NavigationStack {
                    ChangePasswordView()
                }
            }
            .sheet(isPresented: $isShowingLanguageSelection) {
                NavigationStack {
                    LanguageSelectionView()
                }
            }
        }
    }

    // MARK: - Sections

    @ViewBuilder
    private func accountSection(user: User) -> some View {
        Section("Account") {
            Button {
                isShowingEditProfile = true
            } label: {
                HStack(spacing: 12) {
                    Image(systemName: "person.circle.fill")
                        .font(.system(size: 44))
                        .foregroundStyle(.secondary)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(user.displayName ?? user.username)
                            .font(.headline)
                            .foregroundStyle(.primary)
                        Text("@\(user.username)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            }
            .padding(.vertical, 8)
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Account: \(user.displayName ?? user.username)")
            .accessibilityHint("Double tap to edit profile")

            LabeledContent("Member Since") {
                Text(user.createdAt, style: .date)
            }
            .accessibilityLabel("Member since \(user.createdAt.formatted(date: .long, time: .omitted))")
        }
    }

    private var securitySection: some View {
        Section("Security") {
            Button {
                isShowingChangePassword = true
            } label: {
                Label("Change Password", systemImage: "lock")
            }
            .accessibilityHint("Double tap to change your password")
        }
    }

    @ViewBuilder
    private func usageSection(user: User) -> some View {
        Section("Usage") {
            LabeledContent("Total Spend") {
                Text(user.totalSpend, format: .currency(code: "USD"))
            }
            .accessibilityLabel("Total spend: \(user.totalSpend.formatted(.currency(code: "USD")))")

            LabeledContent("Spend Limit") {
                Text(user.spendLimit, format: .currency(code: "USD"))
            }
            .accessibilityLabel("Spend limit: \(user.spendLimit.formatted(.currency(code: "USD")))")
        }
    }

    private var appearanceSection: some View {
        Section("Appearance") {
            @Bindable var theme = themeManager

            Picker(selection: $theme.theme) {
                ForEach(AppTheme.allCases) { option in
                    Label(option.displayName, systemImage: option.systemImage)
                        .tag(option)
                }
            } label: {
                Label("Theme", systemImage: "paintbrush")
            }
            .accessibilityLabel("Theme: \(themeManager.theme.displayName)")
            .accessibilityHint("Double tap to change theme")
        }
    }

    private var preferencesSection: some View {
        Section("Preferences") {
            Button {
                isShowingLanguageSelection = true
            } label: {
                HStack {
                    Label("Language", systemImage: "globe")
                    Spacer()
                    Text(themeManager.language.displayName)
                        .foregroundStyle(.secondary)
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            }
            .accessibilityLabel("Language: \(themeManager.language.displayName)")
            .accessibilityHint("Double tap to change language")

            NavigationLink {
                NotificationSettingsView()
            } label: {
                Label("Notifications", systemImage: "bell")
            }
            .accessibilityHint("Double tap to configure notifications")
        }
    }

    private var chatSection: some View {
        Section("Chat") {
            @Bindable var theme = themeManager

            Toggle(isOn: $theme.showTypingIndicators) {
                Label("Typing Indicators", systemImage: "ellipsis.bubble")
            }
            .accessibilityLabel("Show typing indicators: \(themeManager.showTypingIndicators ? "On" : "Off")")

            Toggle(isOn: $theme.autoScrollToNewMessages) {
                Label("Auto-scroll to New Messages", systemImage: "arrow.down.to.line")
            }
            .accessibilityLabel("Auto-scroll to new messages: \(themeManager.autoScrollToNewMessages ? "On" : "Off")")
        }
    }

    private var aboutSection: some View {
        Section("About") {
            LabeledContent("Version") {
                Text(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
            }
            .accessibilityLabel("Version \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")")

            LabeledContent("Build") {
                Text(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1")
            }
            .accessibilityLabel("Build \(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1")")

            Link(destination: URL(string: "https://diningphilosophers.ai")!) {
                Label("Website", systemImage: "safari")
            }
            .accessibilityHint("Opens in Safari")

            Link(destination: URL(string: "https://diningphilosophers.ai/privacy")!) {
                Label("Privacy Policy", systemImage: "hand.raised")
            }
            .accessibilityHint("Opens in Safari")

            Link(destination: URL(string: "https://diningphilosophers.ai/terms")!) {
                Label("Terms of Service", systemImage: "doc.text")
            }
            .accessibilityHint("Opens in Safari")

            Button {
                isShowingResetConfirmation = true
            } label: {
                Label("Reset Preferences", systemImage: "arrow.counterclockwise")
            }
            .accessibilityHint("Double tap to reset all preferences to defaults")
        }
    }

    private var logoutSection: some View {
        Section {
            Button(role: .destructive) {
                isShowingLogoutConfirmation = true
            } label: {
                Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
            }
            .accessibilityHint("Double tap to sign out")
        }
    }
}

// MARK: - Notification Settings View

/// View for configuring notification preferences
struct NotificationSettingsView: View {
    @Environment(ThemeManager.self) private var themeManager
    @State private var systemNotificationsEnabled = false
    @State private var hasCheckedPermission = false

    var body: some View {
        List {
            Section {
                @Bindable var theme = themeManager

                Toggle(isOn: $theme.notificationsEnabled) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Push Notifications")
                        Text("Receive notifications when thinkers respond")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
                .accessibilityLabel("Push notifications: \(themeManager.notificationsEnabled ? "On" : "Off")")
            } footer: {
                if !systemNotificationsEnabled && hasCheckedPermission {
                    Text("Notifications are disabled in iOS Settings. Tap 'Open Settings' below to enable them.")
                        .foregroundStyle(.orange)
                }
            }

            if !systemNotificationsEnabled && hasCheckedPermission {
                Section {
                    Button {
                        openSystemSettings()
                    } label: {
                        Label("Open Settings", systemImage: "gear")
                    }
                    .accessibilityHint("Opens iOS Settings to enable notifications")
                }
            }

            Section("Notification Types") {
                NotificationTypeRow(
                    title: "New Messages",
                    description: "When a thinker sends a message",
                    systemImage: "bubble.left.fill",
                    isEnabled: true
                )

                NotificationTypeRow(
                    title: "Conversation Activity",
                    description: "When thinkers are discussing",
                    systemImage: "person.3.fill",
                    isEnabled: true
                )

                NotificationTypeRow(
                    title: "Weekly Digest",
                    description: "Summary of your conversations",
                    systemImage: "calendar",
                    isEnabled: false
                )
            }
        }
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await checkNotificationPermission()
        }
    }

    private func checkNotificationPermission() async {
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        await MainActor.run {
            systemNotificationsEnabled = settings.authorizationStatus == .authorized
            hasCheckedPermission = true
        }
    }

    private func openSystemSettings() {
        if let settingsURL = URL(string: UIApplication.openSettingsURLString) {
            UIApplication.shared.open(settingsURL)
        }
    }
}

/// Row for individual notification type
struct NotificationTypeRow: View {
    let title: String
    let description: String
    let systemImage: String
    let isEnabled: Bool

    @State private var localEnabled: Bool

    init(title: String, description: String, systemImage: String, isEnabled: Bool) {
        self.title = title
        self.description = description
        self.systemImage = systemImage
        self.isEnabled = isEnabled
        self._localEnabled = State(initialValue: isEnabled)
    }

    var body: some View {
        Toggle(isOn: $localEnabled) {
            Label {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                    Text(description)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            } icon: {
                Image(systemName: systemImage)
                    .foregroundStyle(.accentColor)
            }
        }
        .accessibilityLabel("\(title): \(localEnabled ? "On" : "Off")")
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
        .environment(AuthManager())
        .environment(ThemeManager())
}

#Preview("Notification Settings") {
    NavigationStack {
        NotificationSettingsView()
    }
    .environment(ThemeManager())
}
