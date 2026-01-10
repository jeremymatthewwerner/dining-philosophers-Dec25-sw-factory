// DiningPhilosophersTests.swift
// Main test suite entry point
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Main test class for DiningPhilosophers app
final class DiningPhilosophersTests: XCTestCase {

    // MARK: - Model Tests

    func testUserDecoding() throws {
        let json = """
        {
            "id": "user-123",
            "username": "testuser",
            "display_name": "Test User",
            "is_admin": false,
            "total_spend": "0.00",
            "spend_limit": "100.00",
            "language_preference": "en",
            "created_at": "2024-01-01T00:00:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let user = try decoder.decode(User.self, from: data)

        XCTAssertEqual(user.id, "user-123")
        XCTAssertEqual(user.username, "testuser")
        XCTAssertEqual(user.displayName, "Test User")
        XCTAssertFalse(user.isAdmin)
    }

    func testConversationSummaryDecoding() throws {
        let json = """
        {
            "id": "conv-123",
            "topic": "Philosophy of Mind",
            "thinker_names": ["Descartes", "Locke"],
            "thinkers": [
                {"name": "Descartes", "image_url": null},
                {"name": "Locke", "image_url": null}
            ],
            "message_count": 10,
            "total_cost": "0.50",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let conversation = try decoder.decode(ConversationSummary.self, from: data)

        XCTAssertEqual(conversation.id, "conv-123")
        XCTAssertEqual(conversation.topic, "Philosophy of Mind")
        XCTAssertEqual(conversation.thinkers.count, 2)
        XCTAssertEqual(conversation.messageCount, 10)
    }

    func testMessageDecoding() throws {
        let json = """
        {
            "id": "msg-123",
            "conversation_id": "conv-123",
            "sender_type": "thinker",
            "sender_name": "Descartes",
            "content": "I think, therefore I am.",
            "cost": "0.01",
            "created_at": "2024-01-01T00:00:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let message = try decoder.decode(Message.self, from: data)

        XCTAssertEqual(message.id, "msg-123")
        XCTAssertEqual(message.senderType, .thinker)
        XCTAssertEqual(message.senderName, "Descartes")
        XCTAssertEqual(message.content, "I think, therefore I am.")
    }

    // MARK: - WebSocket Message Tests

    func testWSMessageTypeDecoding() throws {
        let testCases: [(String, WSMessageType)] = [
            ("join", .join),
            ("leave", .leave),
            ("user_message", .userMessage),
            ("message", .message),
            ("thinker_typing", .thinkerTyping),
            ("thinker_stopped_typing", .thinkerStoppedTyping),
            ("pause", .pause),
            ("resume", .resume),
            ("paused", .paused),
            ("resumed", .resumed),
            ("error", .error)
        ]

        for (rawValue, expectedType) in testCases {
            let json = "\"\(rawValue)\""
            let data = json.data(using: .utf8)!
            let decoded = try JSONDecoder().decode(WSMessageType.self, from: data)
            XCTAssertEqual(decoded, expectedType, "Failed to decode \(rawValue)")
        }
    }

    func testWSMessageJoinCreation() {
        let message = WSMessage.join(conversationId: "conv-123")

        XCTAssertEqual(message.type, .join)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertNil(message.content)
    }

    func testWSMessageUserMessageCreation() {
        let message = WSMessage.userMessage(conversationId: "conv-123", content: "Hello")

        XCTAssertEqual(message.type, .userMessage)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.content, "Hello")
        XCTAssertEqual(message.senderType, "user")
        XCTAssertNotNil(message.timestamp)
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
}
