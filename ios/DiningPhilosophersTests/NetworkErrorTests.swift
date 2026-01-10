// NetworkErrorTests.swift
// Tests for NetworkError model
//
// Created by iOS Native Agent - Phase 2

import XCTest
@testable import DiningPhilosophers

/// Tests for NetworkError
final class NetworkErrorTests: XCTestCase {

    // MARK: - Error Description Tests

    func testConnectionErrorDescriptions() {
        let errors: [(NetworkError, String)] = [
            (.noConnection, "No internet connection. Please check your network settings."),
            (.timeout, "The request timed out. Please try again."),
            (.hostUnreachable, "Unable to reach the server. Please try again later."),
            (.connectionLost, "Connection was lost. Please try again.")
        ]

        for (error, expectedDescription) in errors {
            XCTAssertEqual(error.errorDescription, expectedDescription)
        }
    }

    func testHTTPErrorDescriptions() {
        XCTAssertEqual(NetworkError.unauthorized.errorDescription, "Please log in to continue.")
        XCTAssertEqual(NetworkError.forbidden.errorDescription, "You don't have permission to perform this action.")
        XCTAssertEqual(NetworkError.notFound.errorDescription, "The requested resource was not found.")
        XCTAssertEqual(NetworkError.tooManyRequests(retryAfter: nil).errorDescription,
                       "Too many requests. Please wait a moment and try again.")
    }

    func testBadRequestWithMessage() {
        let error = NetworkError.badRequest(message: "Invalid email format")
        XCTAssertEqual(error.errorDescription, "Invalid email format")
    }

    func testBadRequestWithoutMessage() {
        let error = NetworkError.badRequest(message: nil)
        XCTAssertEqual(error.errorDescription, "Invalid request. Please try again.")
    }

    func testServerErrorDescription() {
        let error = NetworkError.serverError(statusCode: 503, message: nil)
        XCTAssertEqual(error.errorDescription, "Server error (503). Please try again later.")
    }

    func testServerErrorWithMessage() {
        let error = NetworkError.serverError(statusCode: 500, message: "Database unavailable")
        XCTAssertEqual(error.errorDescription, "Database unavailable")
    }

    // MARK: - Error Code Tests

    func testErrorCodes() {
        XCTAssertEqual(NetworkError.noConnection.errorCode, "NO_CONNECTION")
        XCTAssertEqual(NetworkError.timeout.errorCode, "TIMEOUT")
        XCTAssertEqual(NetworkError.unauthorized.errorCode, "UNAUTHORIZED")
        XCTAssertEqual(NetworkError.forbidden.errorCode, "FORBIDDEN")
        XCTAssertEqual(NetworkError.notFound.errorCode, "NOT_FOUND")
        XCTAssertEqual(NetworkError.tooManyRequests(retryAfter: nil).errorCode, "TOO_MANY_REQUESTS")
        XCTAssertEqual(NetworkError.serverError(statusCode: 500, message: nil).errorCode, "SERVER_ERROR")
    }

    // MARK: - isRetryable Tests

    func testRetryableErrors() {
        XCTAssertTrue(NetworkError.noConnection.isRetryable)
        XCTAssertTrue(NetworkError.timeout.isRetryable)
        XCTAssertTrue(NetworkError.hostUnreachable.isRetryable)
        XCTAssertTrue(NetworkError.connectionLost.isRetryable)
        XCTAssertTrue(NetworkError.tooManyRequests(retryAfter: nil).isRetryable)
        XCTAssertTrue(NetworkError.serverError(statusCode: 500, message: nil).isRetryable)
        XCTAssertTrue(NetworkError.serviceUnavailable.isRetryable)
    }

    func testNonRetryableErrors() {
        XCTAssertFalse(NetworkError.unauthorized.isRetryable)
        XCTAssertFalse(NetworkError.forbidden.isRetryable)
        XCTAssertFalse(NetworkError.notFound.isRetryable)
        XCTAssertFalse(NetworkError.badRequest(message: nil).isRetryable)
        XCTAssertFalse(NetworkError.invalidResponse.isRetryable)
        XCTAssertFalse(NetworkError.invalidURL.isRetryable)
    }

    // MARK: - requiresReauth Tests

    func testRequiresReauthErrors() {
        XCTAssertTrue(NetworkError.unauthorized.requiresReauth)
        XCTAssertTrue(NetworkError.forbidden.requiresReauth)
    }

    func testDoesNotRequireReauthErrors() {
        XCTAssertFalse(NetworkError.notFound.requiresReauth)
        XCTAssertFalse(NetworkError.serverError(statusCode: 500, message: nil).requiresReauth)
        XCTAssertFalse(NetworkError.timeout.requiresReauth)
    }

    // MARK: - suggestedRetryDelay Tests

    func testSuggestedRetryDelays() {
        // Rate limited with specific retry-after
        XCTAssertEqual(NetworkError.tooManyRequests(retryAfter: 60.0).suggestedRetryDelay, 60.0)

        // Rate limited without retry-after (default 30s)
        XCTAssertEqual(NetworkError.tooManyRequests(retryAfter: nil).suggestedRetryDelay, 30.0)

        // Server errors (5s)
        XCTAssertEqual(NetworkError.serverError(statusCode: 500, message: nil).suggestedRetryDelay, 5.0)
        XCTAssertEqual(NetworkError.serviceUnavailable.suggestedRetryDelay, 5.0)

        // Connection errors (2s)
        XCTAssertEqual(NetworkError.noConnection.suggestedRetryDelay, 2.0)
        XCTAssertEqual(NetworkError.timeout.suggestedRetryDelay, 2.0)

        // Non-retryable (nil)
        XCTAssertNil(NetworkError.unauthorized.suggestedRetryDelay)
        XCTAssertNil(NetworkError.notFound.suggestedRetryDelay)
    }

    // MARK: - Factory Method Tests

    func testFromHTTPStatus() {
        XCTAssertEqual(NetworkError.fromHTTPStatus(400), .badRequest(message: nil))
        XCTAssertEqual(NetworkError.fromHTTPStatus(401), .unauthorized)
        XCTAssertEqual(NetworkError.fromHTTPStatus(403), .forbidden)
        XCTAssertEqual(NetworkError.fromHTTPStatus(404), .notFound)
        XCTAssertEqual(NetworkError.fromHTTPStatus(405), .methodNotAllowed)
        XCTAssertEqual(NetworkError.fromHTTPStatus(409), .conflict(message: nil))
        XCTAssertEqual(NetworkError.fromHTTPStatus(410), .gone)
        XCTAssertEqual(NetworkError.fromHTTPStatus(422), .unprocessableEntity(message: nil))
        XCTAssertEqual(NetworkError.fromHTTPStatus(429), .tooManyRequests(retryAfter: nil))
        XCTAssertEqual(NetworkError.fromHTTPStatus(500), .serverError(statusCode: 500, message: nil))
        XCTAssertEqual(NetworkError.fromHTTPStatus(503), .serviceUnavailable)
    }

    func testFromHTTPStatusWithMessage() {
        let error = NetworkError.fromHTTPStatus(400, message: "Invalid email")
        XCTAssertEqual(error, .badRequest(message: "Invalid email"))
    }

    func testFromURLError() {
        XCTAssertEqual(NetworkError.fromURLError(URLError(.notConnectedToInternet)), .noConnection)
        XCTAssertEqual(NetworkError.fromURLError(URLError(.timedOut)), .timeout)
        XCTAssertEqual(NetworkError.fromURLError(URLError(.cannotFindHost)), .hostUnreachable)
        XCTAssertEqual(NetworkError.fromURLError(URLError(.cancelled)), .cancelled)
        XCTAssertEqual(NetworkError.fromURLError(URLError(.secureConnectionFailed)), .sslError)
        XCTAssertEqual(NetworkError.fromURLError(URLError(.badURL)), .invalidURL)
    }

    func testFromError() {
        // NetworkError passthrough
        let networkError = NetworkError.unauthorized
        XCTAssertEqual(NetworkError.from(networkError), .unauthorized)

        // URLError conversion
        let urlError = URLError(.timedOut)
        XCTAssertEqual(NetworkError.from(urlError), .timeout)

        // Unknown error
        struct CustomError: Error {}
        let customError = CustomError()
        let converted = NetworkError.from(customError)
        if case .unknown = converted {
            // Expected
        } else {
            XCTFail("Expected .unknown error")
        }
    }

    // MARK: - Equatable Tests

    func testEquatable() {
        // Same errors
        XCTAssertEqual(NetworkError.unauthorized, NetworkError.unauthorized)
        XCTAssertEqual(NetworkError.notFound, NetworkError.notFound)

        // Errors with same associated values
        XCTAssertEqual(NetworkError.badRequest(message: "test"), NetworkError.badRequest(message: "test"))
        XCTAssertEqual(NetworkError.serverError(statusCode: 500, message: "error"),
                       NetworkError.serverError(statusCode: 500, message: "error"))

        // Different errors
        XCTAssertNotEqual(NetworkError.unauthorized, NetworkError.forbidden)
        XCTAssertNotEqual(NetworkError.badRequest(message: "a"), NetworkError.badRequest(message: "b"))
        XCTAssertNotEqual(NetworkError.serverError(statusCode: 500, message: nil),
                         NetworkError.serverError(statusCode: 503, message: nil))
    }

    // MARK: - API Error Response Parsing Tests

    func testAPIErrorResponseParsing() {
        let json = """
        {
            "detail": "User not found"
        }
        """
        let data = json.data(using: .utf8)!

        let error = NetworkError.fromHTTPResponse(statusCode: 404, data: data)
        XCTAssertEqual(error.errorDescription, "User not found")
    }

    func testAPIErrorResponseWithMessage() {
        let json = """
        {
            "message": "Invalid credentials"
        }
        """
        let data = json.data(using: .utf8)!

        let error = NetworkError.fromHTTPResponse(statusCode: 401, data: data)
        XCTAssertEqual(error.errorDescription, "Invalid credentials")
    }

    func testAPIErrorResponseWithError() {
        let json = """
        {
            "error": "Rate limit exceeded"
        }
        """
        let data = json.data(using: .utf8)!

        let error = NetworkError.fromHTTPResponse(statusCode: 429, data: data)
        XCTAssertEqual(error.errorDescription, "Rate limit exceeded")
    }

    func testAPIErrorResponseInvalidJSON() {
        let data = "Not JSON".data(using: .utf8)!

        let error = NetworkError.fromHTTPResponse(statusCode: 500, data: data)
        // Should fall back to status-based message
        XCTAssertEqual(error.errorDescription, "Not JSON")
    }

    func testAPIErrorResponseNoData() {
        let error = NetworkError.fromHTTPResponse(statusCode: 503, data: nil)
        XCTAssertEqual(error, .serviceUnavailable)
    }
}
