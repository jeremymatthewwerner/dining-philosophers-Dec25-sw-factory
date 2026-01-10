// Endpoints.swift
// Type-safe API endpoint definitions
//
// Created by iOS Native Agent

import Foundation

/// API endpoint definitions matching backend routes
enum Endpoint {
    // Auth
    case login
    case register
    case logout
    case me

    // Sessions
    case sessions
    case session(id: String)

    // Conversations
    case conversations
    case conversation(id: String)
    case createConversation

    // Thinkers
    case thinkers
    case suggestThinkers(topic: String)

    // Messages
    case messages(conversationId: String)
    case sendMessage(conversationId: String)

    /// Path for the endpoint
    var path: String {
        switch self {
        // Auth
        case .login:
            return "/api/auth/login"
        case .register:
            return "/api/auth/register"
        case .logout:
            return "/api/auth/logout"
        case .me:
            return "/api/auth/me"

        // Sessions
        case .sessions:
            return "/api/sessions"
        case .session(let id):
            return "/api/sessions/\(id)"

        // Conversations
        case .conversations:
            return "/api/conversations"
        case .conversation(let id):
            return "/api/conversations/\(id)"
        case .createConversation:
            return "/api/conversations"

        // Thinkers
        case .thinkers:
            return "/api/thinkers"
        case .suggestThinkers:
            return "/api/thinkers/suggest"

        // Messages
        case .messages(let conversationId):
            return "/api/conversations/\(conversationId)/messages"
        case .sendMessage(let conversationId):
            return "/api/conversations/\(conversationId)/messages"
        }
    }

    /// Whether this endpoint requires authentication
    var requiresAuth: Bool {
        switch self {
        case .login, .register:
            return false
        default:
            return true
        }
    }
}

/// Request bodies for API calls
enum APIRequest {
    /// Login request body
    struct Login: Encodable {
        let username: String
        let password: String
    }

    /// Register request body
    struct Register: Encodable {
        let username: String
        let password: String
        let displayName: String?

        enum CodingKeys: String, CodingKey {
            case username
            case password
            case displayName = "display_name"
        }
    }

    /// Create conversation request
    struct CreateConversation: Encodable {
        let topic: String
        let thinkerIds: [String]

        enum CodingKeys: String, CodingKey {
            case topic
            case thinkerIds = "thinker_ids"
        }
    }

    /// Send message request
    struct SendMessage: Encodable {
        let content: String
    }

    /// Suggest thinkers request
    struct SuggestThinkers: Encodable {
        let topic: String
        let count: Int?
    }
}
