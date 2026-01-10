// NetworkErrorTests.swift
// Tests for unified network error handling
//
// Created by iOS Native Agent

import XCTest
@testable import DiningPhilosophers

/// Tests for NetworkError
final class NetworkErrorTests: XCTestCase {

    // MARK: - Error Description Tests

    func testNoConnectionErrorDescription() {
        let error = NetworkError.noConnection
        XCTAssertEqual(error.errorDescription, "No internet connection. Please check your network settings.")
    }

    func testTimeoutErrorDescription() {
        let error = NetworkError.timeout
        XCTAssertEqual(error.errorDescription, "The request timed out. Please try again.")
    }

    func testUnauthorizedErrorDescription() {
        let error = NetworkError.unauthorized
        XCTAssertEqual(error.errorDescription, "Your session has expired. Please log in again.")
    }

    func testRateLimitedWithRetryAfter() {
        let error = NetworkError.rateLimited(retryAfter: 30)
        XCTAssertEqual(error.errorDescription, "Too many requests. Please try again in 30 seconds.")
    }

    func testRateLimitedWithoutRetryAfter() {
        let error = NetworkError.rateLimited(retryAfter: nil)
        XCTAssertEqual(error.errorDescription, "Too many requests. Please try again later.")
    }

    func testServerErrorWithMessage() {
        let error = NetworkError.serverError(statusCode: 503, message: "Service unavailable")
        XCTAssertEqual(error.errorDescription, "Service unavailable")
    }

    func testServerErrorWithoutMessage() {
        let error = NetworkError.serverError(statusCode: 500, message: nil)
        XCTAssertEqual(error.errorDescription, "Server error (500). Please try again later.")
    }

    func testValidationErrorWithMessage() {
        let error = NetworkError.validationError("Invalid email format")
        XCTAssertEqual(error.errorDescription, "Invalid email format")
    }

    func testValidationErrorWithoutMessage() {
        let error = NetworkError.validationError(nil)
        XCTAssertEqual(error.errorDescription, "Invalid data submitted.")
    }

    // MARK: - Retryable Tests

    func testRetryableErrors() {
        let retryableErrors: [NetworkError] = [
            .timeout,
            .connectionLost,
            .serverError(statusCode: 503, message: nil),
            .webSocketDisconnected,
            .rateLimited(retryAfter: 5)
        ]

        for error in retryableErrors {
            XCTAssertTrue(error.isRetryable, "\(error) should be retryable")
        }
    }

    func testNonRetryableErrors() {
        let nonRetryableErrors: [NetworkError] = [
            .unauthorized,
            .forbidden,
            .notFound,
            .validationError(nil),
            .decodingFailed(underlying: NSError(domain: "", code: 0)),
            .invalidResponse
        ]

        for error in nonRetryableErrors {
            XCTAssertFalse(error.isRetryable, "\(error) should not be retryable")
        }
    }

    // MARK: - Requires Reauth Tests

    func testRequiresReauth() {
        XCTAssertTrue(NetworkError.unauthorized.requiresReauth)
        XCTAssertFalse(NetworkError.forbidden.requiresReauth)
        XCTAssertFalse(NetworkError.serverError(statusCode: 500, message: nil).requiresReauth)
        XCTAssertFalse(NetworkError.timeout.requiresReauth)
    }

    // MARK: - Conversion Tests

    func testFromAPIErrorUnauthorized() {
        let networkError = NetworkError.from(.unauthorized)
        XCTAssertEqual(networkError.errorDescription, NetworkError.unauthorized.errorDescription)
    }

    func testFromAPIErrorServerError() {
        let networkError = NetworkError.from(.serverError(502))
        switch networkError {
        case .serverError(let code, _):
            XCTAssertEqual(code, 502)
        default:
            XCTFail("Expected serverError")
        }
    }

    func testFromWebSocketErrorNotConnected() {
        let networkError = NetworkError.from(.notConnected)
        XCTAssertEqual(networkError.errorDescription, NetworkError.webSocketDisconnected.errorDescription)
    }

    // MARK: - Recovery Suggestion Tests

    func testRecoverySuggestions() {
        XCTAssertEqual(
            NetworkError.noConnection.recoverySuggestion,
            "Make sure you're connected to the internet and try again."
        )
        XCTAssertEqual(
            NetworkError.unauthorized.recoverySuggestion,
            "Tap to log in again."
        )
        XCTAssertNil(NetworkError.forbidden.recoverySuggestion)
    }
}
