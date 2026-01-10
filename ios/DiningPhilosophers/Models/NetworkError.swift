// NetworkError.swift
// Unified network error handling
//
// Created by iOS Native Agent

import Foundation

/// Unified network error type combining API and WebSocket errors
enum NetworkError: Error, LocalizedError, Sendable {
    // MARK: - Connection Errors
    case noConnection
    case timeout
    case connectionLost

    // MARK: - API Errors
    case unauthorized
    case forbidden
    case notFound
    case validationError(String?)
    case rateLimited(retryAfter: TimeInterval?)
    case serverError(statusCode: Int, message: String?)

    // MARK: - WebSocket Errors
    case webSocketDisconnected
    case webSocketReconnectFailed

    // MARK: - Data Errors
    case decodingFailed(underlying: Error)
    case encodingFailed(underlying: Error)
    case invalidResponse

    // MARK: - Unknown
    case unknown(underlying: Error?)

    // MARK: - LocalizedError

    var errorDescription: String? {
        switch self {
        case .noConnection:
            return "No internet connection. Please check your network settings."
        case .timeout:
            return "The request timed out. Please try again."
        case .connectionLost:
            return "Connection was lost. Please try again."
        case .unauthorized:
            return "Your session has expired. Please log in again."
        case .forbidden:
            return "You don't have permission to perform this action."
        case .notFound:
            return "The requested resource was not found."
        case .validationError(let message):
            return message ?? "Invalid data submitted."
        case .rateLimited(let retryAfter):
            if let delay = retryAfter {
                return "Too many requests. Please try again in \(Int(delay)) seconds."
            }
            return "Too many requests. Please try again later."
        case .serverError(let code, let message):
            if let msg = message {
                return msg
            }
            return "Server error (\(code)). Please try again later."
        case .webSocketDisconnected:
            return "Real-time connection was lost."
        case .webSocketReconnectFailed:
            return "Could not reconnect to the conversation."
        case .decodingFailed:
            return "Failed to process server response."
        case .encodingFailed:
            return "Failed to prepare request data."
        case .invalidResponse:
            return "Received an invalid response from the server."
        case .unknown:
            return "An unexpected error occurred."
        }
    }

    var recoverySuggestion: String? {
        switch self {
        case .noConnection:
            return "Make sure you're connected to the internet and try again."
        case .timeout, .connectionLost:
            return "Check your connection and try again."
        case .unauthorized:
            return "Tap to log in again."
        case .rateLimited:
            return "Wait a moment before trying again."
        case .serverError, .unknown:
            return "If the problem persists, contact support."
        case .webSocketDisconnected, .webSocketReconnectFailed:
            return "The app will try to reconnect automatically."
        default:
            return nil
        }
    }

    /// Whether the error is recoverable by retrying
    var isRetryable: Bool {
        switch self {
        case .timeout, .connectionLost, .serverError, .webSocketDisconnected:
            return true
        case .rateLimited:
            return true
        default:
            return false
        }
    }

    /// Whether the user needs to re-authenticate
    var requiresReauth: Bool {
        switch self {
        case .unauthorized:
            return true
        default:
            return false
        }
    }

    // MARK: - Conversion from APIError

    /// Convert an APIError to NetworkError
    static func from(_ apiError: APIError) -> NetworkError {
        switch apiError {
        case .invalidResponse:
            return .invalidResponse
        case .unauthorized:
            return .unauthorized
        case .forbidden:
            return .forbidden
        case .notFound:
            return .notFound
        case .validationError:
            return .validationError(nil)
        case .rateLimited:
            return .rateLimited(retryAfter: nil)
        case .serverError(let code):
            return .serverError(statusCode: code, message: nil)
        case .httpError(let code):
            return .serverError(statusCode: code, message: nil)
        case .decodingFailed(let error):
            return .decodingFailed(underlying: error)
        case .networkError(let error):
            // Check if it's a URLError for more specific handling
            if let urlError = error as? URLError {
                switch urlError.code {
                case .notConnectedToInternet, .networkConnectionLost:
                    return .noConnection
                case .timedOut:
                    return .timeout
                default:
                    return .connectionLost
                }
            }
            return .unknown(underlying: error)
        }
    }

    // MARK: - Conversion from WebSocketError

    /// Convert a WebSocketError to NetworkError
    static func from(_ wsError: WebSocketError) -> NetworkError {
        switch wsError {
        case .invalidURL:
            return .invalidResponse
        case .notConnected:
            return .webSocketDisconnected
        case .sendFailed:
            return .webSocketDisconnected
        }
    }
}
