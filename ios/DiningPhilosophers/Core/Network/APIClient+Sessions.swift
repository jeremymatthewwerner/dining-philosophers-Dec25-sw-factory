// APIClient+Sessions.swift
// Session API methods
//
// Created by iOS Native Agent

import Foundation

// MARK: - Session Methods

extension APIClient {
    /// Fetch all sessions for the current user
    /// - Returns: Array of Session
    func getSessions() async throws -> [Session] {
        try await get(.sessions)
    }

    /// Get a specific session
    /// - Parameter id: The session ID
    /// - Returns: The Session
    func getSession(id: String) async throws -> Session {
        try await get(.session(id: id))
    }
}
