// DiningPhilosophersApp.swift
// Main entry point for the Dining Philosophers iOS app
//
// Created by iOS Native Agent
// Updated by iOS Native Agent - Phase 7

import SwiftUI

@main
struct DiningPhilosophersApp: App {
    @State private var authManager = AuthManager()
    @State private var settingsManager = SettingsManager.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(authManager)
                .environment(settingsManager)
                .preferredColorScheme(settingsManager.preferredColorScheme)
        }
    }
}

/// Root view that handles authentication state
struct ContentView: View {
    @Environment(AuthManager.self) private var authManager

    var body: some View {
        Group {
            if authManager.isAuthenticated {
                MainTabView()
            } else {
                LoginView()
            }
        }
        .animation(.default, value: authManager.isAuthenticated)
    }
}

/// Main tab view for authenticated users
struct MainTabView: View {
    var body: some View {
        TabView {
            ConversationListView()
                .tabItem {
                    Label("Conversations", systemImage: "bubble.left.and.bubble.right")
                }

            NavigationStack {
                ThinkerBrowserView(mode: .browse)
                    .navigationDestination(for: Thinker.self) { thinker in
                        ThinkerDetailView(thinker: thinker)
                    }
            }
            .tabItem {
                Label("Thinkers", systemImage: "person.3")
            }

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
        }
    }
}

// MARK: - Preview

#Preview {
    ContentView()
        .environment(AuthManager())
}
