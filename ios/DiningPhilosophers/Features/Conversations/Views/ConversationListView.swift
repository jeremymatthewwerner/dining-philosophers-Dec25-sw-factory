// ConversationListView.swift
// List of user's conversations with pull-to-refresh, empty state, and swipe actions
//
// Created by iOS Native Agent

import SwiftUI

/// View displaying list of conversations
struct ConversationListView: View {
    @State private var viewModel = ConversationListViewModel()
    @State private var showingNewConversation = false

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.conversations.isEmpty {
                    loadingState
                } else if viewModel.conversations.isEmpty {
                    EmptyConversationsView(onCreateConversation: {
                        showingNewConversation = true
                    })
                } else {
                    conversationList
                }
            }
            .navigationTitle("Conversations")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingNewConversation = true
                    } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("New conversation")
                    .accessibilityHint("Start a new conversation with thinkers")
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
            .sheet(isPresented: $showingNewConversation) {
                NewConversationView(onConversationCreated: { _ in
                    showingNewConversation = false
                    Task {
                        await viewModel.loadConversations()
                    }
                })
            }
        }
    }

    // MARK: - View Components

    private var loadingState: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)
            Text("Loading conversations...")
                .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Loading conversations")
    }

    private var conversationList: some View {
        List {
            ForEach(viewModel.conversations) { conversation in
                NavigationLink(value: conversation) {
                    ConversationRowView(conversation: conversation)
                }
                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                    Button(role: .destructive) {
                        Task {
                            await viewModel.deleteConversation(conversation)
                        }
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                }
                .accessibilityLabel(conversationAccessibilityLabel(for: conversation))
                .accessibilityHint("Double tap to open conversation")
            }
        }
        .listStyle(.insetGrouped)
        .navigationDestination(for: ConversationSummary.self) { conversation in
            ChatView(conversationId: conversation.id)
        }
    }

    // MARK: - Accessibility Helpers

    private func conversationAccessibilityLabel(for conversation: ConversationSummary) -> String {
        let thinkerList = conversation.thinkerNames.joined(separator: ", ")
        let messageInfo = conversation.messageCount == 1 ? "1 message" : "\(conversation.messageCount) messages"
        return "\(conversation.displayTitle). With \(thinkerList). \(messageInfo)"
    }
}

/// Row displaying conversation summary with thinker avatars
struct ConversationRowView: View {
    let conversation: ConversationSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Title
            Text(conversation.displayTitle)
                .font(.headline)
                .lineLimit(2)

            // Thinker chips with colors
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(conversation.thinkers.prefix(4)) { thinker in
                        ThinkerChip(thinker: thinker)
                    }

                    if conversation.thinkers.count > 4 {
                        Text("+\(conversation.thinkers.count - 4)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(.secondary.opacity(0.2))
                            .clipShape(Capsule())
                    }
                }
            }

            // Footer with message count and date
            HStack {
                Label("\(conversation.messageCount)", systemImage: "bubble.left")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Spacer()

                Text(conversation.createdAt, style: .relative)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }
}

/// Chip displaying thinker name with their assigned color
struct ThinkerChip: View {
    let thinker: ThinkerListItem

    var body: some View {
        Text(thinker.name)
            .font(.caption)
            .fontWeight(.medium)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(thinkerColor.opacity(0.15))
            .foregroundStyle(thinkerColor)
            .clipShape(Capsule())
    }

    private var thinkerColor: Color {
        Color(hex: thinker.color) ?? .accentColor
    }
}

/// Empty state view for when user has no conversations
struct EmptyConversationsView: View {
    let onCreateConversation: () -> Void

    var body: some View {
        ContentUnavailableView {
            Label("No Conversations Yet", systemImage: "bubble.left.and.bubble.right")
        } description: {
            Text("Start a thought-provoking discussion with history's greatest minds")
        } actions: {
            Button {
                onCreateConversation()
            } label: {
                Label("Start a Conversation", systemImage: "plus.circle.fill")
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("No conversations yet")
        .accessibilityHint("Tap to start a new conversation with thinkers")
    }
}

/// Placeholder view for creating new conversations
/// TODO: Full implementation in Phase 5
struct NewConversationView: View {
    @Environment(\.dismiss) private var dismiss
    let onConversationCreated: (String) -> Void

    @State private var topic = ""
    @State private var isCreating = false

    var body: some View {
        NavigationStack {
            Form {
                Section("What would you like to discuss?") {
                    TextField("Enter a topic...", text: $topic, axis: .vertical)
                        .lineLimit(3...6)
                }

                Section {
                    Text("Choose thinkers to join your conversation")
                        .foregroundStyle(.secondary)
                    // TODO: Add thinker selection in Phase 5
                }
            }
            .navigationTitle("New Conversation")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") {
                        // TODO: Implement conversation creation
                    }
                    .disabled(topic.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isCreating)
                }
            }
        }
    }
}

// MARK: - Color Extension

extension Color {
    init?(hex: String) {
        var hexSanitized = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        hexSanitized = hexSanitized.replacingOccurrences(of: "#", with: "")

        var rgb: UInt64 = 0
        guard Scanner(string: hexSanitized).scanHexInt64(&rgb) else {
            return nil
        }

        let r = Double((rgb & 0xFF0000) >> 16) / 255.0
        let g = Double((rgb & 0x00FF00) >> 8) / 255.0
        let b = Double(rgb & 0x0000FF) / 255.0

        self.init(red: r, green: g, blue: b)
    }
}

// MARK: - Preview

#Preview("With Conversations") {
    ConversationListView()
}

#Preview("Empty State") {
    EmptyConversationsView(onCreateConversation: {})
}
