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
    case updateProfile
    case changePassword
    case updateLanguage

    // Sessions
    case sessions
    case session(id: String)

    // Conversations
    case conversations
    case conversation(id: String)
    case createConversation
    case addThinkersToConversation(conversationId: String)

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
        case .updateProfile:
            return "/api/auth/profile"
        case .changePassword:
            return "/api/auth/password"
        case .updateLanguage:
            return "/api/auth/language"

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
        case .addThinkersToConversation(let conversationId):
            return "/api/conversations/\(conversationId)/thinkers"

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

    /// Update profile request
    struct UpdateProfile: Encodable {
        let displayName: String

        enum CodingKeys: String, CodingKey {
            case displayName = "display_name"
        }
    }

    /// Change password request
    struct ChangePassword: Encodable {
        let currentPassword: String
        let newPassword: String

        enum CodingKeys: String, CodingKey {
            case currentPassword = "current_password"
            case newPassword = "new_password"
        }
    }

    /// Update language preference request
    struct UpdateLanguage: Encodable {
        let languagePreference: String

        enum CodingKeys: String, CodingKey {
            case languagePreference = "language_preference"
        }
    }
}

/// Model for creating a thinker (request body)
struct ThinkerCreate: Codable, Sendable {
    let name: String
    let bio: String
    let positions: String
    let style: String
    let color: String
    let imageUrl: String?

    init(name: String, bio: String, positions: String, style: String, color: String = "#6366f1", imageUrl: String? = nil) {
        self.name = name
        self.bio = bio
        self.positions = positions
        self.style = style
        self.color = color
        self.imageUrl = imageUrl
    }

    /// Create from an existing Thinker
    init(from thinker: Thinker) {
        self.name = thinker.name
        self.bio = thinker.bio
        self.positions = thinker.positions
        self.style = thinker.style
        self.color = thinker.color
        self.imageUrl = thinker.imageUrl
    }

    /// Create from a ThinkerSuggestion
    init(from suggestion: ThinkerSuggestion) {
        self.name = suggestion.profile.name
        self.bio = suggestion.profile.bio
        self.positions = suggestion.profile.positions
        self.style = suggestion.profile.style
        self.color = "#6366f1"
        self.imageUrl = suggestion.profile.imageUrl
    }

    enum CodingKeys: String, CodingKey {
        case name, bio, positions, style, color
        case imageUrl = "image_url"
    }
}
