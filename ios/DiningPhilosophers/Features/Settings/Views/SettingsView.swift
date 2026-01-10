// SettingsView.swift
// User settings and preferences
//
// Created by iOS Native Agent

import SwiftUI

/// Settings view
struct SettingsView: View {
    @Environment(AuthManager.self) private var authManager
    @State private var isShowingLogoutConfirmation = false

    var body: some View {
        NavigationStack {
            List {
                // User info section
                if let user = authManager.currentUser {
                    Section("Account") {
                        HStack {
                            Image(systemName: "person.circle.fill")
                                .font(.largeTitle)
                                .foregroundStyle(.secondary)

                            VStack(alignment: .leading) {
                                Text(user.displayName ?? user.username)
                                    .font(.headline)
                                Text("@\(user.username)")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 8)

                        LabeledContent("Member Since") {
                            Text(user.createdAt, style: .date)
                        }
                    }

                    // Usage section
                    Section("Usage") {
                        LabeledContent("Total Spend") {
                            Text(user.totalSpend, format: .currency(code: "USD"))
                        }

                        LabeledContent("Spend Limit") {
                            Text(user.spendLimit, format: .currency(code: "USD"))
                        }
                    }
                }

                // Preferences section
                Section("Preferences") {
                    NavigationLink {
                        Text("Language preferences coming soon")
                    } label: {
                        Label("Language", systemImage: "globe")
                    }

                    NavigationLink {
                        Text("Notification settings coming soon")
                    } label: {
                        Label("Notifications", systemImage: "bell")
                    }
                }

                // About section
                Section("About") {
                    LabeledContent("Version") {
                        Text(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
                    }

                    Link(destination: URL(string: "https://diningphilosophers.ai")!) {
                        Label("Website", systemImage: "safari")
                    }

                    Link(destination: URL(string: "https://diningphilosophers.ai/privacy")!) {
                        Label("Privacy Policy", systemImage: "hand.raised")
                    }
                }

                // Logout section
                Section {
                    Button(role: .destructive) {
                        isShowingLogoutConfirmation = true
                    } label: {
                        Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                }
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
        }
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
        .environment(AuthManager())
}
