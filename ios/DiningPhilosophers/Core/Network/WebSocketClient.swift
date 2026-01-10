// WebSocketClient.swift
// WebSocket client for real-time chat with reconnection support
//
// Created by iOS Native Agent
// Updated by iOS Native Agent - Phase 2

import Foundation

/// WebSocket client for real-time conversation updates with automatic reconnection
actor WebSocketClient {
    // MARK: - Properties

    private var webSocket: URLSessionWebSocketTask?
    private var conversationId: String?
    private var receiveTask: Task<Void, Never>?
    private var pingTask: Task<Void, Never>?

    private let baseURL = "wss://api.diningphilosophers.ai"
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    /// Delegate for receiving messages (main actor isolated)
    weak var delegate: WebSocketDelegate?

    // MARK: - Connection State

    /// Current connection state
    private(set) var state: ConnectionState = .disconnected

    /// Connection state enum
    enum ConnectionState: Equatable, Sendable {
        case disconnected
        case connecting
        case connected
        case reconnecting(attempt: Int)
        case failed(WebSocketError)

        static func == (lhs: ConnectionState, rhs: ConnectionState) -> Bool {
            switch (lhs, rhs) {
            case (.disconnected, .disconnected),
                 (.connecting, .connecting),
                 (.connected, .connected):
                return true
            case (.reconnecting(let lhsAttempt), .reconnecting(let rhsAttempt)):
                return lhsAttempt == rhsAttempt
            case (.failed(let lhsError), .failed(let rhsError)):
                return lhsError.localizedDescription == rhsError.localizedDescription
            default:
                return false
            }
        }

        var isConnected: Bool {
            if case .connected = self { return true }
            return false
        }
    }

    // MARK: - Reconnection Configuration

    /// Configuration for automatic reconnection
    struct ReconnectionConfig: Sendable {
        let maxAttempts: Int
        let baseDelay: TimeInterval
        let maxDelay: TimeInterval
        let backoffMultiplier: Double

        /// Default configuration with exponential backoff
        static let `default` = ReconnectionConfig(
            maxAttempts: 5,
            baseDelay: 1.0,
            maxDelay: 30.0,
            backoffMultiplier: 2.0
        )

        /// No reconnection
        static let none = ReconnectionConfig(
            maxAttempts: 0,
            baseDelay: 0,
            maxDelay: 0,
            backoffMultiplier: 0
        )

        /// Calculate delay for a given attempt number
        func delay(for attempt: Int) -> TimeInterval {
            let delay = baseDelay * pow(backoffMultiplier, Double(attempt - 1))
            return min(delay, maxDelay)
        }
    }

    private var reconnectionConfig: ReconnectionConfig = .default
    private var reconnectAttempt = 0
    private var shouldReconnect = true

    // MARK: - Ping/Pong Configuration

    private let pingInterval: TimeInterval = 30.0
    private var lastPongTime: Date?

    // MARK: - Initialization

    init() {
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    // MARK: - Connection Management

    /// Connect to a conversation's WebSocket
    func connect(conversationId: String, config: ReconnectionConfig = .default) async throws {
        // Store config
        self.reconnectionConfig = config
        self.shouldReconnect = true
        self.reconnectAttempt = 0

        try await performConnect(conversationId: conversationId)
    }

    private func performConnect(conversationId: String) async throws {
        // Disconnect any existing connection
        await disconnectInternal(reason: .goingAway, notifyDelegate: false)

        state = .connecting

        guard let url = URL(string: "\(baseURL)/ws/\(conversationId)") else {
            state = .failed(.invalidURL)
            throw WebSocketError.invalidURL
        }

        var request = URLRequest(url: url)
        request.timeoutInterval = 15.0

        // Add auth token
        if let token = await KeychainService.shared.getToken() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let session = URLSession.shared
        webSocket = session.webSocketTask(with: request)
        webSocket?.resume()

        self.conversationId = conversationId
        state = .connected
        reconnectAttempt = 0

        // Send join message
        try await send(.join(conversationId: conversationId))

        // Start receiving messages
        startReceiving()

        // Start ping task for keep-alive
        startPingTask()

        // Notify delegate
        await delegate?.webSocketDidConnect()
    }

    /// Disconnect from WebSocket
    func disconnect() async {
        shouldReconnect = false
        await disconnectInternal(reason: .normalClosure, notifyDelegate: true)
    }

    private func disconnectInternal(reason: URLSessionWebSocketTask.CloseCode, notifyDelegate: Bool) async {
        // Cancel tasks
        receiveTask?.cancel()
        receiveTask = nil
        pingTask?.cancel()
        pingTask = nil

        // Close WebSocket
        webSocket?.cancel(with: reason, reason: nil)
        webSocket = nil

        let wasConnected = state.isConnected
        state = .disconnected
        conversationId = nil

        if notifyDelegate && wasConnected {
            await delegate?.webSocketDidDisconnect(error: nil)
        }
    }

    // MARK: - Reconnection

    private func attemptReconnect() async {
        guard shouldReconnect,
              let conversationId = conversationId,
              reconnectAttempt < reconnectionConfig.maxAttempts else {
            state = .failed(.connectionFailed)
            await delegate?.webSocketDidDisconnect(error: WebSocketError.connectionFailed)
            return
        }

        reconnectAttempt += 1
        state = .reconnecting(attempt: reconnectAttempt)

        // Calculate delay with exponential backoff
        let delay = reconnectionConfig.delay(for: reconnectAttempt)

        // Notify delegate about reconnection attempt
        await delegate?.webSocketWillReconnect(attempt: reconnectAttempt, delay: delay)

        // Wait before reconnecting
        try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))

        // Check if we should still reconnect
        guard shouldReconnect else { return }

        do {
            try await performConnect(conversationId: conversationId)
        } catch {
            // Continue reconnection attempts
            await attemptReconnect()
        }
    }

    // MARK: - Sending Messages

    /// Send a message through the WebSocket
    func send(_ message: WSMessage) async throws {
        guard let webSocket, state.isConnected else {
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

    private func startReceiving() {
        receiveTask = Task { [weak self] in
            await self?.receiveLoop()
        }
    }

    private func receiveLoop() async {
        guard let webSocket else { return }

        do {
            while state.isConnected {
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
            }
        } catch {
            // Connection closed or error
            if state.isConnected {
                await handleConnectionError(error)
            }
        }
    }

    private func handleConnectionError(_ error: Error) async {
        state = .disconnected

        if shouldReconnect {
            await attemptReconnect()
        } else {
            await delegate?.webSocketDidDisconnect(error: error)
        }
    }

    private func handleData(_ data: Data) async {
        do {
            let message = try decoder.decode(WSMessage.self, from: data)
            await handleMessage(message)
        } catch {
            // Log decoding error but don't crash
            #if DEBUG
            // swiftlint:disable:next no_print_in_production
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

    // MARK: - Ping/Pong for Keep-Alive

    private func startPingTask() {
        pingTask = Task { [weak self] in
            await self?.pingLoop()
        }
    }

    private func pingLoop() async {
        while state.isConnected {
            do {
                try await Task.sleep(nanoseconds: UInt64(pingInterval * 1_000_000_000))

                guard state.isConnected, let webSocket else { break }

                try await webSocket.sendPing { [weak self] error in
                    Task { [weak self] in
                        if let error {
                            await self?.handlePingError(error)
                        } else {
                            await self?.handlePongReceived()
                        }
                    }
                }
            } catch {
                break
            }
        }
    }

    private func handlePongReceived() {
        lastPongTime = Date()
    }

    private func handlePingError(_ error: Error) async {
        // Ping failed, connection might be dead
        if state.isConnected {
            await handleConnectionError(error)
        }
    }
}

// MARK: - WebSocket Delegate Protocol

/// WebSocket delegate protocol for receiving events
@MainActor
protocol WebSocketDelegate: AnyObject {
    /// Called when WebSocket successfully connects
    func webSocketDidConnect()

    /// Called when a new message is received
    func webSocketDidReceiveMessage(_ message: WSMessage)

    /// Called when a thinker starts typing
    func webSocketThinkerTyping(name: String)

    /// Called when a thinker stops typing
    func webSocketThinkerStoppedTyping(name: String)

    /// Called when conversation is paused
    func webSocketConversationPaused()

    /// Called when conversation is resumed
    func webSocketConversationResumed()

    /// Called when conversation speed changes
    func webSocketSpeedChanged(_ speed: Double)

    /// Called when an error message is received
    func webSocketDidReceiveError(_ error: String)

    /// Called when WebSocket disconnects
    func webSocketDidDisconnect(error: Error?)

    /// Called before attempting to reconnect
    func webSocketWillReconnect(attempt: Int, delay: TimeInterval)
}

// Default implementations for optional delegate methods
extension WebSocketDelegate {
    func webSocketDidConnect() {}
    func webSocketWillReconnect(attempt: Int, delay: TimeInterval) {}
}

// MARK: - WebSocket Errors

/// WebSocket errors
enum WebSocketError: Error, LocalizedError, Equatable {
    case invalidURL
    case notConnected
    case connectionFailed
    case sendFailed(Error)
    case encodingFailed

    static func == (lhs: WebSocketError, rhs: WebSocketError) -> Bool {
        switch (lhs, rhs) {
        case (.invalidURL, .invalidURL),
             (.notConnected, .notConnected),
             (.connectionFailed, .connectionFailed),
             (.encodingFailed, .encodingFailed):
            return true
        case (.sendFailed(let lhsErr), .sendFailed(let rhsErr)):
            return lhsErr.localizedDescription == rhsErr.localizedDescription
        default:
            return false
        }
    }

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid WebSocket URL"
        case .notConnected:
            return "Not connected to conversation"
        case .connectionFailed:
            return "Failed to connect to server"
        case .sendFailed(let error):
            return "Failed to send message: \(error.localizedDescription)"
        case .encodingFailed:
            return "Failed to encode message"
        }
    }

    /// Whether this error is recoverable through reconnection
    var isRecoverable: Bool {
        switch self {
        case .connectionFailed:
            return true
        default:
            return false
        }
    }
}

// MARK: - WSMessage Extensions

extension WSMessage {
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
