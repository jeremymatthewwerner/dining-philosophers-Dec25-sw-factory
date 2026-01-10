// KeychainService.swift
// Secure token storage using iOS Keychain
//
// Created by iOS Native Agent
// Updated by iOS Native Agent - Phase 2

import Foundation
import Security

/// Service for secure storage of authentication tokens and sensitive data
actor KeychainService {
    static let shared = KeychainService()

    private let serviceName = "ai.diningphilosophers.app"

    // Key names for stored items
    private enum Key {
        static let accessToken = "auth_token"
        static let refreshToken = "refresh_token"
        static let userId = "user_id"
        static let tokenExpiry = "token_expiry"
    }

    private init() {}

    // MARK: - Access Token Management

    /// Store the authentication access token securely
    func storeToken(_ token: String) async throws {
        try save(key: Key.accessToken, value: token)
    }

    /// Retrieve the stored authentication access token
    func getToken() async -> String? {
        get(key: Key.accessToken)
    }

    /// Delete the stored access token
    func deleteToken() async throws {
        try delete(key: Key.accessToken)
    }

    /// Check if a token exists
    func hasToken() async -> Bool {
        await getToken() != nil
    }

    // MARK: - Refresh Token Management

    /// Store refresh token for token renewal
    func storeRefreshToken(_ token: String) async throws {
        try save(key: Key.refreshToken, value: token)
    }

    /// Retrieve refresh token
    func getRefreshToken() async -> String? {
        get(key: Key.refreshToken)
    }

    /// Delete refresh token
    func deleteRefreshToken() async throws {
        try delete(key: Key.refreshToken)
    }

    // MARK: - Token Expiry Management

    /// Store token expiry date
    func storeTokenExpiry(_ date: Date) async throws {
        let timestamp = String(date.timeIntervalSince1970)
        try save(key: Key.tokenExpiry, value: timestamp)
    }

    /// Get token expiry date
    func getTokenExpiry() async -> Date? {
        guard let timestamp = get(key: Key.tokenExpiry),
              let interval = TimeInterval(timestamp) else {
            return nil
        }
        return Date(timeIntervalSince1970: interval)
    }

    /// Check if token is expired
    func isTokenExpired() async -> Bool {
        guard let expiry = await getTokenExpiry() else {
            // No expiry stored, assume not expired
            return false
        }
        return Date() >= expiry
    }

    /// Delete token expiry
    func deleteTokenExpiry() async throws {
        try delete(key: Key.tokenExpiry)
    }

    // MARK: - User ID Management

    /// Store user ID
    func storeUserId(_ userId: String) async throws {
        try save(key: Key.userId, value: userId)
    }

    /// Get stored user ID
    func getUserId() async -> String? {
        get(key: Key.userId)
    }

    /// Delete user ID
    func deleteUserId() async throws {
        try delete(key: Key.userId)
    }

    // MARK: - Bulk Operations

    /// Store all auth credentials at once
    func storeCredentials(
        accessToken: String,
        refreshToken: String? = nil,
        userId: String? = nil,
        expiry: Date? = nil
    ) async throws {
        try await storeToken(accessToken)

        if let refreshToken = refreshToken {
            try await storeRefreshToken(refreshToken)
        }

        if let userId = userId {
            try await storeUserId(userId)
        }

        if let expiry = expiry {
            try await storeTokenExpiry(expiry)
        }
    }

    /// Clear all stored credentials (for logout)
    func clearAllCredentials() async throws {
        // Attempt to delete all, even if some fail
        var errors: [Error] = []

        do {
            try await deleteToken()
        } catch {
            errors.append(error)
        }

        do {
            try await deleteRefreshToken()
        } catch {
            errors.append(error)
        }

        do {
            try await deleteUserId()
        } catch {
            errors.append(error)
        }

        do {
            try await deleteTokenExpiry()
        } catch {
            errors.append(error)
        }

        // If all operations failed, throw the first error
        if errors.count == 4 {
            throw errors[0]
        }
    }

    // MARK: - Private Keychain Helpers

    private func save(key: String, value: String) throws {
        guard let data = value.data(using: .utf8) else {
            throw KeychainError.encodingFailed
        }

        // Delete any existing item first
        try? delete(key: key)

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            // Only accessible when device is unlocked, not backed up to iCloud
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        let status = SecItemAdd(query as CFDictionary, nil)

        guard status == errSecSuccess else {
            throw KeychainError.saveFailed(status)
        }
    }

    private func get(key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }

        return value
    }

    private func delete(key: String) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: key
        ]

        let status = SecItemDelete(query as CFDictionary)

        // It's okay if item doesn't exist
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.deleteFailed(status)
        }
    }

    private func exists(key: String) -> Bool {
        get(key: key) != nil
    }

    // MARK: - Migration & Validation

    /// Validate that stored credentials are complete
    func hasValidCredentials() async -> Bool {
        guard await hasToken() else {
            return false
        }

        // Check if token is expired (if expiry is stored)
        if await isTokenExpired() {
            return false
        }

        return true
    }
}

// MARK: - KeychainError

/// Keychain-related errors
enum KeychainError: Error, LocalizedError, Equatable {
    case encodingFailed
    case saveFailed(OSStatus)
    case deleteFailed(OSStatus)
    case itemNotFound

    static func == (lhs: KeychainError, rhs: KeychainError) -> Bool {
        switch (lhs, rhs) {
        case (.encodingFailed, .encodingFailed):
            return true
        case (.itemNotFound, .itemNotFound):
            return true
        case (.saveFailed(let lhsStatus), .saveFailed(let rhsStatus)):
            return lhsStatus == rhsStatus
        case (.deleteFailed(let lhsStatus), .deleteFailed(let rhsStatus)):
            return lhsStatus == rhsStatus
        default:
            return false
        }
    }

    var errorDescription: String? {
        switch self {
        case .encodingFailed:
            return "Failed to encode data for keychain storage"
        case .saveFailed(let status):
            return "Failed to save to keychain (status: \(status))"
        case .deleteFailed(let status):
            return "Failed to delete from keychain (status: \(status))"
        case .itemNotFound:
            return "Item not found in keychain"
        }
    }

    /// Human-readable status code description
    var statusDescription: String? {
        switch self {
        case .saveFailed(let status), .deleteFailed(let status):
            return SecCopyErrorMessageString(status, nil) as String?
        default:
            return nil
        }
    }
}
