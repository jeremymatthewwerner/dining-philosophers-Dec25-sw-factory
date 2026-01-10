// APIClientTests.swift
// Tests for API client functionality
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Tests for APIClient
final class APIClientTests: XCTestCase {

    // MARK: - API Error Tests

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
}
