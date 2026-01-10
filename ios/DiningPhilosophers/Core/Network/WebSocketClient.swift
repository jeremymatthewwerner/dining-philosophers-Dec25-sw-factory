// WebSocketClient.swift
// WebSocket client for real-time chat
//
// Created by iOS Native Agent

import Foundation

/// Connection state for WebSocket
enum WebSocketConnectionState: Sendable, Equatable {
    case disconnected
    case connecting
    case connected
    case reconnecting(attempt: Int)
}

/// WebSocket client for real-time conversation updates
actor WebSocketClient {
    private var webSocket: URLSessionWebSocketTask?
    private var connectionState: WebSocketConnectionState = .disconnected
    private var conversationId: String?
    private var reconnectTask: Task<Void, Never>?
    private var shouldReconnect = true

    private let baseURL = "wss://api.diningphilosophers.ai"
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    // Reconnection configuration
    private let maxReconnectAttempts = 5
    private let baseReconnectDelay: TimeInterval = 1.0

    /// Delegate for receiving messages
    weak var delegate: WebSocketDelegate?

    /// Current connection state
    var state: WebSocketConnectionState {
        connectionState
    }

    /// Whether the client is connected
    var isConnected: Bool {
        connectionState == .connected
    }

    // MARK: - Connection Management

    /// Connect to a conversation's WebSocket
    func connect(conversationId: String) async throws {
        // Disconnect any existing connection
        await disconnectInternal(shouldReconnect: false)

        shouldReconnect = true
        self.conversationId = conversationId
        connectionState = .connecting
        await delegate?.webSocketConnectionStateChanged(.connecting)

        try await performConnect(conversationId: conversationId)
    }

    /// Perform the actual connection
    private func performConnect(conversationId: String) async throws {
        guard let url = URL(string: "\(baseURL)/ws/\(conversationId)") else {
            connectionState = .disconnected
            await delegate?.webSocketConnectionStateChanged(.disconnected)
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

        // Send join message
        try await send(.join(conversationId: conversationId))

        connectionState = .connected
        await delegate?.webSocketConnectionStateChanged(.connected)

        // Start receiving messages
        await receiveMessages()
    }

    /// Disconnect from WebSocket
    func disconnect() async {
        await disconnectInternal(shouldReconnect: false)
    }

    /// Internal disconnect with reconnect control
    private func disconnectInternal(shouldReconnect: Bool) async {
        self.shouldReconnect = shouldReconnect
        reconnectTask?.cancel()
        reconnectTask = nil
        webSocket?.cancel(with: .normalClosure, reason: nil)
        webSocket = nil
        connectionState = .disconnected
        await delegate?.webSocketConnectionStateChanged(.disconnected)
    }

    /// Attempt to reconnect with exponential backoff
    private func attemptReconnect() async {
        guard shouldReconnect, let conversationId else { return }

        for attempt in 1...maxReconnectAttempts {
            connectionState = .reconnecting(attempt: attempt)
            await delegate?.webSocketConnectionStateChanged(.reconnecting(attempt: attempt))

            // Exponential backoff: 1s, 2s, 4s, 8s, 16s
            let delay = baseReconnectDelay * pow(2.0, Double(attempt - 1))
            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))

            // Check if we should still reconnect
            guard shouldReconnect else { return }

            do {
                try await performConnect(conversationId: conversationId)
                return // Successfully reconnected
            } catch {
                // Continue to next attempt
                continue
            }
        }

        // All attempts failed
        connectionState = .disconnected
        await delegate?.webSocketConnectionStateChanged(.disconnected)
        await delegate?.webSocketDidDisconnect(error: WebSocketError.reconnectFailed)
    }

    // MARK: - Sending Messages

    /// Send a message through the WebSocket
    func send(_ message: WSMessage) async throws {
        guard let webSocket, connectionState == .connected else {
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
            if connectionState == .connected {
                await receiveMessages()
            }
        } catch {
            // Connection closed or error
            let wasConnected = connectionState == .connected
            connectionState = .disconnected

            if shouldReconnect && wasConnected {
                // Attempt to reconnect
                reconnectTask = Task {
                    await attemptReconnect()
                }
            } else {
                await delegate?.webSocketConnectionStateChanged(.disconnected)
                await delegate?.webSocketDidDisconnect(error: error)
            }
        }
    }

    private func handleData(_ data: Data) async {
        do {
            let message = try decoder.decode(WSMessage.self, from: data)
            await handleMessage(message)
        } catch {
            // Log decoding error but don't crash
            #if DEBUG
            print("Failed to decode WebSocket message: \(error)")
            #endif
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
    func webSocketDidReceiveMessage(_ message: WSMessage)
    func webSocketThinkerTyping(name: String)
    func webSocketThinkerStoppedTyping(name: String)
    func webSocketConversationPaused()
    func webSocketConversationResumed()
    func webSocketSpeedChanged(_ speed: Double)
    func webSocketDidReceiveError(_ error: String)
    func webSocketDidDisconnect(error: Error?)
    func webSocketConnectionStateChanged(_ state: WebSocketConnectionState)
}

/// WebSocket errors
enum WebSocketError: Error, LocalizedError {
    case invalidURL
    case notConnected
    case sendFailed(Error)
    case reconnectFailed

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid WebSocket URL"
        case .notConnected:
            return "Not connected to conversation"
        case .sendFailed(let error):
            return "Failed to send message: \(error.localizedDescription)"
        case .reconnectFailed:
            return "Failed to reconnect after multiple attempts"
        }
    }
}
