// ConversationListViewModel.swift
// View model for conversation list with load, refresh, and delete operations
//
// Created by iOS Native Agent

import Foundation
import SwiftUI

/// ViewModel for conversation list
@Observable
final class ConversationListViewModel {
    private(set) var conversations: [ConversationSummary] = []
    private(set) var isLoading = false
    private(set) var isDeleting = false
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

    /// Delete a conversation
    @MainActor
    func deleteConversation(_ conversation: ConversationSummary) async {
        isDeleting = true
        errorMessage = nil
        defer { isDeleting = false }

        do {
            try await APIClient.shared.delete(.conversation(id: conversation.id))
            // Remove from local list with animation
            withAnimation {
                conversations.removeAll { $0.id == conversation.id }
            }
        } catch let error as APIError {
            errorMessage = "Failed to delete: \(error.localizedDescription)"
        } catch {
            errorMessage = "Failed to delete: \(error.localizedDescription)"
        }
    }

    /// Clear error message
    func clearError() {
        errorMessage = nil
    }
}
