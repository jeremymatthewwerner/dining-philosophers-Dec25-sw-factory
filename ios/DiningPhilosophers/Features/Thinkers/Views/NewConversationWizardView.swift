// NewConversationWizardView.swift
// Multi-step wizard for creating new conversations
//
// Created by iOS Native Agent - Phase 6

import SwiftUI

/// Step in the conversation creation wizard
enum WizardStep: Int, CaseIterable {
    case topic = 0
    case thinkers = 1
    case review = 2

    var title: String {
        switch self {
        case .topic: return "Topic"
        case .thinkers: return "Thinkers"
        case .review: return "Review"
        }
    }
}

/// View model for the new conversation wizard
@Observable
final class NewConversationWizardViewModel {
    var topic = ""
    var selectedThinkers: [Thinker] = []
    var suggestions: [ThinkerSuggestion] = []
    var isLoadingSuggestions = false
    var isCreating = false
    var errorMessage: String?

    var topicIsValid: Bool {
        topic.trimmingCharacters(in: .whitespacesAndNewlines).count >= 3
    }

    var canCreate: Bool {
        topicIsValid && !selectedThinkers.isEmpty && !isCreating
    }

    var selectedThinkerIds: Set<String> {
        Set(selectedThinkers.map(\.id))
    }

    /// Add a thinker to the selection
    func addThinker(_ thinker: Thinker) {
        guard !selectedThinkerIds.contains(thinker.id), selectedThinkers.count < 5 else { return }
        selectedThinkers.append(thinker)
    }

    /// Remove a thinker from selection
    func removeThinker(_ thinker: Thinker) {
        selectedThinkers.removeAll { $0.id == thinker.id }
    }

    /// Add a suggested thinker (convert ThinkerSuggestion to Thinker)
    func addSuggestion(_ suggestion: ThinkerSuggestion) {
        // Create a Thinker from the suggestion profile
        let thinker = Thinker(
            id: UUID().uuidString, // Temporary ID until conversation is created
            name: suggestion.profile.name,
            bio: suggestion.profile.bio,
            positions: suggestion.profile.positions,
            style: suggestion.profile.style,
            color: "#6366f1", // Default color
            imageUrl: suggestion.profile.imageUrl
        )
        addThinker(thinker)
    }

    /// Load AI suggestions for the current topic
    @MainActor
    func loadSuggestions() async {
        guard topicIsValid else { return }

        isLoadingSuggestions = true
        errorMessage = nil
        defer { isLoadingSuggestions = false }

        do {
            let excludeNames = selectedThinkers.map(\.name)
            suggestions = try await APIClient.shared.suggestThinkers(
                topic: topic,
                count: 3
            ).filter { suggestion in
                !excludeNames.contains(suggestion.name)
            }
        } catch let error as NetworkError {
            errorMessage = error.userMessage
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Create the conversation
    @MainActor
    func createConversation() async -> String? {
        guard canCreate else { return nil }

        isCreating = true
        errorMessage = nil
        defer { isCreating = false }

        do {
            // For thinkers from suggestions, we pass their names
            // The backend will create thinker records
            let thinkerNames = selectedThinkers.map(\.name)
            let conversation = try await APIClient.shared.createConversation(
                topic: topic,
                thinkerIds: thinkerNames // Backend expects names for new conversations
            )
            return conversation.id
        } catch let error as NetworkError {
            errorMessage = error.userMessage
            return nil
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    func clearError() {
        errorMessage = nil
    }
}

/// Multi-step wizard for creating new conversations
struct NewConversationWizardView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var viewModel = NewConversationWizardViewModel()
    @State private var currentStep: WizardStep = .topic
    @State private var showingThinkerBrowser = false

    let onConversationCreated: (String) -> Void

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Progress indicator
                progressIndicator

                // Step content
                stepContent
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
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
                    nextButton
                }
            }
            .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
                Button("OK", role: .cancel) {
                    viewModel.clearError()
                }
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
            .sheet(isPresented: $showingThinkerBrowser) {
                NavigationStack {
                    ThinkerBrowserView(
                        mode: .select(onSelect: { thinker in
                            viewModel.addThinker(thinker)
                        }),
                        selectedThinkerIds: viewModel.selectedThinkerIds
                    )
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Done") {
                                showingThinkerBrowser = false
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: - Progress Indicator

    private var progressIndicator: some View {
        HStack(spacing: 0) {
            ForEach(WizardStep.allCases, id: \.rawValue) { step in
                VStack(spacing: 4) {
                    Circle()
                        .fill(stepColor(for: step))
                        .frame(width: 28, height: 28)
                        .overlay {
                            if step.rawValue < currentStep.rawValue {
                                Image(systemName: "checkmark")
                                    .font(.caption.bold())
                                    .foregroundStyle(.white)
                            } else {
                                Text("\(step.rawValue + 1)")
                                    .font(.caption.bold())
                                    .foregroundStyle(step == currentStep ? .white : .secondary)
                            }
                        }

                    Text(step.title)
                        .font(.caption2)
                        .foregroundStyle(step == currentStep ? .primary : .secondary)
                }
                .frame(maxWidth: .infinity)

                if step != WizardStep.allCases.last {
                    Rectangle()
                        .fill(step.rawValue < currentStep.rawValue ? Color.accentColor : Color.secondary.opacity(0.3))
                        .frame(height: 2)
                        .frame(maxWidth: 40)
                }
            }
        }
        .padding()
        .background(Color(.systemGroupedBackground))
    }

    private func stepColor(for step: WizardStep) -> Color {
        if step.rawValue < currentStep.rawValue {
            return .accentColor
        } else if step == currentStep {
            return .accentColor
        } else {
            return .secondary.opacity(0.3)
        }
    }

    // MARK: - Step Content

    @ViewBuilder
    private var stepContent: some View {
        switch currentStep {
        case .topic:
            topicStep
        case .thinkers:
            thinkersStep
        case .review:
            reviewStep
        }
    }

    // MARK: - Topic Step

    private var topicStep: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("What would you like to discuss?")
                    .font(.title2)
                    .fontWeight(.semibold)

                Text("Enter a topic, question, or idea to spark a thought-provoking conversation with history's greatest minds.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                TextEditor(text: $viewModel.topic)
                    .frame(minHeight: 120)
                    .padding(12)
                    .background(Color(.secondarySystemGroupedBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(Color.secondary.opacity(0.2))
                    )

                if !viewModel.topic.isEmpty && !viewModel.topicIsValid {
                    Text("Please enter at least 3 characters")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }

                // Topic suggestions
                VStack(alignment: .leading, spacing: 12) {
                    Text("Suggestions")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(.secondary)

                    ForEach(topicSuggestions, id: \.self) { suggestion in
                        Button {
                            viewModel.topic = suggestion
                        } label: {
                            Text(suggestion)
                                .font(.subheadline)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(Color.accentColor.opacity(0.1))
                                .foregroundStyle(.accentColor)
                                .clipShape(Capsule())
                        }
                    }
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
    }

    private var topicSuggestions: [String] {
        [
            "What is the meaning of life?",
            "How should we balance individual freedom with social responsibility?",
            "Is artificial intelligence a threat to humanity?",
            "What makes a society just?"
        ]
    }

    // MARK: - Thinkers Step

    private var thinkersStep: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Text("Who should join the discussion?")
                    .font(.title2)
                    .fontWeight(.semibold)

                Text("Select 1-5 thinkers to participate in your conversation.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                // Selected thinkers
                selectedThinkersSection

                Divider()

                // AI Suggestions
                suggestionsSection

                // Browse button
                Button {
                    showingThinkerBrowser = true
                } label: {
                    Label("Browse All Thinkers", systemImage: "person.3")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .task {
            if viewModel.suggestions.isEmpty {
                await viewModel.loadSuggestions()
            }
        }
    }

    private var selectedThinkersSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Selected (\(viewModel.selectedThinkers.count)/5)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                Spacer()
            }

            if viewModel.selectedThinkers.isEmpty {
                Text("No thinkers selected yet")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 20)
            } else {
                FlowLayout(spacing: 8) {
                    ForEach(viewModel.selectedThinkers) { thinker in
                        SelectedThinkerChip(thinker: thinker) {
                            withAnimation {
                                viewModel.removeThinker(thinker)
                            }
                        }
                    }
                }
            }
        }
    }

    private var suggestionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Suggested for your topic")
                    .font(.subheadline)
                    .fontWeight(.medium)

                Spacer()

                if !viewModel.isLoadingSuggestions {
                    Button {
                        Task {
                            await viewModel.loadSuggestions()
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .font(.caption)
                    }
                    .buttonStyle(.borderless)
                }
            }

            if viewModel.isLoadingSuggestions {
                HStack {
                    Spacer()
                    ProgressView()
                        .padding()
                    Spacer()
                }
            } else if viewModel.suggestions.isEmpty {
                Text("No suggestions available")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 12)
            } else {
                ForEach(viewModel.suggestions, id: \.name) { suggestion in
                    SuggestionCard(suggestion: suggestion) {
                        withAnimation {
                            viewModel.addSuggestion(suggestion)
                            // Remove from suggestions
                            viewModel.suggestions.removeAll { $0.name == suggestion.name }
                        }
                    }
                }
            }
        }
    }

    // MARK: - Review Step

    private var reviewStep: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Text("Ready to start?")
                    .font(.title2)
                    .fontWeight(.semibold)

                // Topic summary
                VStack(alignment: .leading, spacing: 8) {
                    Label("Topic", systemImage: "bubble.left.and.bubble.right")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Text(viewModel.topic)
                        .font(.body)
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemGroupedBackground))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }

                // Thinkers summary
                VStack(alignment: .leading, spacing: 12) {
                    Label("Participants", systemImage: "person.3")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    ForEach(viewModel.selectedThinkers) { thinker in
                        HStack(spacing: 12) {
                            ThinkerAvatarView(
                                name: thinker.name,
                                color: thinker.color,
                                imageUrl: thinker.imageUrl,
                                size: 44
                            )
                            VStack(alignment: .leading, spacing: 2) {
                                Text(thinker.name)
                                    .font(.headline)
                                Text(thinker.bio)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(.secondarySystemGroupedBackground))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                }

                if viewModel.isCreating {
                    HStack {
                        Spacer()
                        ProgressView("Creating conversation...")
                        Spacer()
                    }
                    .padding(.top, 20)
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
    }

    // MARK: - Navigation

    @ViewBuilder
    private var nextButton: some View {
        switch currentStep {
        case .topic:
            Button("Next") {
                withAnimation {
                    currentStep = .thinkers
                }
            }
            .disabled(!viewModel.topicIsValid)

        case .thinkers:
            Button("Next") {
                withAnimation {
                    currentStep = .review
                }
            }
            .disabled(viewModel.selectedThinkers.isEmpty)

        case .review:
            Button("Create") {
                Task {
                    if let conversationId = await viewModel.createConversation() {
                        onConversationCreated(conversationId)
                    }
                }
            }
            .disabled(!viewModel.canCreate)
        }
    }
}

// MARK: - Supporting Views

/// Chip showing a selected thinker with remove button
struct SelectedThinkerChip: View {
    let thinker: Thinker
    let onRemove: () -> Void

    private var thinkerColor: Color {
        Color(hex: thinker.color) ?? .accentColor
    }

    var body: some View {
        HStack(spacing: 6) {
            ThinkerAvatarView(
                name: thinker.name,
                color: thinker.color,
                imageUrl: thinker.imageUrl,
                size: 24
            )

            Text(thinker.name)
                .font(.subheadline)
                .fontWeight(.medium)

            Button(action: onRemove) {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
        }
        .padding(.leading, 4)
        .padding(.trailing, 8)
        .padding(.vertical, 6)
        .background(thinkerColor.opacity(0.15))
        .clipShape(Capsule())
    }
}

/// Card showing a thinker suggestion
struct SuggestionCard: View {
    let suggestion: ThinkerSuggestion
    let onAdd: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            ThinkerAvatarView(
                name: suggestion.profile.name,
                color: "#6366f1",
                imageUrl: suggestion.profile.imageUrl,
                size: 50
            )

            VStack(alignment: .leading, spacing: 4) {
                Text(suggestion.name)
                    .font(.headline)
                Text(suggestion.reason)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer()

            Button(action: onAdd) {
                Image(systemName: "plus.circle.fill")
                    .font(.title2)
                    .foregroundStyle(.green)
            }
            .buttonStyle(.plain)
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

/// Flow layout for wrapping items
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = layout(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = layout(proposal: proposal, subviews: subviews)
        for (index, frame) in result.frames.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY), proposal: ProposedViewSize(frame.size))
        }
    }

    private func layout(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, frames: [CGRect]) {
        var frames: [CGRect] = []
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var lineHeight: CGFloat = 0
        let maxWidth = proposal.width ?? .infinity

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)

            if currentX + size.width > maxWidth && currentX > 0 {
                currentX = 0
                currentY += lineHeight + spacing
                lineHeight = 0
            }

            frames.append(CGRect(x: currentX, y: currentY, width: size.width, height: size.height))
            lineHeight = max(lineHeight, size.height)
            currentX += size.width + spacing
        }

        let totalHeight = currentY + lineHeight
        return (CGSize(width: maxWidth, height: totalHeight), frames)
    }
}

// MARK: - Preview

#Preview {
    NewConversationWizardView { conversationId in
        print("Created: \(conversationId)")
    }
}
