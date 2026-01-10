// ConversationListView.swift
// List of user's conversations
//
// Created by iOS Native Agent

import SwiftUI

/// View displaying list of conversations
struct ConversationListView: View {
    @State private var viewModel = ConversationListViewModel()

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.conversations.isEmpty {
                    ProgressView("Loading conversations...")
                } else if viewModel.conversations.isEmpty {
                    emptyState
                } else {
                    conversationList
                }
            }
            .navigationTitle("Conversations")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        // TODO: Navigate to new conversation
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .refreshable {
                await viewModel.loadConversations()
            }
            .task {
                await viewModel.loadConversations()
            }
            .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
                Button("Retry") {
                    Task {
                        await viewModel.loadConversations()
                    }
                }
                Button("OK", role: .cancel) {
                    viewModel.clearError()
                }
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
        }
    }

    // MARK: - View Components

    private var emptyState: some View {
        ContentUnavailableView {
            Label("No Conversations", systemImage: "bubble.left.and.bubble.right")
        } description: {
            Text("Start a new conversation with history's greatest thinkers")
        } actions: {
            Button("New Conversation") {
                // TODO: Navigate to new conversation
            }
            .buttonStyle(.borderedProminent)
        }
    }

    private var conversationList: some View {
        List(viewModel.conversations) { conversation in
            NavigationLink(value: conversation) {
                ConversationRow(conversation: conversation)
            }
        }
        .listStyle(.insetGrouped)
        .navigationDestination(for: ConversationSummary.self) { conversation in
            ChatView(conversationId: conversation.id)
        }
    }
}

/// Row displaying conversation summary
struct ConversationRow: View {
    let conversation: ConversationSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(conversation.topic)
                .font(.headline)
                .lineLimit(2)

            HStack {
                // Thinker avatars/names
                ForEach(conversation.thinkers.prefix(3), id: \.name) { thinker in
                    Text(thinker.name)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(.secondary.opacity(0.2))
                        .clipShape(Capsule())
                }

                if conversation.thinkers.count > 3 {
                    Text("+\(conversation.thinkers.count - 3)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            HStack {
                Label("\(conversation.messageCount)", systemImage: "bubble.left")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Spacer()

                Text(conversation.updatedAt, style: .relative)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Preview

#Preview {
    ConversationListView()
}
