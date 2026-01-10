// TypingIndicatorView.swift
// Animated typing indicator for thinkers
//
// Created by iOS Native Agent

import SwiftUI

/// Animated typing indicator showing when a thinker is composing
struct TypingIndicatorView: View {
    let thinkerName: String

    @State private var animationPhase = 0

    private let dotCount = 3
    private let animationInterval: TimeInterval = 0.4

    var body: some View {
        HStack(spacing: 4) {
            Text("\(thinkerName) is thinking")
                .font(.caption)
                .foregroundStyle(.secondary)
                .italic()

            HStack(spacing: 2) {
                ForEach(0..<dotCount, id: \.self) { index in
                    Circle()
                        .fill(Color.secondary)
                        .frame(width: 4, height: 4)
                        .opacity(dotOpacity(for: index))
                        .animation(
                            .easeInOut(duration: animationInterval),
                            value: animationPhase
                        )
                }
            }

            Spacer()
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(.regularMaterial)
        .onAppear {
            startAnimation()
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(thinkerName) is typing")
    }

    private func dotOpacity(for index: Int) -> Double {
        let activeIndex = animationPhase % dotCount
        if index == activeIndex {
            return 1.0
        } else if index == (activeIndex + dotCount - 1) % dotCount {
            return 0.5
        } else {
            return 0.3
        }
    }

    private func startAnimation() {
        Timer.scheduledTimer(withTimeInterval: animationInterval, repeats: true) { _ in
            animationPhase += 1
        }
    }
}

/// Compact bubble-style typing indicator
struct TypingBubbleView: View {
    let thinkerName: String

    @State private var animationPhase = 0

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(thinkerName)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)

                HStack(spacing: 4) {
                    ForEach(0..<3, id: \.self) { index in
                        Circle()
                            .fill(Color.secondary)
                            .frame(width: 6, height: 6)
                            .scaleEffect(dotScale(for: index))
                            .animation(
                                .easeInOut(duration: 0.5)
                                    .repeatForever()
                                    .delay(Double(index) * 0.15),
                                value: animationPhase
                            )
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Color(.systemGray5))
                .clipShape(RoundedRectangle(cornerRadius: 16))
            }

            Spacer()
        }
        .onAppear {
            animationPhase = 1
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(thinkerName) is typing")
    }

    private func dotScale(for index: Int) -> CGFloat {
        animationPhase > 0 ? 1.2 : 1.0
    }
}

// MARK: - Preview

#Preview("Bar Style") {
    VStack {
        Spacer()
        TypingIndicatorView(thinkerName: "Socrates")
    }
}

#Preview("Bubble Style") {
    VStack {
        Spacer()
        TypingBubbleView(thinkerName: "Socrates")
            .padding()
        Spacer()
    }
}
