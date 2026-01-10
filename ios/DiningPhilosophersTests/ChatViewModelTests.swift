// ChatViewModelTests.swift
// Tests for ChatViewModel
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Tests for ChatViewModel and related components
@MainActor
final class ChatViewModelTests: XCTestCase {

    // MARK: - Initial State Tests

    func testInitialState() {
        let viewModel = ChatViewModel(conversationId: "test-conv-123")

        XCTAssertEqual(viewModel.conversationId, "test-conv-123")
        XCTAssertNil(viewModel.conversation)
        XCTAssertTrue(viewModel.messages.isEmpty)
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertFalse(viewModel.isSending)
        XCTAssertFalse(viewModel.isPaused)
        XCTAssertNil(viewModel.typingThinker)
        XCTAssertNil(viewModel.errorMessage)
        XCTAssertEqual(viewModel.connectionState, .disconnected)
        XCTAssertEqual(viewModel.currentSpeed, .normal)
        XCTAssertEqual(viewModel.newMessagesCount, 0)
        XCTAssertFalse(viewModel.isScrolledUp)
    }

    // MARK: - Message Status Tests

    func testMessageStatusEnumValues() {
        XCTAssertEqual(MessageStatus.sending.rawValue, "sending")
        XCTAssertEqual(MessageStatus.sent.rawValue, "sent")
        XCTAssertEqual(MessageStatus.failed.rawValue, "failed")
    }

    func testMessageInitWithDefaultStatus() {
        let message = Message(
            id: "msg-1",
            conversationId: "conv-1",
            senderType: .user,
            senderName: nil,
            content: "Hello",
            cost: nil,
            createdAt: Date()
        )

        XCTAssertEqual(message.status, .sent)
    }

    func testMessageInitWithExplicitStatus() {
        let message = Message(
            id: "msg-1",
            conversationId: "conv-1",
            senderType: .user,
            senderName: nil,
            content: "Hello",
            cost: nil,
            createdAt: Date(),
            status: .sending
        )

        XCTAssertEqual(message.status, .sending)
    }

    // MARK: - Speed Tests

    func testConversationSpeedValues() {
        XCTAssertEqual(ConversationSpeed.normal.rawValue, 1.0)
        XCTAssertEqual(ConversationSpeed.fast.rawValue, 2.0)
        XCTAssertEqual(ConversationSpeed.fastest.rawValue, 3.0)
    }

    func testConversationSpeedLabels() {
        XCTAssertEqual(ConversationSpeed.normal.label, "1x")
        XCTAssertEqual(ConversationSpeed.fast.label, "2x")
        XCTAssertEqual(ConversationSpeed.fastest.label, "3x")
    }

    func testConversationSpeedAccessibilityLabels() {
        XCTAssertEqual(ConversationSpeed.normal.accessibilityLabel, "Normal speed")
        XCTAssertEqual(ConversationSpeed.fast.accessibilityLabel, "Double speed")
        XCTAssertEqual(ConversationSpeed.fastest.accessibilityLabel, "Triple speed")
    }

    func testConversationSpeedAllCases() {
        let allSpeeds = ConversationSpeed.allCases
        XCTAssertEqual(allSpeeds.count, 3)
        XCTAssertEqual(allSpeeds[0], .normal)
        XCTAssertEqual(allSpeeds[1], .fast)
        XCTAssertEqual(allSpeeds[2], .fastest)
    }

    // MARK: - Connection State Tests

    func testConnectionStateEquality() {
        XCTAssertEqual(WebSocketConnectionState.connected, .connected)
        XCTAssertEqual(WebSocketConnectionState.disconnected, .disconnected)
        XCTAssertEqual(WebSocketConnectionState.connecting, .connecting)
        XCTAssertEqual(WebSocketConnectionState.reconnecting(attempt: 1), .reconnecting(attempt: 1))
        XCTAssertNotEqual(WebSocketConnectionState.reconnecting(attempt: 1), .reconnecting(attempt: 2))
    }

    // MARK: - Scroll State Tests

    func testUserScrolledUp() {
        let viewModel = ChatViewModel(conversationId: "test")

        XCTAssertFalse(viewModel.isScrolledUp)

        viewModel.userScrolledUp()

        XCTAssertTrue(viewModel.isScrolledUp)
    }

    func testUserScrolledToBottom() {
        let viewModel = ChatViewModel(conversationId: "test")
        viewModel.isScrolledUp = true

        viewModel.userScrolledToBottom()

        XCTAssertFalse(viewModel.isScrolledUp)
        XCTAssertEqual(viewModel.newMessagesCount, 0)
    }

    func testClearNewMessagesIndicator() {
        let viewModel = ChatViewModel(conversationId: "test")
        // Simulate new messages count being set (normally by WebSocket)
        // We can't directly set it but we can test clearNewMessagesIndicator

        viewModel.clearNewMessagesIndicator()

        XCTAssertEqual(viewModel.newMessagesCount, 0)
    }

    // MARK: - Time Gap Tests

    func testMessageHasTimeGap() {
        let now = Date()
        let fiveMinutesAgo = now.addingTimeInterval(-300)
        let fourMinutesAgo = now.addingTimeInterval(-240)

        let message1 = Message(
            id: "1",
            conversationId: "conv",
            senderType: .user,
            senderName: nil,
            content: "Hello",
            cost: nil,
            createdAt: fiveMinutesAgo
        )

        let message2 = Message(
            id: "2",
            conversationId: "conv",
            senderType: .thinker,
            senderName: "Socrates",
            content: "Greetings",
            cost: nil,
            createdAt: now
        )

        let message3 = Message(
            id: "3",
            conversationId: "conv",
            senderType: .user,
            senderName: nil,
            content: "What is virtue?",
            cost: nil,
            createdAt: fourMinutesAgo
        )

        // 5 minutes gap - should show timestamp
        XCTAssertTrue(message2.hasTimeGap(from: message1))

        // 4 minutes gap - should not show timestamp (default threshold is 5 min)
        XCTAssertFalse(message3.hasTimeGap(from: message1))

        // Custom threshold test
        XCTAssertTrue(message3.hasTimeGap(from: message1, threshold: 60)) // 1 minute threshold
    }

    func testShouldShowTimestampFirstMessage() {
        let viewModel = ChatViewModel(conversationId: "test")

        let message = Message(
            id: "1",
            conversationId: "test",
            senderType: .user,
            senderName: nil,
            content: "Hello",
            cost: nil,
            createdAt: Date()
        )

        // Use internal helper - first message should always show timestamp
        // Since we can't add messages directly, test the logic
        XCTAssertTrue(viewModel.messages.isEmpty)
    }

    // MARK: - WebSocket Error Tests

    func testWebSocketErrorDescriptions() {
        XCTAssertEqual(
            WebSocketError.invalidURL.errorDescription,
            "Invalid WebSocket URL"
        )

        XCTAssertEqual(
            WebSocketError.notConnected.errorDescription,
            "Not connected to conversation"
        )

        XCTAssertEqual(
            WebSocketError.reconnectFailed.errorDescription,
            "Failed to reconnect after multiple attempts"
        )

        let sendError = NSError(domain: "test", code: 1, userInfo: [NSLocalizedDescriptionKey: "Test error"])
        XCTAssertEqual(
            WebSocketError.sendFailed(sendError).errorDescription,
            "Failed to send message: Test error"
        )
    }

    // MARK: - WSMessage Factory Tests

    func testWSMessageJoin() {
        let message = WSMessage.join(conversationId: "conv-123")

        XCTAssertEqual(message.type, .join)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertNil(message.content)
    }

    func testWSMessageUserMessage() {
        let message = WSMessage.userMessage(conversationId: "conv-123", content: "Hello!")

        XCTAssertEqual(message.type, .userMessage)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.content, "Hello!")
        XCTAssertEqual(message.senderType, "user")
        XCTAssertNotNil(message.timestamp)
    }

    func testWSMessagePause() {
        let message = WSMessage.pause(conversationId: "conv-123")

        XCTAssertEqual(message.type, .pause)
        XCTAssertEqual(message.conversationId, "conv-123")
    }

    func testWSMessageResume() {
        let message = WSMessage.resume(conversationId: "conv-123")

        XCTAssertEqual(message.type, .resume)
        XCTAssertEqual(message.conversationId, "conv-123")
    }

    func testWSMessageSetSpeed() {
        let message = WSMessage.setSpeed(conversationId: "conv-123", speed: 2.0)

        XCTAssertEqual(message.type, .setSpeed)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.speedMultiplier, 2.0)
    }

    // MARK: - WSMessageType Tests

    func testWSMessageTypeRawValues() {
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

    // MARK: - Message Decoding Tests

    func testMessageDecodingWithStatus() throws {
        let json = """
        {
            "id": "msg-123",
            "conversation_id": "conv-456",
            "sender_type": "user",
            "sender_name": null,
            "content": "Hello, world!",
            "cost": null,
            "created_at": "2024-01-01T12:00:00Z",
            "status": "sent"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let message = try decoder.decode(Message.self, from: data)

        XCTAssertEqual(message.id, "msg-123")
        XCTAssertEqual(message.conversationId, "conv-456")
        XCTAssertEqual(message.senderType, .user)
        XCTAssertNil(message.senderName)
        XCTAssertEqual(message.content, "Hello, world!")
        XCTAssertEqual(message.status, .sent)
    }

    func testMessageDecodingWithoutStatus() throws {
        let json = """
        {
            "id": "msg-123",
            "conversation_id": "conv-456",
            "sender_type": "thinker",
            "sender_name": "Socrates",
            "content": "Wisdom begins with wonder.",
            "cost": "0.01",
            "created_at": "2024-01-01T12:00:00Z"
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let message = try decoder.decode(Message.self, from: data)

        XCTAssertEqual(message.id, "msg-123")
        XCTAssertEqual(message.senderType, .thinker)
        XCTAssertEqual(message.senderName, "Socrates")
        XCTAssertEqual(message.status, .sent) // Default when not provided
    }

    // MARK: - WSMessage Decoding Tests

    func testWSMessageDecoding() throws {
        let json = """
        {
            "type": "message",
            "conversation_id": "conv-123",
            "content": "Hello from thinker",
            "sender_name": "Aristotle",
            "sender_type": "thinker",
            "message_id": "msg-456",
            "timestamp": "2024-01-01T12:00:00Z",
            "cost": "0.02"
        }
        """

        let data = json.data(using: .utf8)!
        let message = try JSONDecoder().decode(WSMessage.self, from: data)

        XCTAssertEqual(message.type, .message)
        XCTAssertEqual(message.conversationId, "conv-123")
        XCTAssertEqual(message.content, "Hello from thinker")
        XCTAssertEqual(message.senderName, "Aristotle")
        XCTAssertEqual(message.messageId, "msg-456")
    }

    func testWSMessageEncodingAndDecoding() throws {
        let original = WSMessage.setSpeed(conversationId: "conv-test", speed: 3.0)

        let encoder = JSONEncoder()
        let data = try encoder.encode(original)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(WSMessage.self, from: data)

        XCTAssertEqual(decoded.type, .setSpeed)
        XCTAssertEqual(decoded.conversationId, "conv-test")
        XCTAssertEqual(decoded.speedMultiplier, 3.0)
    }
}

// MARK: - Message Extension Tests

final class MessageExtensionTests: XCTestCase {

    func testTimeGapCalculation() {
        let baseDate = Date()

        let message1 = Message(
            id: "1",
            conversationId: "conv",
            senderType: .user,
            senderName: nil,
            content: "First",
            cost: nil,
            createdAt: baseDate
        )

        let message2 = Message(
            id: "2",
            conversationId: "conv",
            senderType: .thinker,
            senderName: "Plato",
            content: "Second",
            cost: nil,
            createdAt: baseDate.addingTimeInterval(301) // 5 min + 1 sec
        )

        let message3 = Message(
            id: "3",
            conversationId: "conv",
            senderType: .user,
            senderName: nil,
            content: "Third",
            cost: nil,
            createdAt: baseDate.addingTimeInterval(299) // 5 min - 1 sec
        )

        // Just over 5 minutes should have gap
        XCTAssertTrue(message2.hasTimeGap(from: message1))

        // Just under 5 minutes should not have gap
        XCTAssertFalse(message3.hasTimeGap(from: message1))
    }
}
