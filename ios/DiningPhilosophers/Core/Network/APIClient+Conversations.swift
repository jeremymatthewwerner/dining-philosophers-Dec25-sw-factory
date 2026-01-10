// APIClient+Conversations.swift
// Conversation API methods
//
// Created by iOS Native Agent

import Foundation

// MARK: - Conversation Methods

extension APIClient {
    /// Fetch all conversations for the current user
    /// - Returns: Array of ConversationSummary
    func getConversations() async throws -> [ConversationSummary] {
        try await get(.conversations)
    }

    /// Get a specific conversation with full details
    /// - Parameter id: The conversation ID
    /// - Returns: The Conversation with messages
    func getConversation(id: String) async throws -> Conversation {
        try await get(.conversation(id: id))
    }

    /// Create a new conversation
    /// - Parameters:
    ///   - topic: The conversation topic
    ///   - thinkerIds: Array of thinker IDs to participate
    /// - Returns: The created Conversation
    func createConversation(topic: String, thinkerIds: [String]) async throws -> Conversation {
        let request = APIRequest.CreateConversation(topic: topic, thinkerIds: thinkerIds)
        return try await post(.createConversation, body: request)
    }

    /// Get messages for a conversation
    /// - Parameter conversationId: The conversation ID
    /// - Returns: Array of Message
    func getMessages(conversationId: String) async throws -> [Message] {
        try await get(.messages(conversationId: conversationId))
    }

    /// Send a message to a conversation
    /// - Parameters:
    ///   - content: The message content
    ///   - conversationId: The conversation ID
    /// - Returns: The created Message
    func sendMessage(content: String, conversationId: String) async throws -> Message {
        let request = APIRequest.SendMessage(content: content)
        return try await post(.sendMessage(conversationId: conversationId), body: request)
    }
}
