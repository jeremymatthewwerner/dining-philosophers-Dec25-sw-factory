// ThinkerBrowserViewModel.swift
// View model for browsing and searching thinkers
//
// Created by iOS Native Agent - Phase 6

import Foundation
import SwiftUI

/// Era category for grouping thinkers
enum ThinkerEra: String, CaseIterable, Identifiable {
    case ancient = "Ancient"
    case medieval = "Medieval"
    case renaissance = "Renaissance"
    case enlightenment = "Enlightenment"
    case modern = "Modern"
    case contemporary = "Contemporary"

    var id: String { rawValue }

    var description: String {
        switch self {
        case .ancient:
            return "Before 500 CE"
        case .medieval:
            return "500-1400 CE"
        case .renaissance:
            return "1400-1600 CE"
        case .enlightenment:
            return "1600-1800 CE"
        case .modern:
            return "1800-1950 CE"
        case .contemporary:
            return "1950-Present"
        }
    }

    var systemImage: String {
        switch self {
        case .ancient:
            return "building.columns"
        case .medieval:
            return "crown"
        case .renaissance:
            return "paintpalette"
        case .enlightenment:
            return "lightbulb"
        case .modern:
            return "gear"
        case .contemporary:
            return "globe"
        }
    }
}

/// Thinker with era categorization for display
struct CategorizedThinker: Identifiable, Sendable {
    let thinker: Thinker
    let era: ThinkerEra

    var id: String { thinker.id }
}

/// Group of thinkers by era
struct ThinkerGroup: Identifiable {
    let era: ThinkerEra
    let thinkers: [Thinker]

    var id: String { era.id }
}

/// ViewModel for thinker browser
@Observable
final class ThinkerBrowserViewModel {
    private(set) var thinkers: [Thinker] = []
    private(set) var isLoading = false
    var errorMessage: String?
    var searchText = ""

    /// Categorize a thinker by parsing their bio for era information
    private func categorize(_ thinker: Thinker) -> ThinkerEra {
        let bio = thinker.bio.lowercased()

        // Check for date patterns in bio
        if let bcMatch = bio.range(of: #"\d+\s*(bc|bce|b\.c\.)"#, options: .regularExpression) {
            let yearString = bio[bcMatch].replacingOccurrences(of: "[^0-9]", with: "", options: .regularExpression)
            if let year = Int(yearString) {
                if year > 500 {
                    return .ancient
                }
            }
            return .ancient
        }

        // Check for AD/CE dates
        if let adMatch = bio.range(of: #"\(?\d{3,4}\s*[-–]\s*\d{3,4}\s*(ad|ce|a\.d\.)?\)?"#, options: .regularExpression) {
            let dateRange = String(bio[adMatch])
            let numbers = dateRange.components(separatedBy: CharacterSet.decimalDigits.inverted)
                .compactMap { Int($0) }
                .filter { $0 > 100 && $0 < 2100 }

            if let birthYear = numbers.first {
                if birthYear < 500 {
                    return .ancient
                } else if birthYear < 1400 {
                    return .medieval
                } else if birthYear < 1600 {
                    return .renaissance
                } else if birthYear < 1800 {
                    return .enlightenment
                } else if birthYear < 1950 {
                    return .modern
                } else {
                    return .contemporary
                }
            }
        }

        // Check for century references
        if bio.contains("ancient") {
            return .ancient
        } else if bio.contains("medieval") {
            return .medieval
        } else if bio.contains("renaissance") {
            return .renaissance
        } else if bio.contains("enlightenment") {
            return .enlightenment
        }

        // Default to modern for unknown
        return .modern
    }

    /// Thinkers grouped by era
    var groupedThinkers: [ThinkerGroup] {
        let filtered = filteredThinkers
        var groups: [ThinkerEra: [Thinker]] = [:]

        for thinker in filtered {
            let era = categorize(thinker)
            groups[era, default: []].append(thinker)
        }

        return ThinkerEra.allCases.compactMap { era in
            guard let thinkers = groups[era], !thinkers.isEmpty else { return nil }
            return ThinkerGroup(era: era, thinkers: thinkers)
        }
    }

    /// Filtered thinkers based on search text
    var filteredThinkers: [Thinker] {
        guard !searchText.isEmpty else { return thinkers }
        let query = searchText.lowercased()
        return thinkers.filter { thinker in
            thinker.name.lowercased().contains(query) ||
            thinker.bio.lowercased().contains(query) ||
            thinker.positions.lowercased().contains(query)
        }
    }

    /// Load all thinkers from API
    @MainActor
    func loadThinkers() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            thinkers = try await APIClient.shared.getThinkers()
        } catch let error as NetworkError {
            errorMessage = error.userMessage
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Get AI-suggested thinkers for a topic
    @MainActor
    func getSuggestions(for topic: String, count: Int = 3) async throws -> [ThinkerSuggestion] {
        try await APIClient.shared.suggestThinkers(topic: topic, count: count)
    }

    /// Clear error message
    func clearError() {
        errorMessage = nil
    }
}
