// ThinkerSelectorView.swift
// Multi-selection interface for adding thinkers to conversations
//
// Created by iOS Native Agent - Phase 6

import SwiftUI

/// View model for thinker selection
@Observable
final class ThinkerSelectorViewModel {
    private(set) var availableThinkers: [Thinker] = []
    private(set) var isLoading = false
    private(set) var isAdding = false
    var errorMessage: String?
    var searchText = ""
    var selectedThinkers: Set<String> = []

    /// Maximum number of thinkers that can be selected
    let maxSelections: Int

    /// Current number of thinkers in the conversation (to enforce total limit)
    let currentThinkerCount: Int

    /// Remaining slots available
    var remainingSlots: Int {
        max(0, 5 - currentThinkerCount - selectedThinkers.count)
    }

    /// IDs of thinkers already in the conversation
    private let excludedThinkerIds: Set<String>

    init(currentThinkerCount: Int, excludedThinkerIds: Set<String>) {
        self.currentThinkerCount = currentThinkerCount
        self.excludedThinkerIds = excludedThinkerIds
        self.maxSelections = 5 - currentThinkerCount
    }

    /// Filtered and available thinkers
    var filteredThinkers: [Thinker] {
        let available = availableThinkers.filter { !excludedThinkerIds.contains($0.id) }
        guard !searchText.isEmpty else { return available }
        let query = searchText.lowercased()
        return available.filter { thinker in
            thinker.name.lowercased().contains(query) ||
            thinker.bio.lowercased().contains(query)
        }
    }

    /// Whether selection is at max capacity
    var isAtMaxSelection: Bool {
        selectedThinkers.count >= maxSelections
    }

    /// Toggle selection of a thinker
    func toggleSelection(_ thinkerId: String) {
        if selectedThinkers.contains(thinkerId) {
            selectedThinkers.remove(thinkerId)
        } else if !isAtMaxSelection {
            selectedThinkers.insert(thinkerId)
        }
    }

    /// Check if a thinker is selected
    func isSelected(_ thinkerId: String) -> Bool {
        selectedThinkers.contains(thinkerId)
    }

    /// Get selected Thinker objects
    var selectedThinkerObjects: [Thinker] {
        availableThinkers.filter { selectedThinkers.contains($0.id) }
    }

    /// Load available thinkers
    @MainActor
    func loadThinkers() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            availableThinkers = try await APIClient.shared.getThinkers()
        } catch let error as NetworkError {
            errorMessage = error.userMessage
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Add selected thinkers to conversation
    @MainActor
    func addThinkersToConversation(conversationId: String) async -> Bool {
        guard !selectedThinkers.isEmpty else { return false }

        isAdding = true
        errorMessage = nil
        defer { isAdding = false }

        do {
            let thinkersToAdd = selectedThinkerObjects.map { ThinkerCreate(from: $0) }
            _ = try await APIClient.shared.addThinkersToConversation(
                conversationId: conversationId,
                thinkers: thinkersToAdd
            )
            return true
        } catch let error as NetworkError {
            errorMessage = error.userMessage
            return false
        } catch {
            errorMessage = error.localizedDescription
            return false
        }
    }

    func clearError() {
        errorMessage = nil
    }
}

/// Multi-selection view for adding thinkers to an existing conversation
struct ThinkerSelectorView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var viewModel: ThinkerSelectorViewModel

    let conversationId: String
    let onThinkersAdded: () -> Void

    init(conversationId: String, currentThinkerCount: Int, excludedThinkerIds: Set<String>, onThinkersAdded: @escaping () -> Void) {
        self.conversationId = conversationId
        self.onThinkersAdded = onThinkersAdded
        self._viewModel = State(wrappedValue: ThinkerSelectorViewModel(
            currentThinkerCount: currentThinkerCount,
            excludedThinkerIds: excludedThinkerIds
        ))
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Selection status header
                selectionHeader

                // Thinker list
                if viewModel.isLoading && viewModel.availableThinkers.isEmpty {
                    loadingState
                } else if viewModel.filteredThinkers.isEmpty {
                    emptyState
                } else {
                    thinkerList
                }
            }
            .navigationTitle("Add Thinkers")
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $viewModel.searchText, prompt: "Search thinkers...")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        Task {
                            if await viewModel.addThinkersToConversation(conversationId: conversationId) {
                                onThinkersAdded()
                                dismiss()
                            }
                        }
                    }
                    .disabled(viewModel.selectedThinkers.isEmpty || viewModel.isAdding)
                }
            }
            .task {
                await viewModel.loadThinkers()
            }
            .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
                Button("OK", role: .cancel) {
                    viewModel.clearError()
                }
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
            .overlay {
                if viewModel.isAdding {
                    ProgressView("Adding thinkers...")
                        .padding()
                        .background(.regularMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }

    // MARK: - View Components

    private var selectionHeader: some View {
        VStack(spacing: 8) {
            HStack {
                Text("Selected: \(viewModel.selectedThinkers.count)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                Spacer()
                Text("\(viewModel.remainingSlots) slots remaining")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if !viewModel.selectedThinkerObjects.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(viewModel.selectedThinkerObjects) { thinker in
                            SelectedThinkerChip(thinker: thinker) {
                                withAnimation {
                                    viewModel.toggleSelection(thinker.id)
                                }
                            }
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemGroupedBackground))
    }

    private var loadingState: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)
            Text("Loading thinkers...")
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        ContentUnavailableView {
            Label("No Thinkers Available", systemImage: "person.3")
        } description: {
            if viewModel.searchText.isEmpty {
                Text("All available thinkers are already in this conversation.")
            } else {
                Text("No thinkers match '\(viewModel.searchText)'")
            }
        }
    }

    private var thinkerList: some View {
        List {
            ForEach(viewModel.filteredThinkers) { thinker in
                SelectableThinkerRow(
                    thinker: thinker,
                    isSelected: viewModel.isSelected(thinker.id),
                    isDisabled: !viewModel.isSelected(thinker.id) && viewModel.isAtMaxSelection
                ) {
                    withAnimation {
                        viewModel.toggleSelection(thinker.id)
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
    }
}

/// Row showing a thinker with selection state
struct SelectableThinkerRow: View {
    let thinker: Thinker
    let isSelected: Bool
    let isDisabled: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                // Selection indicator
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.title3)
                    .foregroundStyle(isSelected ? .green : .secondary)

                // Avatar
                ThinkerAvatarView(
                    name: thinker.name,
                    color: thinker.color,
                    imageUrl: thinker.imageUrl,
                    size: 44
                )

                // Info
                VStack(alignment: .leading, spacing: 2) {
                    Text(thinker.name)
                        .font(.headline)
                        .foregroundStyle(.primary)
                    Text(thinker.bio)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }

                Spacer()
            }
            .padding(.vertical, 4)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(isDisabled)
        .opacity(isDisabled ? 0.5 : 1.0)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(thinker.name). \(thinker.bio)")
        .accessibilityValue(isSelected ? "Selected" : "Not selected")
        .accessibilityHint(isDisabled ? "Maximum thinkers selected" : "Double tap to toggle selection")
    }
}

// MARK: - Preview

#Preview {
    ThinkerSelectorView(
        conversationId: "preview-id",
        currentThinkerCount: 2,
        excludedThinkerIds: [],
        onThinkersAdded: {}
    )
}
