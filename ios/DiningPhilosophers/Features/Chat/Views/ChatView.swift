// ChatView.swift
// Real-time chat interface with controls
//
// Created by iOS Native Agent

import SwiftUI

/// Chat view with real-time messaging and controls
struct ChatView: View {
    let conversationId: String

    @State private var viewModel: ChatViewModel
    @State private var messageText = ""
    @State private var showingControls = false
    @FocusState private var isInputFocused: Bool

    init(conversationId: String) {
        self.conversationId = conversationId
        self._viewModel = State(wrappedValue: ChatViewModel(conversationId: conversationId))
    }

    var body: some View {
        VStack(spacing: 0) {
            // Controls section (collapsible)
            ChatControlsView(
                speed: $viewModel.speedMultiplier,
                isPaused: .init(
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

            // Messages list
            messagesSection

            // Typing indicator
            if let typingThinker = viewModel.typingThinker {
                TypingBubbleView(thinkerName: typingThinker)
                    .padding(.horizontal)
                    .transition(.asymmetric(
                        insertion: .move(edge: .bottom).combined(with: .opacity),
                        removal: .opacity
                    ))
            }

            // Input area
            inputSection
        }
        .navigationTitle(viewModel.conversation?.topic ?? "Chat")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button {
                        Task {
                            await viewModel.togglePause()
                        }
                    } label: {
                        Label(
                            viewModel.isPaused ? "Resume" : "Pause",
                            systemImage: viewModel.isPaused ? "play.fill" : "pause.fill"
                        )
                    }

                    Divider()

                    Text("Speed: \(String(format: "%.1f", viewModel.speedMultiplier))x")
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
        .alert("Error", isPresented: .init(
            get: { viewModel.errorMessage != nil },
            set: { if !$0 { viewModel.clearError() } }
        )) {
            Button("Retry") {
                Task {
                    await viewModel.connect()
                }
            }
            Button("OK", role: .cancel) {
                viewModel.clearError()
            }
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
        .overlay {
            if viewModel.isLoading {
                ProgressView("Loading conversation...")
                    .padding()
                    .background(.regularMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
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

    private var inputSection: some View {
        HStack(spacing: 12) {
            TextField("Message", text: $messageText, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...5)
                .focused($isInputFocused)
                .disabled(viewModel.isPaused)

            Button {
                sendMessage()
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.title2)
            }
            .disabled(
                messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                viewModel.isSending ||
                viewModel.isPaused
            )
        }
        .padding()
        .background(.regularMaterial)
        .overlay(alignment: .top) {
            if viewModel.isPaused {
                Text("Conversation paused")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 4)
                    .padding(.horizontal, 12)
                    .background(.regularMaterial)
                    .clipShape(Capsule())
                    .offset(y: -20)
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

                if let cost = message.cost {
                    Text("$\(cost, format: .number.precision(.fractionLength(4)))")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }

            if message.senderType != .user {
                Spacer()
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
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

    private var accessibilityLabel: String {
        let sender: String
        switch message.senderType {
        case .user:
            sender = "You said"
        case .thinker:
            sender = "\(message.senderName ?? "Thinker") said"
        case .system:
            sender = "System message"
        }
        return "\(sender): \(message.content)"
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ChatView(conversationId: "preview-id")
    }
}
