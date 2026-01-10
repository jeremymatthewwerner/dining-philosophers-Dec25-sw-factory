// MessageBubbleView.swift
// Individual message bubble component
//
// Created by iOS Native Agent

import SwiftUI

/// Individual message bubble with status and timestamp support
struct MessageBubbleView: View {
    let message: Message
    let showTimestamp: Bool
    let onTap: (() -> Void)?

    @State private var showingTimestamp = false

    init(
        message: Message,
        showTimestamp: Bool = false,
        onTap: (() -> Void)? = nil
    ) {
        self.message = message
        self.showTimestamp = showTimestamp
        self.onTap = onTap
    }

    var body: some View {
        VStack(alignment: message.senderType == .user ? .trailing : .leading, spacing: 4) {
            // Timestamp separator (shown for time gaps)
            if showTimestamp {
                timestampSeparator
            }

            // Message content
            HStack {
                if message.senderType == .user {
                    Spacer()
                }

                VStack(alignment: message.senderType == .user ? .trailing : .leading, spacing: 4) {
                    // Sender name for thinkers
                    if message.senderType == .thinker, let name = message.senderName {
                        Text(name)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundStyle(.secondary)
                    }

                    // Message bubble
                    HStack(alignment: .bottom, spacing: 4) {
                        Text(message.content)
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(bubbleBackground)
                            .foregroundStyle(bubbleForeground)
                            .clipShape(RoundedRectangle(cornerRadius: 16))

                        // Status indicator for user messages
                        if message.senderType == .user {
                            statusIndicator
                        }
                    }

                    // Inline timestamp (shown on tap)
                    if showingTimestamp && !showTimestamp {
                        Text(message.createdAt, style: .time)
                            .font(.caption2)
                            .foregroundStyle(.tertiary)
                            .transition(.opacity.combined(with: .scale(scale: 0.8)))
                    }
                }

                if message.senderType != .user {
                    Spacer()
                }
            }
        }
        .onTapGesture {
            withAnimation(.easeInOut(duration: 0.2)) {
                showingTimestamp.toggle()
            }
            onTap?()
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint("Double tap to show timestamp")
    }

    // MARK: - Subviews

    private var timestampSeparator: some View {
        HStack {
            VStack { Divider() }
            Text(message.createdAt, style: .date)
                .font(.caption2)
                .foregroundStyle(.tertiary)
            Text(message.createdAt, style: .time)
                .font(.caption2)
                .foregroundStyle(.tertiary)
            VStack { Divider() }
        }
        .padding(.vertical, 8)
    }

    @ViewBuilder
    private var statusIndicator: some View {
        switch message.status {
        case .sending:
            Image(systemName: "clock")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .accessibilityLabel("Sending")

        case .sent:
            Image(systemName: "checkmark")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .accessibilityLabel("Sent")

        case .failed:
            Image(systemName: "exclamationmark.circle")
                .font(.caption2)
                .foregroundStyle(.red)
                .accessibilityLabel("Failed to send")
        }
    }

    // MARK: - Styling

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
        var label = ""
        if let name = message.senderName {
            label = "\(name) said: "
        } else if message.senderType == .user {
            label = "You said: "
        }
        label += message.content
        return label
    }
}

// MARK: - Time Gap Calculation

extension Message {
    /// Check if this message has a significant time gap from another
    func hasTimeGap(from other: Message, threshold: TimeInterval = 300) -> Bool {
        abs(createdAt.timeIntervalSince(other.createdAt)) >= threshold
    }
}

// MARK: - Preview

#Preview("User Message") {
    VStack(spacing: 12) {
        MessageBubbleView(
            message: Message(
                id: "1",
                conversationId: "conv",
                senderType: .user,
                senderName: nil,
                content: "Hello, what is virtue?",
                cost: nil,
                createdAt: Date(),
                status: .sent
            )
        )

        MessageBubbleView(
            message: Message(
                id: "2",
                conversationId: "conv",
                senderType: .user,
                senderName: nil,
                content: "Sending...",
                cost: nil,
                createdAt: Date(),
                status: .sending
            )
        )

        MessageBubbleView(
            message: Message(
                id: "3",
                conversationId: "conv",
                senderType: .user,
                senderName: nil,
                content: "Failed message",
                cost: nil,
                createdAt: Date(),
                status: .failed
            )
        )
    }
    .padding()
}

#Preview("Thinker Message") {
    MessageBubbleView(
        message: Message(
            id: "2",
            conversationId: "conv",
            senderType: .thinker,
            senderName: "Socrates",
            content: "Ah, the eternal question! Virtue, my friend, is knowledge.",
            cost: Decimal(0.01),
            createdAt: Date()
        ),
        showTimestamp: true
    )
    .padding()
}
