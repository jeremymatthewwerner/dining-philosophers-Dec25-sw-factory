// ChatViewModelTests.swift
// Tests for ChatViewModel
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Tests for ChatViewModel
@MainActor
final class ChatViewModelTests: XCTestCase {

    // MARK: - Initialization Tests

    func testInitialization() {
        let viewModel = ChatViewModel(conversationId: "test-123")

        XCTAssertEqual(viewModel.conversationId, "test-123")
        XCTAssertNil(viewModel.conversation)
        XCTAssertTrue(viewModel.messages.isEmpty)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertFalse(viewModel.isSending)
        XCTAssertFalse(viewModel.isPaused)
        XCTAssertNil(viewModel.typingThinker)
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertEqual(viewModel.speedMultiplier, 1.0)
    }

    // MARK: - State Tests

    func testClearError() {
        let viewModel = ChatViewModel(conversationId: "test-123")

        // Simulate an error was set (normally done by internal methods)
        // We can only test clearError since errorMessage is private(set)
        viewModel.clearError()

        XCTAssertNil(viewModel.errorMessage)
    }

    // MARK: - WebSocket Message Tests

    func testWSMessageSetSpeedCreation() {
        let message = WSMessage.setSpeed(conversationId: "conv-123", speed: 2.0)

        XCTAssertEqual(message.type, .setSpeed)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.speedMultiplier, 2.0)
        XCTAssertNil(message.content)
        XCTAssertNil(message.senderName)
    }

    func testWSMessagePauseCreation() {
        let message = WSMessage.pause(conversationId: "conv-123")

        XCTAssertEqual(message.type, .pause)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertNil(message.speedMultiplier)
    }

    func testWSMessageResumeCreation() {
        let message = WSMessage.resume(conversationId: "conv-123")

        XCTAssertEqual(message.type, .resume)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertNil(message.speedMultiplier)
    }

    // MARK: - Message Model Tests

    func testMessageSenderTypeUser() throws {
        let json = """
        {
            "id": "msg-123",
            "conversation_id": "conv-123",
            "sender_type": "user",
            "sender_name": null,
            "content": "Hello!",
            "cost": null,
            "created_at": "2024-01-01T00:00:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let message = try decoder.decode(Message.self, from: data)

        XCTAssertEqual(message.senderType, .user)
        XCTAssertNil(message.senderName)
        XCTAssertNil(message.cost)
    }

    func testMessageSenderTypeSystem() throws {
        let json = """
        {
            "id": "msg-123",
            "conversation_id": "conv-123",
            "sender_type": "system",
            "sender_name": null,
            "content": "Conversation started",
            "cost": null,
            "created_at": "2024-01-01T00:00:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let message = try decoder.decode(Message.self, from: data)

        XCTAssertEqual(message.senderType, .system)
    }

    func testMessageWithCost() throws {
        let json = """
        {
            "id": "msg-123",
            "conversation_id": "conv-123",
            "sender_type": "thinker",
            "sender_name": "Socrates",
            "content": "Know thyself.",
            "cost": "0.0025",
            "created_at": "2024-01-01T00:00:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let message = try decoder.decode(Message.self, from: data)

        XCTAssertNotNil(message.cost)
        XCTAssertEqual(message.cost, Decimal(string: "0.0025"))
    }

    // MARK: - WebSocket Message Type Tests

    func testWSMessageTypeSpeedRelated() throws {
        let setSpeedJson = "\"set_speed\""
        let speedChangedJson = "\"speed_changed\""

        let decoder = JSONDecoder()

        let setSpeed = try decoder.decode(WSMessageType.self, from: setSpeedJson.data(using: .utf8)!)
        XCTAssertEqual(setSpeed, .setSpeed)

        let speedChanged = try decoder.decode(WSMessageType.self, from: speedChangedJson.data(using: .utf8)!)
        XCTAssertEqual(speedChanged, .speedChanged)
    }

    func testWSMessageTypeThinkerRelated() throws {
        let testCases: [(String, WSMessageType)] = [
            ("thinker_typing", .thinkerTyping),
            ("thinker_thinking", .thinkerThinking),
            ("thinker_stopped_typing", .thinkerStoppedTyping)
        ]

        for (rawValue, expectedType) in testCases {
            let json = "\"\(rawValue)\""
            let data = json.data(using: .utf8)!
            let decoded = try JSONDecoder().decode(WSMessageType.self, from: data)
            XCTAssertEqual(decoded, expectedType, "Failed to decode \(rawValue)")
        }
    }

    // MARK: - Full WebSocket Message Tests

    func testWSMessageDecoding() throws {
        let json = """
        {
            "type": "message",
            "conversation_id": "conv-123",
            "content": "The unexamined life is not worth living.",
            "sender_name": "Socrates",
            "sender_type": "thinker",
            "message_id": "msg-456",
            "timestamp": "2024-01-01T12:00:00Z",
            "cost": "0.01",
            "speed_multiplier": null
        }
        """

        let data = json.data(using: .utf8)!
        let message = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(message.type, .message)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.content, "The unexamined life is not worth living.")
        XCTAssertEqual(message.senderName, "Socrates")
        XCTAssertEqual(message.senderType, "thinker")
        XCTAssertEqual(message.messageId, "msg-456")
        XCTAssertEqual(message.timestamp, "2024-01-01T12:00:00Z")
        XCTAssertEqual(message.cost, Decimal(string: "0.01"))
        XCTAssertNil(message.speedMultiplier)
    }

    func testWSMessageSpeedChangedDecoding() throws {
        let json = """
        {
            "type": "speed_changed",
            "conversation_id": "conv-123",
            "content": null,
            "sender_name": null,
            "sender_type": null,
            "message_id": null,
            "timestamp": null,
            "cost": null,
            "speed_multiplier": 1.5
        }
        """

        let data = json.data(using: .utf8)!
        let message = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(message.type, .speedChanged)
        XCTAssertEqual(message.speedMultiplier, 1.5)
    }

    // MARK: - WebSocket Message Encoding Tests

    func testWSMessageJoinEncoding() throws {
        let message = WSMessage.join(conversationId: "conv-123")
        let data = try JSONEncoder().encode(message)
        let decoded = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(decoded.type, .join)
        XCTAssertEqual(decoded.conversationId, "conv-123")
    }

    func testWSMessageUserMessageEncoding() throws {
        let message = WSMessage.userMessage(conversationId: "conv-123", content: "Hello philosophers!")
        let data = try JSONEncoder().encode(message)
        let decoded = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(decoded.type, .userMessage)
        XCTAssertEqual(decoded.conversationId, "conv-123")
        XCTAssertEqual(decoded.content, "Hello philosophers!")
        XCTAssertEqual(decoded.senderType, "user")
    }

    func testWSMessageSetSpeedEncoding() throws {
        let message = WSMessage.setSpeed(conversationId: "conv-123", speed: 2.5)
        let data = try JSONEncoder().encode(message)
        let decoded = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(decoded.type, .setSpeed)
        XCTAssertEqual(decoded.conversationId, "conv-123")
        XCTAssertEqual(decoded.speedMultiplier, 2.5)
    }
}
