// ThinkerDetailView.swift
// Detailed view of a thinker showing bio, positions, and style
//
// Created by iOS Native Agent - Phase 6

import SwiftUI

/// Detailed view for a single thinker
struct ThinkerDetailView: View {
    let thinker: Thinker
    let onStartConversation: ((Thinker) -> Void)?

    @Environment(\.dismiss) private var dismiss

    init(thinker: Thinker, onStartConversation: ((Thinker) -> Void)? = nil) {
        self.thinker = thinker
        self.onStartConversation = onStartConversation
    }

    private var thinkerColor: Color {
        Color(hex: thinker.color) ?? .accentColor
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header with avatar
                headerSection

                // Bio section
                infoSection(
                    title: "Biography",
                    content: thinker.bio,
                    icon: "person.text.rectangle"
                )

                // Positions section
                infoSection(
                    title: "Positions & Beliefs",
                    content: thinker.positions,
                    icon: "lightbulb"
                )

                // Style section
                infoSection(
                    title: "Conversation Style",
                    content: thinker.style,
                    icon: "bubble.left.and.bubble.right"
                )

                // Action buttons
                if onStartConversation != nil {
                    actionButtons
                }

                Spacer(minLength: 32)
            }
            .padding()
        }
        .navigationTitle(thinker.name)
        .navigationBarTitleDisplayMode(.inline)
        .background(Color(.systemGroupedBackground))
    }

    // MARK: - View Components

    private var headerSection: some View {
        VStack(spacing: 16) {
            ThinkerAvatarView(
                name: thinker.name,
                color: thinker.color,
                imageUrl: thinker.imageUrl,
                size: 120
            )

            Text(thinker.name)
                .font(.title)
                .fontWeight(.bold)
                .multilineTextAlignment(.center)
        }
        .padding(.top, 8)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(thinker.name)
    }

    private func infoSection(title: String, content: String, icon: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: icon)
                    .foregroundStyle(thinkerColor)
                Text(title)
                    .font(.headline)
            }

            Text(content)
                .font(.body)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(title): \(content)")
    }

    private var actionButtons: some View {
        Button {
            onStartConversation?(thinker)
            dismiss()
        } label: {
            Label("Start Conversation", systemImage: "bubble.left.and.bubble.right.fill")
                .font(.headline)
                .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .tint(thinkerColor)
        .controlSize(.large)
        .accessibilityHint("Start a new conversation with \(thinker.name)")
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ThinkerDetailView(
            thinker: Thinker(
                id: "1",
                name: "Socrates",
                bio: "Ancient Greek philosopher from Athens (470-399 BC). Founder of Western philosophy.",
                positions: "Known for the Socratic method of questioning, belief that wisdom begins with acknowledging ignorance.",
                style: "Uses probing questions to examine beliefs. Humble yet persistent. Often claims to know nothing.",
                color: "#6366f1",
                imageUrl: nil
            ),
            onStartConversation: { _ in }
        )
    }
}
