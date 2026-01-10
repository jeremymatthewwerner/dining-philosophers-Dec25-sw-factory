// ChatViewModel.swift
// View model for chat with WebSocket support
//
// Created by iOS Native Agent

import Foundation

/// ViewModel for real-time chat
@Observable
@MainActor
final class ChatViewModel: WebSocketDelegate {
    let conversationId: String

    private(set) var conversation: Conversation?
    private(set) var messages: [Message] = []
    private(set) var isLoading = false
    private(set) var isSending = false
    private(set) var isPaused = false
    private(set) var typingThinker: String?
    private(set) var errorMessage: String?
    var speedMultiplier: Double = 1.0

    private let webSocket = WebSocketClient()

    init(conversationId: String) {
        self.conversationId = conversationId
    }

    // MARK: - Connection

    /// Connect to conversation and load messages
    func connect() async {
        isLoading = true
        defer { isLoading = false }

        // Load conversation details
        do {
            conversation = try await APIClient.shared.get(.conversation(id: conversationId))
            messages = conversation?.messages ?? []
        } catch {
            errorMessage = error.localizedDescription
            return
        }

        // Connect WebSocket
        do {
            await webSocket.delegate = self
            try await webSocket.connect(conversationId: conversationId)
        } catch {
            errorMessage = "Failed to connect to chat: \(error.localizedDescription)"
        }
    }

    /// Disconnect from WebSocket
    func disconnect() async {
        await webSocket.disconnect()
    }

    // MARK: - Actions

    /// Send a message
    func sendMessage(_ content: String) async {
        isSending = true
        defer { isSending = false }

        // Add optimistic message
        let optimisticMessage = Message(
            id: UUID().uuidString,
            conversationId: conversationId,
            senderType: .user,
            senderName: nil,
            content: content,
            cost: nil,
            createdAt: Date()
        )
        messages.append(optimisticMessage)

        do {
            try await webSocket.sendUserMessage(content)
        } catch {
            // Remove optimistic message on failure
            messages.removeAll { $0.id == optimisticMessage.id }
            errorMessage = error.localizedDescription
        }
    }

    /// Toggle conversation pause state
    func togglePause() async {
        do {
            if isPaused {
                try await webSocket.resume()
            } else {
                try await webSocket.pause()
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Set conversation speed
    func setSpeed(_ speed: Double) async {
        do {
            try await webSocket.setSpeed(speed)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Clear error message
    func clearError() {
        errorMessage = nil
    }

    // MARK: - WebSocketDelegate

    nonisolated func webSocketDidReceiveMessage(_ message: WSMessage) async {
        await MainActor.run {
            if let content = message.content,
               let messageId = message.messageId,
               let timestamp = message.timestamp {
                let newMessage = Message(
                    id: messageId,
                    conversationId: conversationId,
                    senderType: .thinker,
                    senderName: message.senderName,
                    content: content,
                    cost: message.cost,
                    createdAt: ISO8601DateFormatter().date(from: timestamp) ?? Date()
                )
                messages.append(newMessage)
                typingThinker = nil
            }
        }
    }

    nonisolated func webSocketThinkerTyping(name: String) async {
        await MainActor.run {
            typingThinker = name
        }
    }

    nonisolated func webSocketThinkerStoppedTyping(name: String) async {
        await MainActor.run {
            if typingThinker == name {
                typingThinker = nil
            }
        }
    }

    nonisolated func webSocketConversationPaused() async {
        await MainActor.run {
            isPaused = true
        }
    }

    nonisolated func webSocketConversationResumed() async {
        await MainActor.run {
            isPaused = false
        }
    }

    nonisolated func webSocketSpeedChanged(_ speed: Double) async {
        await MainActor.run {
            speedMultiplier = speed
        }
    }

    nonisolated func webSocketDidReceiveError(_ error: String) async {
        await MainActor.run {
            errorMessage = error
        }
    }

    nonisolated func webSocketDidDisconnect(error: Error?) async {
        await MainActor.run {
            if let error {
                errorMessage = "Disconnected: \(error.localizedDescription)"
            }
        }
    }
}
