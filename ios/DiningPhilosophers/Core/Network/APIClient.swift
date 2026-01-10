// APIClient.swift
// Network client for API calls with async/await
//
// Created by iOS Native Agent
// Updated by iOS Native Agent - Phase 2

import Foundation

/// API client for making authenticated requests to the backend
actor APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    // Configuration
    private static let defaultTimeout: TimeInterval = 30.0
    private static let maxRetries = 3
    private static let retryDelay: TimeInterval = 1.0

    private init() {
        // Use production URL - can be overridden for testing
        self.baseURL = URL(string: "https://api.diningphilosophers.ai")!

        // Configure URL session with timeout
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = Self.defaultTimeout
        configuration.timeoutIntervalForResource = 60.0
        self.session = URLSession(configuration: configuration)

        self.decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
    }

    /// Initialize with a custom base URL and session (for testing)
    init(baseURL: URL, session: URLSession) {
        self.baseURL = baseURL
        self.session = session

        self.decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Auth API

    /// Login with username and password
    /// Returns AuthResponse containing access token and user info
    func login(username: String, password: String) async throws -> AuthResponse {
        let request = APIRequest.Login(username: username, password: password)
        let response: AuthResponse = try await post(.login, body: request)

        // Store token securely
        try await KeychainService.shared.storeToken(response.accessToken)

        return response
    }

    /// Register a new user
    /// Returns AuthResponse containing access token and new user info
    func register(username: String, password: String, displayName: String? = nil) async throws -> AuthResponse {
        let request = APIRequest.Register(
            username: username,
            password: password,
            displayName: displayName
        )
        let response: AuthResponse = try await post(.register, body: request)

        // Store token securely
        try await KeychainService.shared.storeToken(response.accessToken)

        return response
    }

    /// Get the current authenticated user
    func getCurrentUser() async throws -> User {
        try await get(.me)
    }

    /// Logout the current user
    func logout() async throws {
        try await post(.logout) as EmptyResponse
        try await KeychainService.shared.deleteToken()
    }

    // MARK: - Sessions API

    /// Get all sessions for the current user
    func getSessions() async throws -> [Session] {
        try await get(.sessions)
    }

    /// Get a specific session
    func getSession(id: String) async throws -> Session {
        try await get(.session(id: id))
    }

    // MARK: - Conversations API

    /// List all conversations for the current user
    func getConversations() async throws -> [ConversationSummary] {
        try await get(.conversations)
    }

    /// Get a specific conversation with full details
    func getConversation(id: String) async throws -> Conversation {
        try await get(.conversation(id: id))
    }

    /// Create a new conversation
    func createConversation(topic: String, thinkerIds: [String]) async throws -> Conversation {
        let request = APIRequest.CreateConversation(topic: topic, thinkerIds: thinkerIds)
        return try await post(.createConversation, body: request)
    }

    /// Delete a conversation
    func deleteConversation(id: String) async throws {
        try await delete(.conversation(id: id))
    }

    // MARK: - Messages API

    /// Get messages for a conversation
    func getMessages(conversationId: String) async throws -> [Message] {
        try await get(.messages(conversationId: conversationId))
    }

    /// Send a message in a conversation
    func sendMessage(conversationId: String, content: String) async throws -> Message {
        let request = APIRequest.SendMessage(content: content)
        return try await post(.sendMessage(conversationId: conversationId), body: request)
    }

    // MARK: - Thinkers API

    /// Get all available thinkers
    func getThinkers() async throws -> [Thinker] {
        try await get(.thinkers)
    }

    /// Get AI-suggested thinkers for a topic
    func suggestThinkers(topic: String, count: Int? = nil) async throws -> [ThinkerSuggestion] {
        let request = APIRequest.SuggestThinkers(topic: topic, count: count)
        return try await post(.suggestThinkers(topic: topic), body: request)
    }

    // MARK: - Generic Request Methods

    /// Perform an authenticated GET request
    func get<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let request = try await buildRequest(endpoint: endpoint, method: "GET")
        return try await performWithRetry(request)
    }

    /// Perform an authenticated POST request with body
    func post<T: Decodable, B: Encodable>(_ endpoint: Endpoint, body: B) async throws -> T {
        var request = try await buildRequest(endpoint: endpoint, method: "POST")
        do {
            request.httpBody = try encoder.encode(body)
        } catch {
            throw NetworkError.encodingFailed(error)
        }
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await performWithRetry(request)
    }

    /// Perform an authenticated POST request without body
    func post<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let request = try await buildRequest(endpoint: endpoint, method: "POST")
        return try await performWithRetry(request)
    }

    /// Perform an authenticated DELETE request
    func delete(_ endpoint: Endpoint) async throws {
        let request = try await buildRequest(endpoint: endpoint, method: "DELETE")
        let (data, response) = try await performRequest(request)
        try validateResponse(response, data: data)
    }

    // MARK: - Private Helpers

    private func buildRequest(endpoint: Endpoint, method: String) async throws -> URLRequest {
        var request = URLRequest(url: baseURL.appending(path: endpoint.path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("DiningPhilosophers-iOS/1.0", forHTTPHeaderField: "User-Agent")

        // Add auth token if available and endpoint requires auth
        if endpoint.requiresAuth {
            if let token = await KeychainService.shared.getToken() {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            } else {
                throw NetworkError.unauthorized
            }
        }

        return request
    }

    private func performWithRetry<T: Decodable>(_ request: URLRequest, attempt: Int = 1) async throws -> T {
        do {
            return try await perform(request)
        } catch let error as NetworkError where error.isRetryable && attempt < Self.maxRetries {
            // Wait before retrying with exponential backoff
            let delay = Self.retryDelay * pow(2.0, Double(attempt - 1))
            try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            return try await performWithRetry(request, attempt: attempt + 1)
        } catch {
            throw error
        }
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await performRequest(request)
        try validateResponse(response, data: data)

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw NetworkError.decodingFailed(error)
        }
    }

    private func performRequest(_ request: URLRequest) async throws -> (Data, URLResponse) {
        do {
            return try await session.data(for: request)
        } catch let error as URLError {
            throw NetworkError.fromURLError(error)
        } catch {
            throw NetworkError.unknown(error)
        }
    }

    private func validateResponse(_ response: URLResponse, data: Data?) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return // Success
        default:
            throw NetworkError.fromHTTPResponse(
                statusCode: httpResponse.statusCode,
                data: data,
                decoder: decoder
            )
        }
    }
}

// MARK: - Legacy APIError (for backwards compatibility)

/// API errors (legacy - use NetworkError for new code)
enum APIError: Error, LocalizedError {
    case invalidResponse
    case unauthorized
    case forbidden
    case notFound
    case validationError
    case rateLimited
    case serverError(Int)
    case httpError(Int)
    case decodingFailed(Error)
    case networkError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .unauthorized:
            return "Please log in to continue"
        case .forbidden:
            return "You don't have permission to perform this action"
        case .notFound:
            return "The requested resource was not found"
        case .validationError:
            return "Invalid request data"
        case .rateLimited:
            return "Too many requests. Please try again later"
        case .serverError(let code):
            return "Server error (\(code)). Please try again later"
        case .httpError(let code):
            return "Request failed with status \(code)"
        case .decodingFailed:
            return "Failed to process server response"
        case .networkError:
            return "Network connection error"
        }
    }

    /// Convert to NetworkError
    var asNetworkError: NetworkError {
        switch self {
        case .invalidResponse:
            return .invalidResponse
        case .unauthorized:
            return .unauthorized
        case .forbidden:
            return .forbidden
        case .notFound:
            return .notFound
        case .validationError:
            return .unprocessableEntity(message: nil)
        case .rateLimited:
            return .tooManyRequests(retryAfter: nil)
        case .serverError(let code):
            return .serverError(statusCode: code, message: nil)
        case .httpError(let code):
            return .serverError(statusCode: code, message: nil)
        case .decodingFailed(let error):
            return .decodingFailed(error)
        case .networkError(let error):
            return .unknown(error)
        }
    }
}

// MARK: - Supporting Types

/// Empty response type for endpoints that return no body
struct EmptyResponse: Decodable {}

/// Thinker model for list endpoints
struct Thinker: Codable, Identifiable, Sendable, Hashable {
    let id: String
    let name: String
    let bio: String
    let positions: String
    let style: String
    let color: String
    let imageUrl: String?

    enum CodingKeys: String, CodingKey {
        case id, name, bio, positions, style, color
        case imageUrl = "image_url"
    }

    // MARK: - Hashable

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    static func == (lhs: Thinker, rhs: Thinker) -> Bool {
        lhs.id == rhs.id
    }
}
