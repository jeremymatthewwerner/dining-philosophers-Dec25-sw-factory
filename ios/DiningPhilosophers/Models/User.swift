// User.swift
// User model matching backend Pydantic schema
//
// Created by iOS Native Agent

import Foundation

/// User model - matches backend/app/schemas/auth.py
struct User: Codable, Identifiable, Sendable, Equatable {
    let id: String
    let username: String
    let displayName: String?
    let isAdmin: Bool
    let totalSpend: Decimal
    let spendLimit: Decimal
    let languagePreference: String
    let createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case username
        case displayName = "display_name"
        case isAdmin = "is_admin"
        case totalSpend = "total_spend"
        case spendLimit = "spend_limit"
        case languagePreference = "language_preference"
        case createdAt = "created_at"
    }
}

/// Authentication response from /api/auth/login
struct AuthResponse: Codable, Sendable {
    let accessToken: String
    let user: User

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case user
    }
}

/// User with additional statistics
struct UserWithStats: Codable, Identifiable, Sendable {
    let id: String
    let username: String
    let displayName: String?
    let isAdmin: Bool
    let totalSpend: Decimal
    let spendLimit: Decimal
    let languagePreference: String
    let createdAt: Date
    let conversationCount: Int

    enum CodingKeys: String, CodingKey {
        case id
        case username
        case displayName = "display_name"
        case isAdmin = "is_admin"
        case totalSpend = "total_spend"
        case spendLimit = "spend_limit"
        case languagePreference = "language_preference"
        case createdAt = "created_at"
        case conversationCount = "conversation_count"
    }
}

/// Session model
struct Session: Codable, Identifiable, Sendable {
    let id: String
    let createdAt: Date

    enum CodingKeys: String, CodingKey {
        case id
        case createdAt = "created_at"
    }
}
