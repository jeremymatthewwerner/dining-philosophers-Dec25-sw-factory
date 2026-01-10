// EndpointsTests.swift
// Tests for API endpoint definitions
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Tests for Endpoint enum
final class EndpointsTests: XCTestCase {

    // MARK: - Auth Endpoint Paths

    func testLoginEndpointPath() {
        XCTAssertEqual(Endpoint.login.path, "/api/auth/login")
    }

    func testRegisterEndpointPath() {
        XCTAssertEqual(Endpoint.register.path, "/api/auth/register")
    }

    func testLogoutEndpointPath() {
        XCTAssertEqual(Endpoint.logout.path, "/api/auth/logout")
    }

    func testMeEndpointPath() {
        XCTAssertEqual(Endpoint.me.path, "/api/auth/me")
    }

    // MARK: - Session Endpoint Paths

    func testSessionsEndpointPath() {
        XCTAssertEqual(Endpoint.sessions.path, "/api/sessions")
    }

    func testSessionEndpointPath() {
        XCTAssertEqual(Endpoint.session(id: "abc123").path, "/api/sessions/abc123")
    }

    // MARK: - Conversation Endpoint Paths

    func testConversationsEndpointPath() {
        XCTAssertEqual(Endpoint.conversations.path, "/api/conversations")
    }

    func testConversationEndpointPath() {
        XCTAssertEqual(Endpoint.conversation(id: "conv-456").path, "/api/conversations/conv-456")
    }

    func testCreateConversationEndpointPath() {
        XCTAssertEqual(Endpoint.createConversation.path, "/api/conversations")
    }

    // MARK: - Thinker Endpoint Paths

    func testThinkersEndpointPath() {
        XCTAssertEqual(Endpoint.thinkers.path, "/api/thinkers")
    }

    func testSuggestThinkersEndpointPath() {
        XCTAssertEqual(Endpoint.suggestThinkers(topic: "ethics").path, "/api/thinkers/suggest")
    }

    // MARK: - Message Endpoint Paths

    func testMessagesEndpointPath() {
        XCTAssertEqual(Endpoint.messages(conversationId: "conv-789").path, "/api/conversations/conv-789/messages")
    }

    func testSendMessageEndpointPath() {
        XCTAssertEqual(Endpoint.sendMessage(conversationId: "conv-789").path, "/api/conversations/conv-789/messages")
    }

    // MARK: - Auth Requirements

    func testLoginDoesNotRequireAuth() {
        XCTAssertFalse(Endpoint.login.requiresAuth)
    }

    func testRegisterDoesNotRequireAuth() {
        XCTAssertFalse(Endpoint.register.requiresAuth)
    }

    func testAllOtherEndpointsRequireAuth() {
        let authRequiredEndpoints: [Endpoint] = [
            .logout,
            .me,
            .sessions,
            .session(id: "test"),
            .conversations,
            .conversation(id: "test"),
            .createConversation,
            .thinkers,
            .suggestThinkers(topic: "test"),
            .messages(conversationId: "test"),
            .sendMessage(conversationId: "test")
        ]

        for endpoint in authRequiredEndpoints {
            XCTAssertTrue(endpoint.requiresAuth, "\(endpoint) should require auth")
        }
    }

    // MARK: - ID Interpolation Tests

    func testSessionIdInterpolation() {
        let id = "session-uuid-12345"
        XCTAssertEqual(Endpoint.session(id: id).path, "/api/sessions/session-uuid-12345")
    }

    func testConversationIdInterpolation() {
        let id = "conv-uuid-67890"
        XCTAssertEqual(Endpoint.conversation(id: id).path, "/api/conversations/conv-uuid-67890")
        XCTAssertEqual(Endpoint.messages(conversationId: id).path, "/api/conversations/conv-uuid-67890/messages")
    }

    // MARK: - Special Characters in IDs

    func testSpecialCharactersInId() {
        // UUIDs with hyphens are common
        let uuid = "550e8400-e29b-41d4-a716-446655440000"
        XCTAssertEqual(Endpoint.conversation(id: uuid).path, "/api/conversations/550e8400-e29b-41d4-a716-446655440000")
    }
}
