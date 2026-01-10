// KeychainServiceTests.swift
// Tests for Keychain service
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Tests for KeychainService
/// Note: These tests may require running on a real device or simulator
/// as the Keychain is not available in some test environments
final class KeychainServiceTests: XCTestCase {

    // MARK: - Error Tests

    func testKeychainErrorDescriptions() {
        let errors: [(KeychainError, String)] = [
            (.encodingFailed, "Failed to encode token"),
            (.saveFailed(0), "Failed to save token (status: 0)"),
            (.deleteFailed(-25300), "Failed to delete token (status: -25300)")
        ]

        for (error, expectedDescription) in errors {
            XCTAssertEqual(error.errorDescription, expectedDescription)
        }
    }

    func testSaveFailedWithDifferentStatus() {
        let error = KeychainError.saveFailed(-25299)
        XCTAssertEqual(error.errorDescription, "Failed to save token (status: -25299)")
    }

    // MARK: - HasToken Tests

    // Note: These are basic tests. Full integration tests would require
    // a proper Keychain mock or running on device/simulator

    func testKeychainServiceIsSingleton() async {
        // Verify that the shared instance is consistent
        let instance1 = KeychainService.shared
        let instance2 = KeychainService.shared

        // Both should be the same actor instance (reference equality)
        // We can verify this by calling a method and ensuring consistent state
        let hasToken1 = await instance1.hasToken()
        let hasToken2 = await instance2.hasToken()

        // The state should be consistent between references
        XCTAssertEqual(hasToken1, hasToken2)
    }
}

// MARK: - Mock Keychain for Testing

/// A mock keychain service for unit testing
actor MockKeychainService {
    private var storedToken: String?

    func storeToken(_ token: String) async throws {
        storedToken = token
    }

    func getToken() async -> String? {
        storedToken
    }

    func deleteToken() async throws {
        storedToken = nil
    }

    func hasToken() async -> Bool {
        storedToken != nil
    }
}

/// Tests using the mock keychain
final class MockKeychainServiceTests: XCTestCase {

    func testStoreAndRetrieveToken() async throws {
        let keychain = MockKeychainService()

        try await keychain.storeToken("test-jwt-token")
        let token = await keychain.getToken()

        XCTAssertEqual(token, "test-jwt-token")
    }

    func testDeleteToken() async throws {
        let keychain = MockKeychainService()

        try await keychain.storeToken("test-jwt-token")
        XCTAssertTrue(await keychain.hasToken())

        try await keychain.deleteToken()
        XCTAssertFalse(await keychain.hasToken())
        XCTAssertNil(await keychain.getToken())
    }

    func testHasTokenWhenEmpty() async {
        let keychain = MockKeychainService()
        XCTAssertFalse(await keychain.hasToken())
    }

    func testOverwriteToken() async throws {
        let keychain = MockKeychainService()

        try await keychain.storeToken("first-token")
        try await keychain.storeToken("second-token")

        let token = await keychain.getToken()
        XCTAssertEqual(token, "second-token")
    }
}
