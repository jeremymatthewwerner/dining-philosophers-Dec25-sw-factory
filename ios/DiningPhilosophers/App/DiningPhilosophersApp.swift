// DiningPhilosophersApp.swift
// Main entry point for the Dining Philosophers iOS app
//
// Created by iOS Native Agent

import SwiftUI

@main
struct DiningPhilosophersApp: App {
    @State private var authManager = AuthManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(authManager)
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
