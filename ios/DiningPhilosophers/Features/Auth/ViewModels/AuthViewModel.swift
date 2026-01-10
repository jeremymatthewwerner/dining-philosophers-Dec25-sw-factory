// AuthViewModel.swift
// Authentication state management
//
// Created by iOS Native Agent

import Foundation

/// Global authentication manager
@Observable
final class AuthManager: Sendable {
    private(set) var currentUser: User?
    private(set) var isAuthenticated = false
    private(set) var isLoading = false

    init() {
        // Check for existing token on init
        Task {
            await checkExistingAuth()
        }
    }

    /// Check if user has existing valid session
    @MainActor
    func checkExistingAuth() async {
        guard await KeychainService.shared.hasToken() else {
            return
        }

        isLoading = true
        defer { isLoading = false }

        do {
            let user: User = try await APIClient.shared.get(.me)
            self.currentUser = user
            self.isAuthenticated = true
        } catch {
            // Token invalid, clear it
            try? await KeychainService.shared.deleteToken()
        }
    }

    /// Log in with username and password
    @MainActor
    func login(username: String, password: String) async throws {
        isLoading = true
        defer { isLoading = false }

        let request = APIRequest.Login(username: username, password: password)
        let response: AuthResponse = try await APIClient.shared.post(.login, body: request)

        try await KeychainService.shared.storeToken(response.accessToken)
        self.currentUser = response.user
        self.isAuthenticated = true
    }

    /// Register a new account
    @MainActor
    func register(username: String, password: String, displayName: String?) async throws {
        isLoading = true
        defer { isLoading = false }

        let request = APIRequest.Register(
            username: username,
            password: password,
            displayName: displayName
        )
        let response: AuthResponse = try await APIClient.shared.post(.register, body: request)

        try await KeychainService.shared.storeToken(response.accessToken)
        self.currentUser = response.user
        self.isAuthenticated = true
    }

    /// Log out
    @MainActor
    func logout() async {
        isLoading = true
        defer { isLoading = false }

        // Try to logout on server, but don't fail if it errors
        try? await APIClient.shared.post(.logout) as EmptyResponse

        // Always clear local state
        try? await KeychainService.shared.deleteToken()
        self.currentUser = nil
        self.isAuthenticated = false
    }
}

/// Empty response for endpoints that return nothing
struct EmptyResponse: Decodable {}
