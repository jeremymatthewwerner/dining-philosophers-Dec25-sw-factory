// ChatView.swift
// Real-time chat interface
//
// Created by iOS Native Agent

import SwiftUI

/// Chat view with real-time messaging
struct ChatView: View {
    let conversationId: String

    @State private var viewModel: ChatViewModel
    @State private var messageText = ""
    @FocusState private var isInputFocused: Bool

    init(conversationId: String) {
        self.conversationId = conversationId
        self._viewModel = State(wrappedValue: ChatViewModel(conversationId: conversationId))
    }

    var body: some View {
        VStack(spacing: 0) {
            // Messages list
            messagesSection

            // Typing indicator
            if let typingThinker = viewModel.typingThinker {
                typingIndicator(for: typingThinker)
            }

            // Input area
            inputSection
        }
        .navigationTitle(viewModel.conversation?.topic ?? "Chat")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button(viewModel.isPaused ? "Resume" : "Pause") {
                        Task {
                            await viewModel.togglePause()
                        }
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .task {
            await viewModel.connect()
        }
        .onDisappear {
            Task {
                await viewModel.disconnect()
            }
        }
    }

    // MARK: - View Components

    private var messagesSection: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(viewModel.messages) { message in
                        MessageBubble(message: message)
                            .id(message.id)
                    }
                }
                .padding()
            }
            .onChange(of: viewModel.messages.count) { _, _ in
                if let lastMessage = viewModel.messages.last {
                    withAnimation {
                        proxy.scrollTo(lastMessage.id, anchor: .bottom)
                    }
                }
            }
        }
    }

    private func typingIndicator(for name: String) -> some View {
        HStack {
            Text("\(name) is thinking...")
                .font(.caption)
                .foregroundStyle(.secondary)
                .italic()
            Spacer()
        }
        .padding(.horizontal)
        .padding(.vertical, 4)
        .background(.regularMaterial)
    }

    private var inputSection: some View {
        HStack(spacing: 12) {
            TextField("Message", text: $messageText, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...5)
                .focused($isInputFocused)

            Button {
                sendMessage()
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title2)
            }
            .disabled(messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || viewModel.isSending)
        }
        .padding()
        .background(.regularMaterial)
    }

    // MARK: - Actions

    private func sendMessage() {
        let content = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty else { return }

        messageText = ""

        Task {
            await viewModel.sendMessage(content)
        }
    }
}

/// Individual message bubble
struct MessageBubble: View {
    let message: Message

    var body: some View {
        HStack {
            if message.senderType == .user {
                Spacer()
            }

            VStack(alignment: message.senderType == .user ? .trailing : .leading, spacing: 4) {
                if message.senderType == .thinker {
                    Text(message.senderName ?? "Thinker")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundStyle(.secondary)
                }

                Text(message.content)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(bubbleBackground)
                    .foregroundStyle(bubbleForeground)
                    .clipShape(RoundedRectangle(cornerRadius: 16))
            }

            if message.senderType != .user {
                Spacer()
            }
        }
    }

    private var bubbleBackground: Color {
        switch message.senderType {
        case .user:
            return .accentColor
        case .thinker:
            return Color(.systemGray5)
        case .system:
            return Color(.systemGray6)
        }
    }

    private var bubbleForeground: Color {
        switch message.senderType {
        case .user:
            return .white
        case .thinker, .system:
            return .primary
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ChatView(conversationId: "preview-id")
    }
}
