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

/// Summary of a conversation for list views - matches backend ConversationSummary schema
struct ConversationSummary: Codable, Identifiable, Sendable, Hashable {
    let id: String
    let sessionId: String
    let topic: String
    let title: String?
    let isActive: Bool
    let createdAt: Date
    let thinkers: [ThinkerListItem]
    let messageCount: Int
    let totalCost: Double

    enum CodingKeys: String, CodingKey {
        case id
        case sessionId = "session_id"
        case topic
        case title
        case isActive = "is_active"
        case createdAt = "created_at"
        case thinkers
        case messageCount = "message_count"
        case totalCost = "total_cost"
    }

    /// Computed property for display title
    var displayTitle: String {
        title ?? topic
    }

    /// Computed property for thinker names
    var thinkerNames: [String] {
        thinkers.map(\.name)
    }

    // MARK: - Hashable

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    static func == (lhs: ConversationSummary, rhs: ConversationSummary) -> Bool {
        lhs.id == rhs.id
    }
}

/// Thinker item in list response - matches ThinkerResponse from backend
struct ThinkerListItem: Codable, Identifiable, Sendable, Hashable {
    let id: String
    let conversationId: String
    let name: String
    let bio: String
    let positions: String
    let style: String
    let color: String
    let imageUrl: String?
    let createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case conversationId = "conversation_id"
        case name
        case bio
        case positions
        case style
        case color
        case imageUrl = "image_url"
        case createdAt = "created_at"
    }
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

    enum CodingKeys: String, CodingKey {
        case id
        case conversationId = "conversation_id"
        case senderType = "sender_type"
        case senderName = "sender_name"
        case content
        case cost
        case createdAt = "created_at"
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

