// WebSocketMessage.swift
// WebSocket message types matching frontend/src/types/index.ts
//
// Created by iOS Native Agent

import Foundation

/// WebSocket message types - matches frontend types
enum WSMessageType: String, Codable, Sendable {
    case join
    case leave
    case userMessage = "user_message"
    case typingStart = "typing_start"
    case typingStop = "typing_stop"
    case message
    case thinkerTyping = "thinker_typing"
    case thinkerThinking = "thinker_thinking"
    case thinkerStoppedTyping = "thinker_stopped_typing"
    case userJoined = "user_joined"
    case userLeft = "user_left"
    case pause
    case resume
    case paused
    case resumed
    case setSpeed = "set_speed"
    case speedChanged = "speed_changed"
    case error
}

/// WebSocket message structure
struct WSMessage: Codable, Sendable {
    let type: WSMessageType
    let conversationId: String?
    let content: String?
    let senderName: String?
    let senderType: String?
    let messageId: String?
    let timestamp: String?
    let cost: Decimal?
    let speedMultiplier: Double?

    enum CodingKeys: String, CodingKey {
        case type
        case conversationId = "conversation_id"
        case content
        case senderName = "sender_name"
        case senderType = "sender_type"
        case messageId = "message_id"
        case timestamp
        case cost
        case speedMultiplier = "speed_multiplier"
    }

    /// Create a join message
    static func join(conversationId: String) -> WSMessage {
        WSMessage(
            type: .join,
            conversationId: conversationId,
            content: nil,
            senderName: nil,
            senderType: nil,
            messageId: nil,
            timestamp: nil,
            cost: nil,
            speedMultiplier: nil
        )
    }

    /// Create a user message
    static func userMessage(conversationId: String, content: String) -> WSMessage {
        WSMessage(
            type: .userMessage,
            conversationId: conversationId,
            content: content,
            senderName: nil,
            senderType: "user",
            messageId: nil,
            timestamp: ISO8601DateFormatter().string(from: Date()),
            cost: nil,
            speedMultiplier: nil
        )
    }

    /// Create a pause message
    static func pause(conversationId: String) -> WSMessage {
        WSMessage(
            type: .pause,
            conversationId: conversationId,
            content: nil,
            senderName: nil,
            senderType: nil,
            messageId: nil,
            timestamp: nil,
            cost: nil,
            speedMultiplier: nil
        )
    }

    /// Create a resume message
    static func resume(conversationId: String) -> WSMessage {
        WSMessage(
            type: .resume,
            conversationId: conversationId,
            content: nil,
            senderName: nil,
            senderType: nil,
            messageId: nil,
            timestamp: nil,
            cost: nil,
            speedMultiplier: nil
        )
    }

    /// Create a set speed message
    static func setSpeed(conversationId: String, speed: Double) -> WSMessage {
        WSMessage(
            type: .setSpeed,
            conversationId: conversationId,
            content: nil,
            senderName: nil,
            senderType: nil,
            messageId: nil,
            timestamp: nil,
            cost: nil,
            speedMultiplier: speed
        )
    }
}
