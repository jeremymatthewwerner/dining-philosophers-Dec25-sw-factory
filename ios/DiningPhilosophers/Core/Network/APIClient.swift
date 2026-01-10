// APIClient.swift
// Network client for API calls with async/await
//
// Created by iOS Native Agent

import Foundation

/// API client for making authenticated requests to the backend
actor APIClient {
    static let shared = APIClient()

    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    private init() {
        // Use production URL - can be overridden for testing
        self.baseURL = URL(string: "https://api.diningphilosophers.ai")!
        self.session = URLSession.shared

        self.decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Public API

    /// Perform an authenticated GET request
    func get<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let request = try await buildRequest(endpoint: endpoint, method: "GET")
        return try await perform(request)
    }

    /// Perform an authenticated POST request with body
    func post<T: Decodable, B: Encodable>(_ endpoint: Endpoint, body: B) async throws -> T {
        var request = try await buildRequest(endpoint: endpoint, method: "POST")
        request.httpBody = try encoder.encode(body)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return try await perform(request)
    }

    /// Perform an authenticated POST request without body
    func post<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let request = try await buildRequest(endpoint: endpoint, method: "POST")
        return try await perform(request)
    }

    /// Perform an authenticated DELETE request
    func delete(_ endpoint: Endpoint) async throws {
        let request = try await buildRequest(endpoint: endpoint, method: "DELETE")
        let (_, response) = try await session.data(for: request)
        try validateResponse(response)
    }

    // MARK: - Private Helpers

    private func buildRequest(endpoint: Endpoint, method: String) async throws -> URLRequest {
        var request = URLRequest(url: baseURL.appending(path: endpoint.path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        // Add auth token if available and endpoint requires auth
        if endpoint.requiresAuth {
            if let token = await KeychainService.shared.getToken() {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            } else {
                throw APIError.unauthorized
            }
        }

        return request
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)

        try validateResponse(response)

        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingFailed(error)
        }
    }

    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        switch httpResponse.statusCode {
        case 200...299:
            return // Success
        case 401:
            throw APIError.unauthorized
        case 403:
            throw APIError.forbidden
        case 404:
            throw APIError.notFound
        case 422:
            throw APIError.validationError
        case 429:
            throw APIError.rateLimited
        case 500...599:
            throw APIError.serverError(httpResponse.statusCode)
        default:
            throw APIError.httpError(httpResponse.statusCode)
        }
    }
}

/// API errors
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
}
