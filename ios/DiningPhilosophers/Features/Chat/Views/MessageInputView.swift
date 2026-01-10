// MessageInputView.swift
// Message input component with send button
//
// Created by iOS Native Agent

import SwiftUI

/// Message input field with send button
struct MessageInputView: View {
    @Binding var text: String
    let isSending: Bool
    let onSend: () -> Void

    @FocusState private var isFocused: Bool

    var body: some View {
        HStack(spacing: 12) {
            TextField("Message", text: $text, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...5)
                .focused($isFocused)
                .accessibilityLabel("Message input")
                .accessibilityHint("Type your message here")

            Button(action: onSend) {
                ZStack {
                    if isSending {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle())
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.title2)
                    }
                }
                .frame(width: 32, height: 32)
            }
            .disabled(isDisabled)
            .accessibilityLabel("Send message")
            .accessibilityHint(isDisabled ? "Enter a message to enable" : "Double tap to send")
        }
        .padding()
        .background(.regularMaterial)
    }

    private var isDisabled: Bool {
        text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSending
    }
}

// MARK: - Preview

#Preview {
    VStack {
        Spacer()
        MessageInputView(
            text: .constant(""),
            isSending: false,
            onSend: {}
        )
    }
}

#Preview("With Text") {
    VStack {
        Spacer()
        MessageInputView(
            text: .constant("Hello, Socrates!"),
            isSending: false,
            onSend: {}
        )
    }
}

#Preview("Sending") {
    VStack {
        Spacer()
        MessageInputView(
            text: .constant("Message being sent..."),
            isSending: true,
            onSend: {}
        )
    }
}
