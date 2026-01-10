// DiningPhilosophersTests.swift
// Main test file for the Dining Philosophers iOS app
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

final class DiningPhilosophersTests: XCTestCase {

    override func setUpWithError() throws {
        // Put setup code here. This method is called before the invocation of each test method in the class.
    }

    override func tearDownWithError() throws {
        // Put teardown code here. This method is called after the invocation of each test method in the class.
    }

    // MARK: - Model Tests

    func testUserDecoding() throws {
        let json = """
        {
            "id": "user123",
            "username": "testuser",
            "display_name": "Test User",
            "is_admin": false,
            "total_spend": "10.50",
            "spend_limit": "100.00",
            "language_preference": "en",
            "created_at": "2024-01-01T12:00:00Z"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let user = try decoder.decode(User.self, from: json)

        XCTAssertEqual(user.id, "user123")
        XCTAssertEqual(user.username, "testuser")
        XCTAssertEqual(user.displayName, "Test User")
        XCTAssertFalse(user.isAdmin)
        XCTAssertEqual(user.languagePreference, "en")
    }

    func testConversationSummaryDecoding() throws {
        let json = """
        {
            "id": "conv123",
            "topic": "Philosophy of Mind",
            "thinker_names": ["Socrates", "Plato"],
            "thinkers": [
                {"name": "Socrates", "image_url": null},
                {"name": "Plato", "image_url": null}
            ],
            "message_count": 10,
            "total_cost": "0.05",
            "created_at": "2024-01-01T12:00:00Z",
            "updated_at": "2024-01-01T13:00:00Z"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let conversation = try decoder.decode(ConversationSummary.self, from: json)

        XCTAssertEqual(conversation.id, "conv123")
        XCTAssertEqual(conversation.topic, "Philosophy of Mind")
        XCTAssertEqual(conversation.thinkerNames, ["Socrates", "Plato"])
        XCTAssertEqual(conversation.messageCount, 10)
    }

    func testSenderTypeDecoding() throws {
        XCTAssertEqual(SenderType(rawValue: "user"), .user)
        XCTAssertEqual(SenderType(rawValue: "thinker"), .thinker)
        XCTAssertEqual(SenderType(rawValue: "system"), .system)
        XCTAssertNil(SenderType(rawValue: "invalid"))
    }

    // MARK: - Endpoint Tests

    func testEndpointPaths() {
        XCTAssertEqual(Endpoint.login.path, "/api/auth/login")
        XCTAssertEqual(Endpoint.register.path, "/api/auth/register")
        XCTAssertEqual(Endpoint.me.path, "/api/auth/me")
        XCTAssertEqual(Endpoint.conversations.path, "/api/conversations")
        XCTAssertEqual(Endpoint.conversation(id: "123").path, "/api/conversations/123")
        XCTAssertEqual(Endpoint.thinkers.path, "/api/thinkers")
    }

    func testEndpointAuthRequirements() {
        XCTAssertFalse(Endpoint.login.requiresAuth)
        XCTAssertFalse(Endpoint.register.requiresAuth)
        XCTAssertTrue(Endpoint.me.requiresAuth)
        XCTAssertTrue(Endpoint.conversations.requiresAuth)
        XCTAssertTrue(Endpoint.thinkers.requiresAuth)
    }

    // MARK: - Performance Tests

    func testModelDecodingPerformance() throws {
        let json = """
        {
            "id": "user123",
            "username": "testuser",
            "display_name": "Test User",
            "is_admin": false,
            "total_spend": "10.50",
            "spend_limit": "100.00",
            "language_preference": "en",
            "created_at": "2024-01-01T12:00:00Z"
        }
        """.data(using: .utf8)!

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        measure {
            for _ in 0..<1000 {
                _ = try? decoder.decode(User.self, from: json)
            }
        }
    }
}
