// AuthViewModelTests.swift
// Tests for authentication view model
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Tests for AuthManager/AuthViewModel
@MainActor
final class AuthViewModelTests: XCTestCase {

    // MARK: - Initial State Tests

    func testInitialState() {
        let authManager = AuthManager()

        XCTAssertNil(authManager.currentUser)
        XCTAssertFalse(authManager.isAuthenticated)
    }

    // MARK: - Keychain Error Tests

    func testKeychainErrorDescriptions() {
        let errors: [(KeychainError, String)] = [
            (.encodingFailed, "Failed to encode data for keychain storage"),
            (.saveFailed(0), "Failed to save to keychain (status: 0)"),
            (.deleteFailed(-25300), "Failed to delete from keychain (status: -25300)"),
            (.itemNotFound, "Item not found in keychain")
        ]

        for (error, expectedDescription) in errors {
            XCTAssertEqual(error.errorDescription, expectedDescription)
        }
    }

    // MARK: - WebSocket Error Tests

    func testWebSocketErrorDescriptions() {
        let errors: [(WebSocketError, String)] = [
            (.invalidURL, "Invalid WebSocket URL"),
            (.notConnected, "Not connected to conversation"),
            (.connectionFailed, "Failed to connect to server"),
            (.encodingFailed, "Failed to encode message")
        ]

        for (error, expectedDescription) in errors {
            XCTAssertEqual(error.errorDescription, expectedDescription)
        }
    }

    // MARK: - Sender Type Tests

    func testSenderTypeRawValues() {
        XCTAssertEqual(SenderType.user.rawValue, "user")
        XCTAssertEqual(SenderType.thinker.rawValue, "thinker")
        XCTAssertEqual(SenderType.system.rawValue, "system")
    }

    func testSenderTypeDecoding() throws {
        let testCases = ["user", "thinker", "system"]

        for type in testCases {
            let json = "\"\(type)\""
            let data = json.data(using: .utf8)!
            let decoded = try JSONDecoder().decode(SenderType.self, from: data)
            XCTAssertEqual(decoded.rawValue, type)
        }
    }
}

// MARK: - Thinker Model Tests

final class ThinkerModelTests: XCTestCase {

    func testThinkerProfileDecoding() throws {
        let json = """
        {
            "name": "Aristotle",
            "bio": "Ancient Greek philosopher",
            "positions": "Virtue ethics, empiricism",
            "style": "Systematic, logical",
            "image_url": "https://example.com/aristotle.jpg"
        }
        """

        let data = json.data(using: .utf8)!
        let profile = try JSONDecoder().decode(ThinkerProfile.self, from: data)

        XCTAssertEqual(profile.name, "Aristotle")
        XCTAssertEqual(profile.bio, "Ancient Greek philosopher")
        XCTAssertEqual(profile.imageUrl, "https://example.com/aristotle.jpg")
    }

    func testThinkerSuggestionDecoding() throws {
        let json = """
        {
            "name": "Socrates",
            "reason": "Expert in dialectic method",
            "profile": {
                "name": "Socrates",
                "bio": "Classical Greek philosopher",
                "positions": "Socratic method, ethics",
                "style": "Questioning, dialectic",
                "image_url": null
            }
        }
        """

        let data = json.data(using: .utf8)!
        let suggestion = try JSONDecoder().decode(ThinkerSuggestion.self, from: data)

        XCTAssertEqual(suggestion.name, "Socrates")
        XCTAssertEqual(suggestion.reason, "Expert in dialectic method")
        XCTAssertEqual(suggestion.profile.style, "Questioning, dialectic")
        XCTAssertNil(suggestion.profile.imageUrl)
    }

    func testConversationThinkerDecoding() throws {
        let json = """
        {
            "id": "thinker-123",
            "name": "Plato",
            "bio": "Student of Socrates",
            "positions": "Theory of Forms",
            "style": "Dialogues, mythology",
            "color": "#4A90D9",
            "image_url": "https://example.com/plato.jpg"
        }
        """

        let data = json.data(using: .utf8)!
        let thinker = try JSONDecoder().decode(ConversationThinker.self, from: data)

        XCTAssertEqual(thinker.id, "thinker-123")
        XCTAssertEqual(thinker.name, "Plato")
        XCTAssertEqual(thinker.color, "#4A90D9")
    }
}

// MARK: - Session Model Tests

final class SessionModelTests: XCTestCase {

    func testSessionDecoding() throws {
        let json = """
        {
            "id": "session-123",
            "created_at": "2024-01-01T00:00:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let session = try decoder.decode(Session.self, from: data)

        XCTAssertEqual(session.id, "session-123")
        XCTAssertNotNil(session.createdAt)
    }

    func testUserWithStatsDecoding() throws {
        let json = """
        {
            "id": "user-123",
            "username": "testuser",
            "display_name": "Test User",
            "is_admin": true,
            "total_spend": "25.50",
            "spend_limit": "100.00",
            "language_preference": "en",
            "created_at": "2024-01-01T00:00:00Z",
            "conversation_count": 15
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let user = try decoder.decode(UserWithStats.self, from: data)

        XCTAssertEqual(user.id, "user-123")
        XCTAssertTrue(user.isAdmin)
        XCTAssertEqual(user.conversationCount, 15)
    }
}
