// ConversationListViewModel.swift
// View model for conversation list
//
// Created by iOS Native Agent

import Foundation

/// ViewModel for conversation list
@Observable
final class ConversationListViewModel {
    private(set) var conversations: [ConversationSummary] = []
    private(set) var isLoading = false
    var errorMessage: String?

    /// Load conversations from API
    @MainActor
    func loadConversations() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            conversations = try await APIClient.shared.get(.conversations)
        } catch let error as APIError {
            errorMessage = error.localizedDescription
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Clear error message
    func clearError() {
        errorMessage = nil
    }
}
