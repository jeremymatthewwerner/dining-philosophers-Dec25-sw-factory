// TypingIndicatorView.swift
// Animated typing indicator for thinkers
//
// Created by iOS Native Agent

import SwiftUI

/// Animated typing indicator showing a thinker is composing
struct TypingIndicatorView: View {
    let thinkerName: String

    @State private var animationOffset = 0

    var body: some View {
        HStack(spacing: 8) {
            // Thinker name
            Text(thinkerName)
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)

            Text("is thinking")
                .font(.caption)
                .foregroundStyle(.secondary)
                .italic()

            // Animated dots
            HStack(spacing: 4) {
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .fill(Color.accentColor)
                        .frame(width: 6, height: 6)
                        .scaleEffect(animationOffset == index ? 1.2 : 0.8)
                        .opacity(animationOffset == index ? 1 : 0.5)
                }
            }

            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(.regularMaterial)
        .onAppear {
            startAnimation()
        }
    }

    private func startAnimation() {
        Timer.scheduledTimer(withTimeInterval: 0.4, repeats: true) { _ in
            withAnimation(.easeInOut(duration: 0.2)) {
                animationOffset = (animationOffset + 1) % 3
            }
        }
    }
}

/// Compact typing bubble that looks like a message bubble
struct TypingBubbleView: View {
    let thinkerName: String

    @State private var dotSizes: [CGFloat] = [0.8, 0.8, 0.8]

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(thinkerName)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)

                HStack(spacing: 6) {
                    ForEach(0..<3, id: \.self) { index in
                        Circle()
                            .fill(Color.secondary)
                            .frame(width: 8, height: 8)
                            .scaleEffect(dotSizes[index])
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(Color(.systemGray5))
                .clipShape(RoundedRectangle(cornerRadius: 16))
            }

            Spacer()
        }
        .onAppear {
            startBubbleAnimation()
        }
    }

    private func startBubbleAnimation() {
        animateDot(at: 0)
    }

    private func animateDot(at index: Int) {
        withAnimation(.easeInOut(duration: 0.3)) {
            dotSizes[index] = 1.2
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            withAnimation(.easeInOut(duration: 0.3)) {
                dotSizes[index] = 0.8
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            let nextIndex = (index + 1) % 3
            animateDot(at: nextIndex)
        }
    }
}

// MARK: - Preview

#Preview("Typing Indicator") {
    VStack {
        TypingIndicatorView(thinkerName: "Socrates")
        Divider()
        TypingBubbleView(thinkerName: "Aristotle")
            .padding()
    }
}
