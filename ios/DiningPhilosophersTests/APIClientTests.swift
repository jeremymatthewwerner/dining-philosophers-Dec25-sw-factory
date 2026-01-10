// APIClientTests.swift
// Tests for the API client
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

final class APIClientTests: XCTestCase {

    // MARK: - APIError Tests

    func testAPIErrorDescriptions() {
        XCTAssertNotNil(APIError.unauthorized.errorDescription)
        XCTAssertNotNil(APIError.forbidden.errorDescription)
        XCTAssertNotNil(APIError.notFound.errorDescription)
        XCTAssertNotNil(APIError.validationError.errorDescription)
        XCTAssertNotNil(APIError.rateLimited.errorDescription)
        XCTAssertNotNil(APIError.serverError(500).errorDescription)
        XCTAssertNotNil(APIError.httpError(418).errorDescription)
        XCTAssertNotNil(APIError.invalidResponse.errorDescription)
    }

    func testServerErrorContainsStatusCode() {
        let error = APIError.serverError(503)
        XCTAssertTrue(error.errorDescription?.contains("503") ?? false)
    }

    func testHttpErrorContainsStatusCode() {
        let error = APIError.httpError(418)
        XCTAssertTrue(error.errorDescription?.contains("418") ?? false)
    }

    // MARK: - Request Body Tests

    func testLoginRequestEncoding() throws {
        let request = APIRequest.Login(username: "testuser", password: "password123")

        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertEqual(json?["username"] as? String, "testuser")
        XCTAssertEqual(json?["password"] as? String, "password123")
    }

    func testRegisterRequestEncoding() throws {
        let request = APIRequest.Register(
            username: "newuser",
            password: "password123",
            displayName: "New User"
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertEqual(json?["username"] as? String, "newuser")
        XCTAssertEqual(json?["password"] as? String, "password123")
        XCTAssertEqual(json?["display_name"] as? String, "New User")
    }

    func testRegisterRequestEncodingWithoutDisplayName() throws {
        let request = APIRequest.Register(
            username: "newuser",
            password: "password123",
            displayName: nil
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertEqual(json?["username"] as? String, "newuser")
        XCTAssertNil(json?["display_name"])
    }

    func testCreateConversationRequestEncoding() throws {
        let request = APIRequest.CreateConversation(
            topic: "Philosophy of Mind",
            thinkerIds: ["thinker1", "thinker2"]
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertEqual(json?["topic"] as? String, "Philosophy of Mind")
        XCTAssertEqual(json?["thinker_ids"] as? [String], ["thinker1", "thinker2"])
    }

    func testSendMessageRequestEncoding() throws {
        let request = APIRequest.SendMessage(content: "Hello, philosophers!")

        let encoder = JSONEncoder()
        let data = try encoder.encode(request)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertEqual(json?["content"] as? String, "Hello, philosophers!")
    }
}
