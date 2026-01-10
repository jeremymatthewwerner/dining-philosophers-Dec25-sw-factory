// WebSocketClientTests.swift
// Tests for WebSocket client
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Tests for WebSocketClient and related types
final class WebSocketClientTests: XCTestCase {

    // MARK: - Error Tests

    func testWebSocketErrorDescriptions() {
        let errors: [(WebSocketError, String)] = [
            (.invalidURL, "Invalid WebSocket URL"),
            (.notConnected, "Not connected to conversation")
        ]

        for (error, expectedDescription) in errors {
            XCTAssertEqual(error.errorDescription, expectedDescription)
        }
    }

    func testSendFailedErrorDescription() {
        let underlyingError = NSError(domain: "test", code: -1, userInfo: [NSLocalizedDescriptionKey: "Connection refused"])
        let error = WebSocketError.sendFailed(underlyingError)
        XCTAssertEqual(error.errorDescription, "Failed to send message: Connection refused")
    }

    // MARK: - WSMessage Factory Tests

    func testJoinMessage() {
        let message = WSMessage.join(conversationId: "conv-123")

        XCTAssertEqual(message.type, .join)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertNil(message.content)
        XCTAssertNil(message.senderName)
    }

    func testUserMessage() {
        let message = WSMessage.userMessage(conversationId: "conv-123", content: "Hello, philosophers!")

        XCTAssertEqual(message.type, .userMessage)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.content, "Hello, philosophers!")
        XCTAssertEqual(message.senderType, "user")
        XCTAssertNotNil(message.timestamp)
    }

    func testPauseMessage() {
        let message = WSMessage.pause(conversationId: "conv-456")

        XCTAssertEqual(message.type, .pause)
        XCTAssertEqual(message.conversationId, "conv-456")
    }

    func testResumeMessage() {
        let message = WSMessage.resume(conversationId: "conv-456")

        XCTAssertEqual(message.type, .resume)
        XCTAssertEqual(message.conversationId, "conv-456")
    }

    func testSetSpeedMessage() {
        let message = WSMessage.setSpeed(conversationId: "conv-789", speed: 2.0)

        XCTAssertEqual(message.type, .setSpeed)
        XCTAssertEqual(message.conversationId, "conv-789")
        XCTAssertEqual(message.speedMultiplier, 2.0)
    }

    // MARK: - Message Encoding Tests

    func testWSMessageEncodesToJSON() throws {
        let message = WSMessage.userMessage(conversationId: "conv-123", content: "Test message")

        let encoder = JSONEncoder()
        let data = try encoder.encode(message)
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(json["type"] as? String, "user_message")
        XCTAssertEqual(json["conversation_id"] as? String, "conv-123")
        XCTAssertEqual(json["content"] as? String, "Test message")
        XCTAssertEqual(json["sender_type"] as? String, "user")
    }

    // MARK: - Message Decoding Tests

    func testWSMessageDecodesFromJSON() throws {
        let json = """
        {
            "type": "message",
            "conversation_id": "conv-123",
            "content": "I think, therefore I am.",
            "sender_name": "Descartes",
            "sender_type": "thinker",
            "message_id": "msg-456",
            "timestamp": "2024-01-01T12:00:00Z",
            "cost": "0.05"
        }
        """

        let data = json.data(using: .utf8)!
        let message = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(message.type, .message)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.content, "I think, therefore I am.")
        XCTAssertEqual(message.senderName, "Descartes")
        XCTAssertEqual(message.senderType, "thinker")
        XCTAssertEqual(message.messageId, "msg-456")
    }

    func testTypingIndicatorDecoding() throws {
        let json = """
        {
            "type": "thinker_typing",
            "sender_name": "Socrates"
        }
        """

        let data = json.data(using: .utf8)!
        let message = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(message.type, .thinkerTyping)
        XCTAssertEqual(message.senderName, "Socrates")
    }

    func testSpeedChangedDecoding() throws {
        let json = """
        {
            "type": "speed_changed",
            "conversation_id": "conv-123",
            "speed_multiplier": 1.5
        }
        """

        let data = json.data(using: .utf8)!
        let message = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(message.type, .speedChanged)
        XCTAssertEqual(message.speedMultiplier, 1.5)
    }

    // MARK: - WSMessageType Tests

    func testAllMessageTypesHaveCorrectRawValues() {
        XCTAssertEqual(WSMessageType.join.rawValue, "join")
        XCTAssertEqual(WSMessageType.leave.rawValue, "leave")
        XCTAssertEqual(WSMessageType.userMessage.rawValue, "user_message")
        XCTAssertEqual(WSMessageType.typingStart.rawValue, "typing_start")
        XCTAssertEqual(WSMessageType.typingStop.rawValue, "typing_stop")
        XCTAssertEqual(WSMessageType.message.rawValue, "message")
        XCTAssertEqual(WSMessageType.thinkerTyping.rawValue, "thinker_typing")
        XCTAssertEqual(WSMessageType.thinkerThinking.rawValue, "thinker_thinking")
        XCTAssertEqual(WSMessageType.thinkerStoppedTyping.rawValue, "thinker_stopped_typing")
        XCTAssertEqual(WSMessageType.userJoined.rawValue, "user_joined")
        XCTAssertEqual(WSMessageType.userLeft.rawValue, "user_left")
        XCTAssertEqual(WSMessageType.pause.rawValue, "pause")
        XCTAssertEqual(WSMessageType.resume.rawValue, "resume")
        XCTAssertEqual(WSMessageType.paused.rawValue, "paused")
        XCTAssertEqual(WSMessageType.resumed.rawValue, "resumed")
        XCTAssertEqual(WSMessageType.setSpeed.rawValue, "set_speed")
        XCTAssertEqual(WSMessageType.speedChanged.rawValue, "speed_changed")
        XCTAssertEqual(WSMessageType.error.rawValue, "error")
    }
}
