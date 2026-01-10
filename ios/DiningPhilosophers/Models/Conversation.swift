// Conversation.swift
// Conversation and message models matching backend Pydantic schemas
//
// Created by iOS Native Agent

import Foundation

/// Conversation model - matches backend/app/schemas/conversation.py
struct Conversation: Codable, Identifiable, Sendable {
    let id: String
    let sessionId: String
    let topic: String
    let thinkers: [ConversationThinker]
    let messages: [Message]
    let totalCost: Decimal
    let createdAt: Date
    let updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case sessionId = "session_id"
        case topic
        case thinkers
        case messages
        case totalCost = "total_cost"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

/// Summary of a conversation for list views
struct ConversationSummary: Codable, Identifiable, Sendable {
    let id: String
    let topic: String
    let thinkerNames: [String]
    let thinkers: [ThinkerSummary]
    let messageCount: Int
    let totalCost: Decimal
    let createdAt: Date
    let updatedAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case topic
        case thinkerNames = "thinker_names"
        case thinkers
        case messageCount = "message_count"
        case totalCost = "total_cost"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

/// Message status for optimistic updates
enum MessageStatus: String, Codable, Sendable {
    case sending
    case sent
    case failed
}

/// Message within a conversation
struct Message: Codable, Identifiable, Sendable {
    let id: String
    let conversationId: String
    let senderType: SenderType
    let senderName: String?
    let content: String
    let cost: Decimal?
    let createdAt: Date
    var status: MessageStatus

    enum CodingKeys: String, CodingKey {
        case id
        case conversationId = "conversation_id"
        case senderType = "sender_type"
        case senderName = "sender_name"
        case content
        case cost
        case createdAt = "created_at"
        case status
    }

    init(
        id: String,
        conversationId: String,
        senderType: SenderType,
        senderName: String?,
        content: String,
        cost: Decimal?,
        createdAt: Date,
        status: MessageStatus = .sent
    ) {
        self.id = id
        self.conversationId = conversationId
        self.senderType = senderType
        self.senderName = senderName
        self.content = content
        self.cost = cost
        self.createdAt = createdAt
        self.status = status
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(String.self, forKey: .id)
        conversationId = try container.decode(String.self, forKey: .conversationId)
        senderType = try container.decode(SenderType.self, forKey: .senderType)
        senderName = try container.decodeIfPresent(String.self, forKey: .senderName)
        content = try container.decode(String.self, forKey: .content)
        cost = try container.decodeIfPresent(Decimal.self, forKey: .cost)
        createdAt = try container.decode(Date.self, forKey: .createdAt)
        // Status defaults to sent for messages from server
        status = try container.decodeIfPresent(MessageStatus.self, forKey: .status) ?? .sent
    }
}

/// Type of message sender
enum SenderType: String, Codable, Sendable {
    case user
    case thinker
    case system
}

/// Thinker in a conversation (full details)
struct ConversationThinker: Codable, Identifiable, Sendable {
    let id: String
    let name: String
    let bio: String
    let positions: String
    let style: String
    let color: String
    let imageUrl: String?

    enum CodingKeys: String, CodingKey {
        case id
        case name
        case bio
        case positions
        case style
        case color
        case imageUrl = "image_url"
    }
}

/// Thinker summary for list views
struct ThinkerSummary: Codable, Sendable {
    let name: String
    let imageUrl: String?

    enum CodingKeys: String, CodingKey {
        case name
        case imageUrl = "image_url"
    }
}
