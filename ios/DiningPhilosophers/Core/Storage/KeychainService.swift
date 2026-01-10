// KeychainService.swift
// Secure token storage using iOS Keychain
//
// Created by iOS Native Agent

import Foundation
import Security

/// Service for secure storage of authentication tokens
actor KeychainService {
    static let shared = KeychainService()

    private let serviceName = "ai.diningphilosophers.app"
    private let tokenKey = "auth_token"

    private init() {}

    // MARK: - Token Management

    /// Store the authentication token securely
    func storeToken(_ token: String) async throws {
        guard let data = token.data(using: .utf8) else {
            throw KeychainError.encodingFailed
        }

        // Delete any existing token first
        try? await deleteToken()

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: tokenKey,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        let status = SecItemAdd(query as CFDictionary, nil)

        guard status == errSecSuccess else {
            throw KeychainError.saveFailed(status)
        }
    }

    /// Retrieve the stored authentication token
    func getToken() async -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: tokenKey,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else {
            return nil
        }

        return token
    }

    /// Delete the stored token
    func deleteToken() async throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: tokenKey
        ]

        let status = SecItemDelete(query as CFDictionary)

        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.deleteFailed(status)
        }
    }

    /// Check if a token exists
    func hasToken() async -> Bool {
        await getToken() != nil
    }
}

/// Keychain-related errors
enum KeychainError: Error, LocalizedError {
    case encodingFailed
    case saveFailed(OSStatus)
    case deleteFailed(OSStatus)

    var errorDescription: String? {
        switch self {
        case .encodingFailed:
            return "Failed to encode token"
        case .saveFailed(let status):
            return "Failed to save token (status: \(status))"
        case .deleteFailed(let status):
            return "Failed to delete token (status: \(status))"
        }
    }
}
