// SettingsView.swift
// User settings and preferences
//
// Created by iOS Native Agent
// Updated by iOS Native Agent - Phase 7

import SwiftUI

/// Settings view with user preferences and app configuration
struct SettingsView: View {
    @Environment(AuthManager.self) private var authManager
    @Environment(SettingsManager.self) private var settingsManager
    @State private var isShowingLogoutConfirmation = false
    @State private var isShowingEditProfile = false
    @State private var isShowingLanguageSelection = false
    @State private var isShowingChangePassword = false

    var body: some View {
        NavigationStack {
            List {
                // User info section
                if let user = authManager.currentUser {
                    userSection(user: user)
                    usageSection(user: user)
                }

                // Appearance section
                appearanceSection

                // Notifications section
                notificationsSection

                // Preferences section
                preferencesSection

                // About section
                aboutSection

                // Account actions section
                accountActionsSection
            }
            .navigationTitle("Settings")
            .sheet(isPresented: $isShowingEditProfile) {
                EditProfileView()
            }
            .sheet(isPresented: $isShowingLanguageSelection) {
                LanguageSelectionView()
            }
            .sheet(isPresented: $isShowingChangePassword) {
                ChangePasswordView()
            }
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
        }
    }

    // MARK: - User Section

    @ViewBuilder
    private func userSection(user: User) -> some View {
        Section {
            Button {
                isShowingEditProfile = true
            } label: {
                HStack {
                    Image(systemName: "person.circle.fill")
                        .font(.system(size: 50))
                        .foregroundStyle(.secondary)
                        .accessibilityHidden(true)

                    VStack(alignment: .leading, spacing: 4) {
                        Text(user.displayName ?? user.username)
                            .font(.headline)
                            .foregroundStyle(.primary)
                        Text("@\(user.username)")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
                .padding(.vertical, 8)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Edit profile. \(user.displayName ?? user.username), @\(user.username)")
            .accessibilityHint("Double tap to edit your display name")

            LabeledContent("Member Since") {
                Text(user.createdAt, style: .date)
            }
            .accessibilityElement(children: .combine)
        } header: {
            Text("Account")
        }
    }

    // MARK: - Usage Section

    @ViewBuilder
    private func usageSection(user: User) -> some View {
        Section("Usage") {
            LabeledContent("Total Spend") {
                Text(user.totalSpend, format: .currency(code: "USD"))
            }
            .accessibilityElement(children: .combine)

            LabeledContent("Spend Limit") {
                Text(user.spendLimit, format: .currency(code: "USD"))
            }
            .accessibilityElement(children: .combine)
        }
    }

    // MARK: - Appearance Section

    @ViewBuilder
    private var appearanceSection: some View {
        Section("Appearance") {
            Picker("Theme", selection: Bindable(settingsManager).themePreference) {
                ForEach(ThemePreference.allCases) { theme in
                    Label(theme.title, systemImage: theme.icon)
                        .tag(theme)
                }
            }
            .accessibilityLabel("Theme")
            .accessibilityHint("Select light, dark, or system theme")
        }
    }

    // MARK: - Notifications Section

    @ViewBuilder
    private var notificationsSection: some View {
        Section("Notifications") {
            Toggle(isOn: Bindable(settingsManager).notificationsEnabled) {
                Label("Enable Notifications", systemImage: "bell")
            }
            .accessibilityHint("Turn on to receive push notifications")

            if settingsManager.notificationsEnabled {
                Toggle(isOn: Bindable(settingsManager).notifyNewMessages) {
                    Label("New Messages", systemImage: "message")
                }
                .accessibilityHint("Receive notifications when you get new messages")

                Toggle(isOn: Bindable(settingsManager).notifyThinkerResponses) {
                    Label("Thinker Responses", systemImage: "person.wave.2")
                }
                .accessibilityHint("Receive notifications when thinkers respond in conversations")
            }
        }
    }

    // MARK: - Preferences Section

    @ViewBuilder
    private var preferencesSection: some View {
        Section("Preferences") {
            Button {
                isShowingLanguageSelection = true
            } label: {
                HStack {
                    Label("Language", systemImage: "globe")
                        .foregroundStyle(.primary)
                    Spacer()
                    if let user = authManager.currentUser,
                       let language = SupportedLanguage(rawValue: user.languagePreference) {
                        Text("\(language.flag) \(language.displayName)")
                            .foregroundStyle(.secondary)
                    }
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Language")
            .accessibilityHint("Double tap to change language preference")

            Toggle(isOn: Bindable(settingsManager).compactLayout) {
                Label("Compact Layout", systemImage: "list.bullet")
            }
            .accessibilityHint("Use a more compact layout for conversation lists")

            Toggle(isOn: Bindable(settingsManager).showTimestamps) {
                Label("Show Timestamps", systemImage: "clock")
            }
            .accessibilityHint("Show message timestamps in conversations")
        }
    }

    // MARK: - About Section

    @ViewBuilder
    private var aboutSection: some View {
        Section("About") {
            LabeledContent("Version") {
                Text(appVersion)
            }
            .accessibilityElement(children: .combine)

            LabeledContent("Build") {
                Text(buildNumber)
            }
            .accessibilityElement(children: .combine)

            Link(destination: URL(string: "https://diningphilosophers.ai")!) {
                Label("Website", systemImage: "safari")
            }
            .accessibilityHint("Open the Dining Philosophers website in your browser")

            Link(destination: URL(string: "https://diningphilosophers.ai/privacy")!) {
                Label("Privacy Policy", systemImage: "hand.raised")
            }
            .accessibilityHint("Read our privacy policy")

            Link(destination: URL(string: "https://diningphilosophers.ai/terms")!) {
                Label("Terms of Service", systemImage: "doc.text")
            }
            .accessibilityHint("Read our terms of service")
        }
    }

    // MARK: - Account Actions Section

    @ViewBuilder
    private var accountActionsSection: some View {
        Section {
            Button {
                isShowingChangePassword = true
            } label: {
                Label("Change Password", systemImage: "key")
            }
            .accessibilityHint("Double tap to change your password")

            Button(role: .destructive) {
                isShowingLogoutConfirmation = true
            } label: {
                Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
            }
            .accessibilityHint("Double tap to sign out of your account")
        }
    }

    // MARK: - Helpers

    private var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
    }

    private var buildNumber: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
        .environment(AuthManager())
        .environment(SettingsManager.shared)
}
