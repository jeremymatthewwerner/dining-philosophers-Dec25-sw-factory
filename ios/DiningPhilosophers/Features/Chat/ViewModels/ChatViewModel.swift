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
    private(set) var connectionState: WebSocketConnectionState = .disconnected
    private(set) var currentSpeed: ConversationSpeed = .normal
    private(set) var newMessagesCount = 0

    /// Whether the user has scrolled away from the bottom
    var isScrolledUp = false

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

    /// Reconnect after disconnection
    func reconnect() async {
        guard connectionState == .disconnected else { return }

        do {
            try await webSocket.connect(conversationId: conversationId)
        } catch {
            errorMessage = "Failed to reconnect: \(error.localizedDescription)"
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
        let optimisticId = UUID().uuidString

        // Add optimistic message with sending status
        let optimisticMessage = Message(
            id: optimisticId,
            conversationId: conversationId,
            senderType: .user,
            senderName: nil,
            content: content,
            cost: nil,
            createdAt: Date(),
            status: .sending
        )
        messages.append(optimisticMessage)

        do {
            try await webSocket.sendUserMessage(content)
            // Update status to sent
            updateMessageStatus(id: optimisticId, status: .sent)
        } catch {
            // Update status to failed
            updateMessageStatus(id: optimisticId, status: .failed)
            errorMessage = error.localizedDescription
        }

        isSending = false
    }

    /// Retry sending a failed message
    func retryMessage(id: String) async {
        guard let index = messages.firstIndex(where: { $0.id == id }),
              messages[index].status == .failed else {
            return
        }

        let content = messages[index].content

        // Remove the failed message
        messages.remove(at: index)

        // Send as new message
        await sendMessage(content)
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
    func setSpeed(_ speed: ConversationSpeed) async {
        do {
            try await webSocket.setSpeed(speed.rawValue)
            currentSpeed = speed
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Clear new messages indicator and reset count
    func clearNewMessagesIndicator() {
        newMessagesCount = 0
    }

    /// Called when user scrolls to bottom
    func userScrolledToBottom() {
        isScrolledUp = false
        clearNewMessagesIndicator()
    }

    /// Called when user scrolls up
    func userScrolledUp() {
        isScrolledUp = true
    }

    // MARK: - Private Helpers

    private func updateMessageStatus(id: String, status: MessageStatus) {
        if let index = messages.firstIndex(where: { $0.id == id }) {
            messages[index].status = status
        }
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
                    createdAt: ISO8601DateFormatter().date(from: timestamp) ?? Date(),
                    status: .sent
                )
                messages.append(newMessage)
                typingThinker = nil

                // Update new messages count if scrolled up
                if isScrolledUp {
                    newMessagesCount += 1
                }
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
            if let newSpeed = ConversationSpeed(rawValue: speed) {
                currentSpeed = newSpeed
            }
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

    nonisolated func webSocketConnectionStateChanged(_ state: WebSocketConnectionState) async {
        await MainActor.run {
            connectionState = state
        }
    }
}

// MARK: - Message Helpers

extension ChatViewModel {
    /// Check if a timestamp separator should be shown before a message
    func shouldShowTimestamp(for message: Message, at index: Int) -> Bool {
        // Always show for first message
        guard index > 0 else { return true }

        let previousMessage = messages[index - 1]
        return message.hasTimeGap(from: previousMessage)
    }

    /// Get messages with their timestamp visibility computed
    var messagesWithTimestamps: [(message: Message, showTimestamp: Bool)] {
        messages.enumerated().map { index, message in
            (message, shouldShowTimestamp(for: message, at: index))
        }
    }
}
