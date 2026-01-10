// AuthViewModelTests.swift
// Tests for authentication view model
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

final class AuthViewModelTests: XCTestCase {

    // MARK: - AuthManager Initial State Tests

    func testAuthManagerInitialState() {
        let authManager = AuthManager()

        // Initial state should be not authenticated
        XCTAssertFalse(authManager.isAuthenticated)
        XCTAssertNil(authManager.currentUser)
    }

    // MARK: - EmptyResponse Tests

    func testEmptyResponseDecoding() throws {
        let json = "{}".data(using: .utf8)!
        let decoder = JSONDecoder()

        let response = try decoder.decode(EmptyResponse.self, from: json)
        XCTAssertNotNil(response)
    }

    // MARK: - AuthResponse Tests

    func testAuthResponseDecoding() throws {
        let json = """
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "user": {
                "id": "user123",
                "username": "testuser",
                "display_name": "Test User",
                "is_admin": false,
                "total_spend": "0.00",
                "spend_limit": "100.00",
                "language_preference": "en",
                "created_at": "2024-01-01T12:00:00Z"
            }
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let response = try decoder.decode(AuthResponse.self, from: json)

        XCTAssertEqual(response.accessToken, "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
        XCTAssertEqual(response.user.id, "user123")
        XCTAssertEqual(response.user.username, "testuser")
    }

    // MARK: - Session Tests

    func testSessionDecoding() throws {
        let json = """
        {
            "id": "session123",
            "created_at": "2024-01-01T12:00:00Z"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let session = try decoder.decode(Session.self, from: json)

        XCTAssertEqual(session.id, "session123")
    }

    // MARK: - UserWithStats Tests

    func testUserWithStatsDecoding() throws {
        let json = """
        {
            "id": "user123",
            "username": "testuser",
            "display_name": "Test User",
            "is_admin": true,
            "total_spend": "25.50",
            "spend_limit": "200.00",
            "language_preference": "en",
            "created_at": "2024-01-01T12:00:00Z",
            "conversation_count": 15
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let user = try decoder.decode(UserWithStats.self, from: json)

        XCTAssertEqual(user.id, "user123")
        XCTAssertTrue(user.isAdmin)
        XCTAssertEqual(user.conversationCount, 15)
    }
}
