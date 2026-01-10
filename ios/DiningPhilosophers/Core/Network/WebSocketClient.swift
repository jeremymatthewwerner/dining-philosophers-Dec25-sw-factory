// WebSocketClient.swift
// WebSocket client for real-time chat
//
// Created by iOS Native Agent

import Foundation

/// WebSocket client for real-time conversation updates with automatic reconnection
actor WebSocketClient {
    private var webSocket: URLSessionWebSocketTask?
    private var isConnected = false
    private var conversationId: String?
    private var shouldReconnect = false
    private var reconnectAttempts = 0
    private var reconnectTask: Task<Void, Never>?

    private let baseURL = "wss://api.diningphilosophers.ai"
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    /// Maximum reconnection attempts before giving up
    private let maxReconnectAttempts = 5

    /// Base delay for exponential backoff (in seconds)
    private let baseReconnectDelay: TimeInterval = 1.0

    /// Delegate for receiving messages
    weak var delegate: WebSocketDelegate?

    // MARK: - Connection Management

    /// Connect to a conversation's WebSocket
    func connect(conversationId: String) async throws {
        // Disconnect any existing connection
        await disconnect()

        guard let url = URL(string: "\(baseURL)/ws/\(conversationId)") else {
            throw WebSocketError.invalidURL
        }

        var request = URLRequest(url: url)

        // Add auth token
        if let token = await KeychainService.shared.getToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let session = URLSession.shared
        webSocket = session.webSocketTask(with: request)
        webSocket?.resume()

        self.conversationId = conversationId
        self.isConnected = true
        self.shouldReconnect = true
        self.reconnectAttempts = 0

        // Send join message
        try await send(.join(conversationId: conversationId))

        // Start receiving messages
        await receiveMessages()
    }

    /// Disconnect from WebSocket (user-initiated, no reconnection)
    func disconnect() async {
        shouldReconnect = false
        reconnectTask?.cancel()
        reconnectTask = nil
        webSocket?.cancel(with: .normalClosure, reason: nil)
        webSocket = nil
        isConnected = false
        conversationId = nil
        reconnectAttempts = 0
    }

    /// Check if the WebSocket is currently connected
    var connected: Bool {
        isConnected
    }

    // MARK: - Reconnection Logic

    /// Attempt to reconnect with exponential backoff
    private func attemptReconnect() async {
        guard shouldReconnect,
              reconnectAttempts < maxReconnectAttempts,
              let conversationId else {
            if reconnectAttempts >= maxReconnectAttempts {
                await delegate?.webSocketDidFailToReconnect()
            }
            return
        }

        reconnectAttempts += 1

        // Calculate delay with exponential backoff: 1s, 2s, 4s, 8s, 16s
        let delay = baseReconnectDelay * pow(2.0, Double(reconnectAttempts - 1))

        await delegate?.webSocketWillReconnect(attempt: reconnectAttempts, maxAttempts: maxReconnectAttempts, delay: delay)

        // Wait before reconnecting
        try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))

        // Check if we should still reconnect
        guard shouldReconnect else { return }

        do {
            try await connect(conversationId: conversationId)
            await delegate?.webSocketDidReconnect()
        } catch {
            // Reconnection failed, try again
            await attemptReconnect()
        }
    }

    // MARK: - Sending Messages

    /// Send a message through the WebSocket
    func send(_ message: WSMessage) async throws {
        guard let webSocket, isConnected else {
            throw WebSocketError.notConnected
        }

        let data = try encoder.encode(message)
        try await webSocket.send(.data(data))
    }

    /// Send a user message
    func sendUserMessage(_ content: String) async throws {
        guard let conversationId else {
            throw WebSocketError.notConnected
        }

        let message = WSMessage.userMessage(conversationId: conversationId, content: content)
        try await send(message)
    }

    /// Pause the conversation
    func pause() async throws {
        guard let conversationId else {
            throw WebSocketError.notConnected
        }

        try await send(.pause(conversationId: conversationId))
    }

    /// Resume the conversation
    func resume() async throws {
        guard let conversationId else {
            throw WebSocketError.notConnected
        }

        try await send(.resume(conversationId: conversationId))
    }

    /// Set conversation speed
    func setSpeed(_ speed: Double) async throws {
        guard let conversationId else {
            throw WebSocketError.notConnected
        }

        try await send(.setSpeed(conversationId: conversationId, speed: speed))
    }

    // MARK: - Receiving Messages

    private func receiveMessages() async {
        guard let webSocket else { return }

        do {
            let message = try await webSocket.receive()

            switch message {
            case .data(let data):
                await handleData(data)
            case .string(let text):
                if let data = text.data(using: .utf8) {
                    await handleData(data)
                }
            @unknown default:
                break
            }

            // Continue receiving
            if isConnected {
                await receiveMessages()
            }
        } catch {
            // Connection closed or error
            isConnected = false
            await delegate?.webSocketDidDisconnect(error: error)

            // Attempt reconnection if it wasn't a user-initiated disconnect
            if shouldReconnect {
                reconnectTask = Task {
                    await attemptReconnect()
                }
            }
        }
    }

    private func handleData(_ data: Data) async {
        do {
            let message = try decoder.decode(WSMessage.self, from: data)
            await handleMessage(message)
        } catch {
            // Log decoding error but don't crash
            // swiftlint:disable:next no_print_in_production
            print("Failed to decode WebSocket message: \(error)")
        }
    }

    private func handleMessage(_ message: WSMessage) async {
        switch message.type {
        case .message:
            // New message from thinker
            await delegate?.webSocketDidReceiveMessage(message)

        case .thinkerTyping, .thinkerThinking:
            // Thinker started typing
            await delegate?.webSocketThinkerTyping(name: message.senderName ?? "Unknown")

        case .thinkerStoppedTyping:
            // Thinker stopped typing
            await delegate?.webSocketThinkerStoppedTyping(name: message.senderName ?? "Unknown")

        case .paused:
            await delegate?.webSocketConversationPaused()

        case .resumed:
            await delegate?.webSocketConversationResumed()

        case .speedChanged:
            if let speed = message.speedMultiplier {
                await delegate?.webSocketSpeedChanged(speed)
            }

        case .error:
            await delegate?.webSocketDidReceiveError(message.content ?? "Unknown error")

        case .userJoined, .userLeft:
            // Handle user presence if needed
            break

        default:
            break
        }
    }
}

/// WebSocket delegate protocol
@MainActor
protocol WebSocketDelegate: AnyObject {
    // Message handling
    func webSocketDidReceiveMessage(_ message: WSMessage)
    func webSocketThinkerTyping(name: String)
    func webSocketThinkerStoppedTyping(name: String)
    func webSocketConversationPaused()
    func webSocketConversationResumed()
    func webSocketSpeedChanged(_ speed: Double)
    func webSocketDidReceiveError(_ error: String)

    // Connection lifecycle
    func webSocketDidDisconnect(error: Error?)
    func webSocketWillReconnect(attempt: Int, maxAttempts: Int, delay: TimeInterval)
    func webSocketDidReconnect()
    func webSocketDidFailToReconnect()
}

// MARK: - Default Implementations

extension WebSocketDelegate {
    // Provide default empty implementations for optional methods
    func webSocketWillReconnect(attempt: Int, maxAttempts: Int, delay: TimeInterval) {}
    func webSocketDidReconnect() {}
    func webSocketDidFailToReconnect() {}
}

/// WebSocket errors
enum WebSocketError: Error, LocalizedError {
    case invalidURL
    case notConnected
    case sendFailed(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid WebSocket URL"
        case .notConnected:
            return "Not connected to conversation"
        case .sendFailed(let error):
            return "Failed to send message: \(error.localizedDescription)"
        }
    }
}
