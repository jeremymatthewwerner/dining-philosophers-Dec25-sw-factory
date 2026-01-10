// APIClientTests.swift
// Tests for API client functionality
//
// Created by iOS Native Agent
// Updated by iOS Native Agent - Phase 2

import XCTest
@testable import DiningPhilosophers

/// Tests for APIClient
final class APIClientTests: XCTestCase {

    // MARK: - Legacy API Error Tests (Backwards Compatibility)

    func testAPIErrorDescriptions() {
        let errors: [(APIError, String)] = [
            (.unauthorized, "Please log in to continue"),
            (.forbidden, "You don't have permission to perform this action"),
            (.notFound, "The requested resource was not found"),
            (.validationError, "Invalid request data"),
            (.rateLimited, "Too many requests. Please try again later"),
            (.serverError(500), "Server error (500). Please try again later"),
            (.httpError(418), "Request failed with status 418"),
            (.invalidResponse, "Invalid response from server")
        ]

        for (error, expectedDescription) in errors {
            XCTAssertEqual(error.errorDescription, expectedDescription)
        }
    }

    func testAPIErrorToNetworkErrorConversion() {
        // Test conversion from legacy APIError to NetworkError
        XCTAssertEqual(APIError.invalidResponse.asNetworkError, .invalidResponse)
        XCTAssertEqual(APIError.unauthorized.asNetworkError, .unauthorized)
        XCTAssertEqual(APIError.forbidden.asNetworkError, .forbidden)
        XCTAssertEqual(APIError.notFound.asNetworkError, .notFound)
        XCTAssertEqual(APIError.validationError.asNetworkError, .unprocessableEntity(message: nil))
        XCTAssertEqual(APIError.rateLimited.asNetworkError, .tooManyRequests(retryAfter: nil))
        XCTAssertEqual(APIError.serverError(500).asNetworkError, .serverError(statusCode: 500, message: nil))
        XCTAssertEqual(APIError.httpError(418).asNetworkError, .serverError(statusCode: 418, message: nil))
    }

    // MARK: - Request Body Encoding Tests

    func testLoginRequestEncoding() throws {
        let request = APIRequest.Login(username: "testuser", password: "password123")
        let data = try JSONEncoder().encode(request)
        let decoded = try JSONDecoder().decode([String: String].self, from: data)

        XCTAssertEqual(decoded["username"], "testuser")
        XCTAssertEqual(decoded["password"], "password123")
    }

    func testRegisterRequestEncoding() throws {
        let request = APIRequest.Register(
            username: "newuser",
            password: "password123",
            displayName: "New User"
        )
        let encoder = JSONEncoder()
        let data = try encoder.encode(request)

        // Decode as dictionary to verify snake_case keys
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(json["username"] as? String, "newuser")
        XCTAssertEqual(json["password"] as? String, "password123")
        XCTAssertEqual(json["display_name"] as? String, "New User")
    }

    func testRegisterRequestWithoutDisplayName() throws {
        let request = APIRequest.Register(
            username: "newuser",
            password: "password123",
            displayName: nil
        )
        let data = try JSONEncoder().encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(json["username"] as? String, "newuser")
        XCTAssertNil(json["display_name"])
    }

    func testCreateConversationRequestEncoding() throws {
        let request = APIRequest.CreateConversation(
            topic: "Ethics and Morality",
            thinkerIds: ["thinker-1", "thinker-2"]
        )
        let data = try JSONEncoder().encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(json["topic"] as? String, "Ethics and Morality")
        XCTAssertEqual(json["thinker_ids"] as? [String], ["thinker-1", "thinker-2"])
    }

    func testSendMessageRequestEncoding() throws {
        let request = APIRequest.SendMessage(content: "What is the meaning of life?")
        let data = try JSONEncoder().encode(request)
        let decoded = try JSONDecoder().decode([String: String].self, from: data)

        XCTAssertEqual(decoded["content"], "What is the meaning of life?")
    }

    func testSuggestThinkersRequestEncoding() throws {
        let request = APIRequest.SuggestThinkers(topic: "Artificial Intelligence", count: 3)
        let data = try JSONEncoder().encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(json["topic"] as? String, "Artificial Intelligence")
        XCTAssertEqual(json["count"] as? Int, 3)
    }

    func testSuggestThinkersRequestWithoutCount() throws {
        let request = APIRequest.SuggestThinkers(topic: "Philosophy", count: nil)
        let data = try JSONEncoder().encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as! [String: Any]

        XCTAssertEqual(json["topic"] as? String, "Philosophy")
        XCTAssertNil(json["count"])
    }

    // MARK: - Auth Response Decoding Tests

    func testAuthResponseDecoding() throws {
        let json = """
        {
            "access_token": "jwt-token-here",
            "user": {
                "id": "user-123",
                "username": "testuser",
                "display_name": null,
                "is_admin": false,
                "total_spend": "0.00",
                "spend_limit": "100.00",
                "language_preference": "en",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }
        """

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        let data = json.data(using: .utf8)!
        let response = try decoder.decode(AuthResponse.self, from: data)

        XCTAssertEqual(response.accessToken, "jwt-token-here")
        XCTAssertEqual(response.user.id, "user-123")
        XCTAssertEqual(response.user.username, "testuser")
        XCTAssertNil(response.user.displayName)
    }

    // MARK: - Thinker Model Tests

    func testThinkerDecoding() throws {
        let json = """
        {
            "id": "thinker-123",
            "name": "Aristotle",
            "bio": "Ancient Greek philosopher",
            "positions": "Virtue ethics, empiricism",
            "style": "Systematic, logical",
            "color": "#4A90D9",
            "image_url": "https://example.com/aristotle.jpg"
        }
        """

        let data = json.data(using: .utf8)!
        let thinker = try JSONDecoder().decode(Thinker.self, from: data)

        XCTAssertEqual(thinker.id, "thinker-123")
        XCTAssertEqual(thinker.name, "Aristotle")
        XCTAssertEqual(thinker.bio, "Ancient Greek philosopher")
        XCTAssertEqual(thinker.positions, "Virtue ethics, empiricism")
        XCTAssertEqual(thinker.style, "Systematic, logical")
        XCTAssertEqual(thinker.color, "#4A90D9")
        XCTAssertEqual(thinker.imageUrl, "https://example.com/aristotle.jpg")
    }

    func testThinkerDecodingWithNullImageUrl() throws {
        let json = """
        {
            "id": "thinker-456",
            "name": "Socrates",
            "bio": "Classical Greek philosopher",
            "positions": "Socratic method",
            "style": "Questioning",
            "color": "#FF5733",
            "image_url": null
        }
        """

        let data = json.data(using: .utf8)!
        let thinker = try JSONDecoder().decode(Thinker.self, from: data)

        XCTAssertEqual(thinker.id, "thinker-456")
        XCTAssertEqual(thinker.name, "Socrates")
        XCTAssertNil(thinker.imageUrl)
    }

    // MARK: - EmptyResponse Tests

    func testEmptyResponseDecoding() throws {
        let json = "{}"
        let data = json.data(using: .utf8)!
        let response = try JSONDecoder().decode(EmptyResponse.self, from: data)

        // EmptyResponse should decode successfully
        _ = response
    }

    // MARK: - Endpoint Tests

    func testAllEndpointPaths() {
        // Auth endpoints
        XCTAssertEqual(Endpoint.login.path, "/api/auth/login")
        XCTAssertEqual(Endpoint.register.path, "/api/auth/register")
        XCTAssertEqual(Endpoint.logout.path, "/api/auth/logout")
        XCTAssertEqual(Endpoint.me.path, "/api/auth/me")

        // Session endpoints
        XCTAssertEqual(Endpoint.sessions.path, "/api/sessions")
        XCTAssertEqual(Endpoint.session(id: "sess-123").path, "/api/sessions/sess-123")

        // Conversation endpoints
        XCTAssertEqual(Endpoint.conversations.path, "/api/conversations")
        XCTAssertEqual(Endpoint.conversation(id: "conv-123").path, "/api/conversations/conv-123")
        XCTAssertEqual(Endpoint.createConversation.path, "/api/conversations")

        // Thinker endpoints
        XCTAssertEqual(Endpoint.thinkers.path, "/api/thinkers")
        XCTAssertEqual(Endpoint.suggestThinkers(topic: "ethics").path, "/api/thinkers/suggest")

        // Message endpoints
        XCTAssertEqual(Endpoint.messages(conversationId: "conv-123").path, "/api/conversations/conv-123/messages")
        XCTAssertEqual(Endpoint.sendMessage(conversationId: "conv-456").path, "/api/conversations/conv-456/messages")
    }

    func testEndpointAuthRequirements() {
        // Public endpoints (no auth required)
        XCTAssertFalse(Endpoint.login.requiresAuth)
        XCTAssertFalse(Endpoint.register.requiresAuth)

        // Protected endpoints (auth required)
        XCTAssertTrue(Endpoint.logout.requiresAuth)
        XCTAssertTrue(Endpoint.me.requiresAuth)
        XCTAssertTrue(Endpoint.sessions.requiresAuth)
        XCTAssertTrue(Endpoint.session(id: "123").requiresAuth)
        XCTAssertTrue(Endpoint.conversations.requiresAuth)
        XCTAssertTrue(Endpoint.conversation(id: "123").requiresAuth)
        XCTAssertTrue(Endpoint.createConversation.requiresAuth)
        XCTAssertTrue(Endpoint.thinkers.requiresAuth)
        XCTAssertTrue(Endpoint.suggestThinkers(topic: "test").requiresAuth)
        XCTAssertTrue(Endpoint.messages(conversationId: "123").requiresAuth)
        XCTAssertTrue(Endpoint.sendMessage(conversationId: "123").requiresAuth)
    }
}
