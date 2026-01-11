// DiningPhilosophersApp.swift
// Main entry point for the Dining Philosophers iOS app
//
// Created by iOS Native Agent
// Updated by iOS Native Agent - Phase 7

import SwiftUI

@main
struct DiningPhilosophersApp: App {
    @State private var authManager = AuthManager()
    @State private var themeManager = ThemeManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(authManager)
                .environment(themeManager)
                .preferredColorScheme(themeManager.preferredColorScheme)
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
    @State private var selectedTab = 0
    @State private var showingNewConversation = false
    @State private var preselectedThinker: Thinker?

    var body: some View {
        TabView(selection: $selectedTab) {
            ConversationListView()
                .tabItem {
                    Label("Conversations", systemImage: "bubble.left.and.bubble.right")
                }
                .tag(0)

            NavigationStack {
                ThinkerBrowserView(mode: .browse)
                    .navigationDestination(for: Thinker.self) { thinker in
                        ThinkerDetailView(thinker: thinker, onStartConversation: { selectedThinker in
                            preselectedThinker = selectedThinker
                            showingNewConversation = true
                        })
                    }
            }
            .tabItem {
                Label("Thinkers", systemImage: "person.3")
            }
            .tag(1)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gear")
                }
                .tag(2)
        }
        .sheet(isPresented: $showingNewConversation) {
            NewConversationWizardView(
                preselectedThinker: preselectedThinker,
                onConversationCreated: { conversationId in
                    showingNewConversation = false
                    preselectedThinker = nil
                    // Switch to conversations tab
                    selectedTab = 0
                }
            )
        }
    }
}

// MARK: - Preview

#Preview {
    ContentView()
        .environment(AuthManager())
}
