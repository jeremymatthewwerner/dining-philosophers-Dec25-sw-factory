// APIClient+Thinkers.swift
// Thinker API methods
//
// Created by iOS Native Agent

import Foundation

// MARK: - Thinker Methods

extension APIClient {
    /// Fetch all available thinkers
    /// - Returns: Array of ThinkerProfile
    func getThinkers() async throws -> [ThinkerProfile] {
        try await get(.thinkers)
    }

    /// Get thinker suggestions based on a topic
    /// - Parameters:
    ///   - topic: The conversation topic
    ///   - count: Number of suggestions (default: 3)
    /// - Returns: Array of ThinkerSuggestion
    func suggestThinkers(topic: String, count: Int = 3) async throws -> [ThinkerSuggestion] {
        // Build URL with query parameters
        var components = URLComponents()
        components.queryItems = [
            URLQueryItem(name: "topic", value: topic),
            URLQueryItem(name: "count", value: String(count))
        ]

        let request = APIRequest.SuggestThinkers(topic: topic, count: count)
        return try await post(.suggestThinkers(topic: topic), body: request)
    }
}
