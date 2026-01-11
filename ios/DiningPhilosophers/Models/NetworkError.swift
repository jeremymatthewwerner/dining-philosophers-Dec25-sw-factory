// NetworkError.swift
// Comprehensive network error handling for iOS app
//
// Created by iOS Native Agent - Phase 2

import Foundation

/// Comprehensive network error type for the iOS app
/// Maps HTTP status codes and network errors to user-friendly messages
enum NetworkError: Error, LocalizedError, Equatable {
    // MARK: - Connection Errors
    case noConnection
    case timeout
    case hostUnreachable
    case connectionLost

    // MARK: - HTTP Errors
    case badRequest(message: String?)
    case unauthorized
    case forbidden
    case notFound
    case methodNotAllowed
    case conflict(message: String?)
    case gone
    case unprocessableEntity(message: String?)
    case tooManyRequests(retryAfter: TimeInterval?)
    case serverError(statusCode: Int, message: String?)
    case serviceUnavailable

    // MARK: - Data Errors
    case invalidResponse
    case decodingFailed(Error)
    case encodingFailed(Error)
    case invalidURL

    // MARK: - Security Errors
    case sslError
    case certificateError

    // MARK: - General
    case unknown(Error)
    case cancelled

    // MARK: - Equatable conformance

    static func == (lhs: NetworkError, rhs: NetworkError) -> Bool {
        switch (lhs, rhs) {
        case (.noConnection, .noConnection),
             (.timeout, .timeout),
             (.hostUnreachable, .hostUnreachable),
             (.connectionLost, .connectionLost),
             (.unauthorized, .unauthorized),
             (.forbidden, .forbidden),
             (.notFound, .notFound),
             (.methodNotAllowed, .methodNotAllowed),
             (.gone, .gone),
             (.serviceUnavailable, .serviceUnavailable),
             (.invalidResponse, .invalidResponse),
             (.invalidURL, .invalidURL),
             (.sslError, .sslError),
             (.certificateError, .certificateError),
             (.cancelled, .cancelled):
            return true
        case (.badRequest(let lhsMsg), .badRequest(let rhsMsg)):
            return lhsMsg == rhsMsg
        case (.conflict(let lhsMsg), .conflict(let rhsMsg)):
            return lhsMsg == rhsMsg
        case (.unprocessableEntity(let lhsMsg), .unprocessableEntity(let rhsMsg)):
            return lhsMsg == rhsMsg
        case (.tooManyRequests(let lhsRetry), .tooManyRequests(let rhsRetry)):
            return lhsRetry == rhsRetry
        case (.serverError(let lhsCode, let lhsMsg), .serverError(let rhsCode, let rhsMsg)):
            return lhsCode == rhsCode && lhsMsg == rhsMsg
        case (.decodingFailed(let lhsErr), .decodingFailed(let rhsErr)):
            return lhsErr.localizedDescription == rhsErr.localizedDescription
        case (.encodingFailed(let lhsErr), .encodingFailed(let rhsErr)):
            return lhsErr.localizedDescription == rhsErr.localizedDescription
        case (.unknown(let lhsErr), .unknown(let rhsErr)):
            return lhsErr.localizedDescription == rhsErr.localizedDescription
        default:
            return false
        }
    }

    // MARK: - LocalizedError

    var errorDescription: String? {
        switch self {
        // Connection errors
        case .noConnection:
            return "No internet connection. Please check your network settings."
        case .timeout:
            return "The request timed out. Please try again."
        case .hostUnreachable:
            return "Unable to reach the server. Please try again later."
        case .connectionLost:
            return "Connection was lost. Please try again."

        // HTTP errors
        case .badRequest(let message):
            return message ?? "Invalid request. Please try again."
        case .unauthorized:
            return "Please log in to continue."
        case .forbidden:
            return "You don't have permission to perform this action."
        case .notFound:
            return "The requested resource was not found."
        case .methodNotAllowed:
            return "This action is not allowed."
        case .conflict(let message):
            return message ?? "A conflict occurred. Please try again."
        case .gone:
            return "This resource is no longer available."
        case .unprocessableEntity(let message):
            return message ?? "Invalid data. Please check your input."
        case .tooManyRequests:
            return "Too many requests. Please wait a moment and try again."
        case .serverError(let statusCode, let message):
            if let message = message {
                return message
            }
            return "Server error (\(statusCode)). Please try again later."
        case .serviceUnavailable:
            return "Service is temporarily unavailable. Please try again later."

        // Data errors
        case .invalidResponse:
            return "Invalid response from server."
        case .decodingFailed:
            return "Failed to process server response."
        case .encodingFailed:
            return "Failed to prepare request."
        case .invalidURL:
            return "Invalid URL."

        // Security errors
        case .sslError:
            return "Secure connection failed."
        case .certificateError:
            return "Server certificate is invalid."

        // General
        case .unknown:
            return "An unexpected error occurred."
        case .cancelled:
            return "Request was cancelled."
        }
    }

    /// Short error code for logging/analytics
    var errorCode: String {
        switch self {
        case .noConnection: return "NO_CONNECTION"
        case .timeout: return "TIMEOUT"
        case .hostUnreachable: return "HOST_UNREACHABLE"
        case .connectionLost: return "CONNECTION_LOST"
        case .badRequest: return "BAD_REQUEST"
        case .unauthorized: return "UNAUTHORIZED"
        case .forbidden: return "FORBIDDEN"
        case .notFound: return "NOT_FOUND"
        case .methodNotAllowed: return "METHOD_NOT_ALLOWED"
        case .conflict: return "CONFLICT"
        case .gone: return "GONE"
        case .unprocessableEntity: return "UNPROCESSABLE_ENTITY"
        case .tooManyRequests: return "TOO_MANY_REQUESTS"
        case .serverError: return "SERVER_ERROR"
        case .serviceUnavailable: return "SERVICE_UNAVAILABLE"
        case .invalidResponse: return "INVALID_RESPONSE"
        case .decodingFailed: return "DECODING_FAILED"
        case .encodingFailed: return "ENCODING_FAILED"
        case .invalidURL: return "INVALID_URL"
        case .sslError: return "SSL_ERROR"
        case .certificateError: return "CERTIFICATE_ERROR"
        case .unknown: return "UNKNOWN"
        case .cancelled: return "CANCELLED"
        }
    }

    /// Whether the error is retryable
    var isRetryable: Bool {
        switch self {
        case .noConnection, .timeout, .hostUnreachable, .connectionLost,
             .tooManyRequests, .serverError, .serviceUnavailable:
            return true
        default:
            return false
        }
    }

    /// Whether the error requires re-authentication
    var requiresReauth: Bool {
        switch self {
        case .unauthorized, .forbidden:
            return true
        default:
            return false
        }
    }

    /// Suggested retry delay in seconds (nil if not retryable)
    var suggestedRetryDelay: TimeInterval? {
        switch self {
        case .tooManyRequests(let retryAfter):
            return retryAfter ?? 30.0
        case .serverError, .serviceUnavailable:
            return 5.0
        case .noConnection, .timeout, .hostUnreachable, .connectionLost:
            return 2.0
        default:
            return nil
        }
    }

    /// User-friendly message for displaying to the user
    var userMessage: String {
        errorDescription ?? "An unexpected error occurred."
    }

    // MARK: - Factory Methods

    /// Create a NetworkError from an HTTP status code
    static func fromHTTPStatus(_ statusCode: Int, message: String? = nil) -> NetworkError {
        switch statusCode {
        case 400:
            return .badRequest(message: message)
        case 401:
            return .unauthorized
        case 403:
            return .forbidden
        case 404:
            return .notFound
        case 405:
            return .methodNotAllowed
        case 409:
            return .conflict(message: message)
        case 410:
            return .gone
        case 422:
            return .unprocessableEntity(message: message)
        case 429:
            return .tooManyRequests(retryAfter: nil)
        case 500...599:
            if statusCode == 503 {
                return .serviceUnavailable
            }
            return .serverError(statusCode: statusCode, message: message)
        default:
            return .serverError(statusCode: statusCode, message: message)
        }
    }

    /// Create a NetworkError from a URLError
    static func fromURLError(_ error: URLError) -> NetworkError {
        switch error.code {
        case .notConnectedToInternet, .networkConnectionLost:
            return .noConnection
        case .timedOut:
            return .timeout
        case .cannotFindHost, .cannotConnectToHost:
            return .hostUnreachable
        case .cancelled:
            return .cancelled
        case .secureConnectionFailed:
            return .sslError
        case .serverCertificateHasBadDate,
             .serverCertificateUntrusted,
             .serverCertificateHasUnknownRoot,
             .serverCertificateNotYetValid:
            return .certificateError
        case .badURL:
            return .invalidURL
        default:
            return .unknown(error)
        }
    }

    /// Create a NetworkError from any Error
    static func from(_ error: Error) -> NetworkError {
        if let networkError = error as? NetworkError {
            return networkError
        }
        if let urlError = error as? URLError {
            return fromURLError(urlError)
        }
        return .unknown(error)
    }
}

// MARK: - Error Response Parsing

/// Standard error response from the API
struct APIErrorResponse: Codable {
    let detail: String?
    let message: String?
    let error: String?

    /// Get the best available error message
    var errorMessage: String? {
        detail ?? message ?? error
    }
}

extension NetworkError {
    /// Try to parse an error message from response data
    static func fromHTTPResponse(
        statusCode: Int,
        data: Data?,
        decoder: JSONDecoder = JSONDecoder()
    ) -> NetworkError {
        var message: String?

        if let data = data {
            // Try to decode standard error response
            if let errorResponse = try? decoder.decode(APIErrorResponse.self, from: data) {
                message = errorResponse.errorMessage
            } else if let stringMessage = String(data: data, encoding: .utf8),
                      !stringMessage.isEmpty {
                // Use raw string if JSON parsing fails
                message = stringMessage
            }
        }

        return fromHTTPStatus(statusCode, message: message)
    }
}
