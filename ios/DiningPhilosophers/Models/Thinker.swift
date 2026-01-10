// Thinker.swift
// Thinker models matching backend Pydantic schemas
//
// Created by iOS Native Agent

import Foundation

/// Thinker profile - matches backend/app/schemas/thinker.py
struct ThinkerProfile: Codable, Sendable {
    let name: String
    let bio: String
    let positions: String
    let style: String
    let imageUrl: String?

    enum CodingKeys: String, CodingKey {
        case name
        case bio
        case positions
        case style
        case imageUrl = "image_url"
    }
}

/// Thinker suggestion returned by AI
struct ThinkerSuggestion: Codable, Sendable {
    let name: String
    let reason: String
    let profile: ThinkerProfile
}
