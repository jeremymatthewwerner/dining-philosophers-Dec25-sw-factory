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
    @State private var scrollProxy: ScrollViewProxy?
    @FocusState private var isInputFocused: Bool

    init(conversationId: String) {
        self.conversationId = conversationId
        self._viewModel = State(wrappedValue: ChatViewModel(conversationId: conversationId))
    }

    var body: some View {
        VStack(spacing: 0) {
            // Connection status banner
            ConnectionStatusBanner(connectionState: viewModel.connectionState)
                .onTapGesture {
                    if viewModel.connectionState == .disconnected {
                        Task {
                            await viewModel.reconnect()
                        }
                    }
                }

            // Chat toolbar with speed control
            ChatToolbarView(
                speed: Binding(
                    get: { viewModel.currentSpeed },
                    set: { _ in }
                ),
                isPaused: Binding(
                    get: { viewModel.isPaused },
                    set: { _ in }
                ),
                onSpeedChange: { speed in
                    Task {
                        await viewModel.setSpeed(speed)
                    }
                },
                onTogglePause: {
                    Task {
                        await viewModel.togglePause()
                    }
                }
            )
            .background(.regularMaterial)

            // Messages list
            messagesSection

            // Typing indicator
            if let typingThinker = viewModel.typingThinker {
                TypingIndicatorView(thinkerName: typingThinker)
            }

            // Input area
            MessageInputView(
                text: $messageText,
                isSending: viewModel.isSending,
                onSend: sendMessage
            )
        }
        .navigationTitle(viewModel.conversation?.topic ?? "Chat")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                HStack(spacing: 8) {
                    ConnectionIndicator(connectionState: viewModel.connectionState)
                    Text(viewModel.conversation?.topic ?? "Chat")
                        .font(.headline)
                }
            }

            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Section("Speed") {
                        ForEach(ConversationSpeed.allCases) { speed in
                            Button {
                                Task {
                                    await viewModel.setSpeed(speed)
                                }
                            } label: {
                                HStack {
                                    Text(speed.label)
                                    if speed == viewModel.currentSpeed {
                                        Image(systemName: "checkmark")
                                    }
                                }
                            }
                        }
                    }

                    Section {
                        Button(viewModel.isPaused ? "Resume" : "Pause") {
                            Task {
                                await viewModel.togglePause()
                            }
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
        .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
            Button("OK") {
                // Clear error handled by ViewModel
            }
        } message: {
            if let error = viewModel.errorMessage {
                Text(error)
            }
        }
    }

    // MARK: - View Components

    private var messagesSection: some View {
        ZStack(alignment: .bottom) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(Array(viewModel.messages.enumerated()), id: \.element.id) { index, message in
                            MessageBubbleView(
                                message: message,
                                showTimestamp: viewModel.shouldShowTimestamp(for: message, at: index),
                                onTap: {
                                    if message.status == .failed {
                                        Task {
                                            await viewModel.retryMessage(id: message.id)
                                        }
                                    }
                                }
                            )
                            .id(message.id)
                        }
                    }
                    .padding()
                }
                .onChange(of: viewModel.messages.count) { _, _ in
                    if !viewModel.isScrolledUp, let lastMessage = viewModel.messages.last {
                        withAnimation {
                            proxy.scrollTo(lastMessage.id, anchor: .bottom)
                        }
                    }
                }
                .onAppear {
                    scrollProxy = proxy
                }
                // Detect scroll position
                .simultaneousGesture(
                    DragGesture().onChanged { value in
                        if value.translation.height > 50 {
                            viewModel.userScrolledUp()
                        }
                    }
                )
            }

            // New messages indicator
            if viewModel.newMessagesCount > 0 {
                NewMessagesIndicator(messageCount: viewModel.newMessagesCount) {
                    scrollToBottom()
                }
                .padding(.bottom, 8)
            }
        }
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

    private func scrollToBottom() {
        viewModel.userScrolledToBottom()
        if let lastMessage = viewModel.messages.last {
            withAnimation {
                scrollProxy?.scrollTo(lastMessage.id, anchor: .bottom)
            }
        }
    }
}

// MARK: - Legacy MessageBubble (kept for backwards compatibility)

/// Individual message bubble (deprecated - use MessageBubbleView instead)
@available(*, deprecated, renamed: "MessageBubbleView")
struct MessageBubble: View {
    let message: Message

    var body: some View {
        MessageBubbleView(message: message)
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ChatView(conversationId: "preview-id")
    }
}
