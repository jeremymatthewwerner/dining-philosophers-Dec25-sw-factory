// APIClient+Auth.swift
// Authentication API methods
//
// Created by iOS Native Agent

import Foundation

// MARK: - Authentication Methods

extension APIClient {
    /// Register a new user
    /// - Parameters:
    ///   - username: The username for the new account
    ///   - password: The password for the new account
    ///   - displayName: Optional display name
    /// - Returns: AuthResponse containing token and user
    func register(
        username: String,
        password: String,
        displayName: String? = nil
    ) async throws -> AuthResponse {
        let request = APIRequest.Register(
            username: username,
            password: password,
            displayName: displayName
        )
        return try await post(.register, body: request)
    }

    /// Log in an existing user
    /// - Parameters:
    ///   - username: The username
    ///   - password: The password
    /// - Returns: AuthResponse containing token and user
    func login(username: String, password: String) async throws -> AuthResponse {
        let request = APIRequest.Login(username: username, password: password)
        return try await post(.login, body: request)
    }

    /// Get the current authenticated user
    /// - Returns: The current User
    func getCurrentUser() async throws -> User {
        try await get(.me)
    }

    /// Log out the current user
    func logout() async throws {
        try await delete(.logout)
        try await KeychainService.shared.deleteToken()
    }
}
