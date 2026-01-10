// WebSocketClientTests.swift
// Tests for WebSocketClient
//
// Created by iOS Native Agent - Phase 2

import XCTest
@testable import DiningPhilosophers

/// Tests for WebSocketClient
final class WebSocketClientTests: XCTestCase {

    // MARK: - Connection State Tests

    func testConnectionStateEquatable() {
        // Same states
        XCTAssertEqual(WebSocketClient.ConnectionState.disconnected, .disconnected)
        XCTAssertEqual(WebSocketClient.ConnectionState.connecting, .connecting)
        XCTAssertEqual(WebSocketClient.ConnectionState.connected, .connected)
        XCTAssertEqual(WebSocketClient.ConnectionState.reconnecting(attempt: 1), .reconnecting(attempt: 1))

        // Different states
        XCTAssertNotEqual(WebSocketClient.ConnectionState.disconnected, .connected)
        XCTAssertNotEqual(WebSocketClient.ConnectionState.reconnecting(attempt: 1), .reconnecting(attempt: 2))
    }

    func testConnectionStateIsConnected() {
        XCTAssertTrue(WebSocketClient.ConnectionState.connected.isConnected)
        XCTAssertFalse(WebSocketClient.ConnectionState.disconnected.isConnected)
        XCTAssertFalse(WebSocketClient.ConnectionState.connecting.isConnected)
        XCTAssertFalse(WebSocketClient.ConnectionState.reconnecting(attempt: 1).isConnected)
        XCTAssertFalse(WebSocketClient.ConnectionState.failed(.connectionFailed).isConnected)
    }

    // MARK: - Reconnection Config Tests

    func testReconnectionConfigDefault() {
        let config = WebSocketClient.ReconnectionConfig.default

        XCTAssertEqual(config.maxAttempts, 5)
        XCTAssertEqual(config.baseDelay, 1.0)
        XCTAssertEqual(config.maxDelay, 30.0)
        XCTAssertEqual(config.backoffMultiplier, 2.0)
    }

    func testReconnectionConfigNone() {
        let config = WebSocketClient.ReconnectionConfig.none

        XCTAssertEqual(config.maxAttempts, 0)
        XCTAssertEqual(config.baseDelay, 0)
    }

    func testReconnectionConfigDelayCalculation() {
        let config = WebSocketClient.ReconnectionConfig.default

        // Exponential backoff: 1, 2, 4, 8, 16, capped at 30
        XCTAssertEqual(config.delay(for: 1), 1.0)
        XCTAssertEqual(config.delay(for: 2), 2.0)
        XCTAssertEqual(config.delay(for: 3), 4.0)
        XCTAssertEqual(config.delay(for: 4), 8.0)
        XCTAssertEqual(config.delay(for: 5), 16.0)
        XCTAssertEqual(config.delay(for: 6), 30.0) // Capped at maxDelay
        XCTAssertEqual(config.delay(for: 10), 30.0) // Still capped
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

    func testWebSocketErrorSendFailed() {
        struct TestError: Error, LocalizedError {
            var errorDescription: String? { "Test error" }
        }

        let error = WebSocketError.sendFailed(TestError())
        XCTAssertEqual(error.errorDescription, "Failed to send message: Test error")
    }

    func testWebSocketErrorEquatable() {
        // Same errors
        XCTAssertEqual(WebSocketError.invalidURL, .invalidURL)
        XCTAssertEqual(WebSocketError.notConnected, .notConnected)
        XCTAssertEqual(WebSocketError.connectionFailed, .connectionFailed)
        XCTAssertEqual(WebSocketError.encodingFailed, .encodingFailed)

        // Different errors
        XCTAssertNotEqual(WebSocketError.invalidURL, .notConnected)
        XCTAssertNotEqual(WebSocketError.connectionFailed, .encodingFailed)
    }

    func testWebSocketErrorIsRecoverable() {
        XCTAssertTrue(WebSocketError.connectionFailed.isRecoverable)
        XCTAssertFalse(WebSocketError.invalidURL.isRecoverable)
        XCTAssertFalse(WebSocketError.notConnected.isRecoverable)
        XCTAssertFalse(WebSocketError.encodingFailed.isRecoverable)
    }

    // MARK: - WSMessage Extension Tests

    func testWSMessageSetSpeed() {
        let message = WSMessage.setSpeed(conversationId: "conv-123", speed: 1.5)

        XCTAssertEqual(message.type, .setSpeed)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.speedMultiplier, 1.5)
        XCTAssertNil(message.content)
        XCTAssertNil(message.senderName)
    }

    // MARK: - WebSocket Client Initial State Tests

    func testWebSocketClientInitialState() async {
        let client = WebSocketClient()
        let state = await client.state

        XCTAssertEqual(state, .disconnected)
    }

    // MARK: - Send Without Connection Tests

    func testSendWithoutConnectionThrows() async {
        let client = WebSocketClient()

        do {
            try await client.sendUserMessage("Hello")
            XCTFail("Expected error to be thrown")
        } catch let error as WebSocketError {
            XCTAssertEqual(error, .notConnected)
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    func testPauseWithoutConnectionThrows() async {
        let client = WebSocketClient()

        do {
            try await client.pause()
            XCTFail("Expected error to be thrown")
        } catch let error as WebSocketError {
            XCTAssertEqual(error, .notConnected)
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    func testResumeWithoutConnectionThrows() async {
        let client = WebSocketClient()

        do {
            try await client.resume()
            XCTFail("Expected error to be thrown")
        } catch let error as WebSocketError {
            XCTAssertEqual(error, .notConnected)
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    func testSetSpeedWithoutConnectionThrows() async {
        let client = WebSocketClient()

        do {
            try await client.setSpeed(2.0)
            XCTFail("Expected error to be thrown")
        } catch let error as WebSocketError {
            XCTAssertEqual(error, .notConnected)
        } catch {
            XCTFail("Unexpected error type: \(error)")
        }
    }

    // MARK: - Disconnect Tests

    func testDisconnectFromDisconnectedState() async {
        let client = WebSocketClient()

        // Should not throw or crash
        await client.disconnect()

        let state = await client.state
        XCTAssertEqual(state, .disconnected)
    }
}

// MARK: - WebSocket Message Type Tests

final class WSMessageTypeTests: XCTestCase {

    func testAllMessageTypesHaveRawValues() {
        let types: [WSMessageType] = [
            .join, .leave, .userMessage, .typingStart, .typingStop,
            .message, .thinkerTyping, .thinkerThinking, .thinkerStoppedTyping,
            .userJoined, .userLeft, .pause, .resume, .paused, .resumed,
            .setSpeed, .speedChanged, .error
        ]

        for type in types {
            XCTAssertFalse(type.rawValue.isEmpty, "Type \(type) should have a non-empty raw value")
        }
    }

    func testMessageTypeRawValues() {
        XCTAssertEqual(WSMessageType.join.rawValue, "join")
        XCTAssertEqual(WSMessageType.leave.rawValue, "leave")
        XCTAssertEqual(WSMessageType.userMessage.rawValue, "user_message")
        XCTAssertEqual(WSMessageType.typingStart.rawValue, "typing_start")
        XCTAssertEqual(WSMessageType.typingStop.rawValue, "typing_stop")
        XCTAssertEqual(WSMessageType.message.rawValue, "message")
        XCTAssertEqual(WSMessageType.thinkerTyping.rawValue, "thinker_typing")
        XCTAssertEqual(WSMessageType.thinkerThinking.rawValue, "thinker_thinking")
        XCTAssertEqual(WSMessageType.thinkerStoppedTyping.rawValue, "thinker_stopped_typing")
        XCTAssertEqual(WSMessageType.pause.rawValue, "pause")
        XCTAssertEqual(WSMessageType.resume.rawValue, "resume")
        XCTAssertEqual(WSMessageType.setSpeed.rawValue, "set_speed")
        XCTAssertEqual(WSMessageType.speedChanged.rawValue, "speed_changed")
        XCTAssertEqual(WSMessageType.error.rawValue, "error")
    }
}

// MARK: - WSMessage Factory Method Tests

final class WSMessageFactoryTests: XCTestCase {

    func testJoinMessageCreation() {
        let message = WSMessage.join(conversationId: "conv-123")

        XCTAssertEqual(message.type, .join)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertNil(message.content)
        XCTAssertNil(message.senderName)
        XCTAssertNil(message.senderType)
        XCTAssertNil(message.messageId)
        XCTAssertNil(message.cost)
        XCTAssertNil(message.speedMultiplier)
    }

    func testUserMessageCreation() {
        let message = WSMessage.userMessage(conversationId: "conv-123", content: "Hello, philosophers!")

        XCTAssertEqual(message.type, .userMessage)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.content, "Hello, philosophers!")
        XCTAssertEqual(message.senderType, "user")
        XCTAssertNotNil(message.timestamp)
        XCTAssertNil(message.senderName)
        XCTAssertNil(message.messageId)
        XCTAssertNil(message.cost)
    }

    func testPauseMessageCreation() {
        let message = WSMessage.pause(conversationId: "conv-123")

        XCTAssertEqual(message.type, .pause)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertNil(message.content)
    }

    func testResumeMessageCreation() {
        let message = WSMessage.resume(conversationId: "conv-123")

        XCTAssertEqual(message.type, .resume)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertNil(message.content)
    }

    func testSetSpeedMessageCreation() {
        let message = WSMessage.setSpeed(conversationId: "conv-123", speed: 2.5)

        XCTAssertEqual(message.type, .setSpeed)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.speedMultiplier, 2.5)
        XCTAssertNil(message.content)
    }
}
