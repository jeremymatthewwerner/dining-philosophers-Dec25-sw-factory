// ThinkerBrowserView.swift
// Browse thinkers organized by era categories with search
//
// Created by iOS Native Agent - Phase 6

import SwiftUI

/// Mode for the thinker browser
enum ThinkerBrowserMode {
    /// Browsing thinkers to view details
    case browse
    /// Selecting thinkers for a conversation (with callback)
    case select(onSelect: (Thinker) -> Void)
}

/// View for browsing available thinkers
struct ThinkerBrowserView: View {
    @State private var viewModel = ThinkerBrowserViewModel()
    @Environment(\.dismiss) private var dismiss

    let mode: ThinkerBrowserMode
    let selectedThinkerIds: Set<String>

    init(mode: ThinkerBrowserMode = .browse, selectedThinkerIds: Set<String> = []) {
        self.mode = mode
        self.selectedThinkerIds = selectedThinkerIds
    }

    var body: some View {
        Group {
            if viewModel.isLoading && viewModel.thinkers.isEmpty {
                loadingState
            } else if viewModel.thinkers.isEmpty {
                emptyState
            } else {
                thinkerList
            }
        }
        .navigationTitle("Thinkers")
        .searchable(text: $viewModel.searchText, prompt: "Search thinkers...")
        .refreshable {
            await viewModel.loadThinkers()
        }
        .task {
            if viewModel.thinkers.isEmpty {
                await viewModel.loadThinkers()
            }
        }
        .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
            Button("Retry") {
                Task {
                    await viewModel.loadThinkers()
                }
            }
            Button("OK", role: .cancel) {
                viewModel.clearError()
            }
        } message: {
            Text(viewModel.errorMessage ?? "")
        }
    }

    // MARK: - View Components

    private var loadingState: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)
            Text("Loading thinkers...")
                .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Loading thinkers")
    }

    private var emptyState: some View {
        ContentUnavailableView {
            Label("No Thinkers Found", systemImage: "person.3")
        } description: {
            if viewModel.searchText.isEmpty {
                Text("Unable to load thinkers. Pull to refresh.")
            } else {
                Text("No thinkers match '\(viewModel.searchText)'")
            }
        }
    }

    private var thinkerList: some View {
        List {
            ForEach(viewModel.groupedThinkers) { group in
                Section {
                    ForEach(group.thinkers) { thinker in
                        thinkerRow(thinker)
                    }
                } header: {
                    eraHeader(group.era)
                }
            }
        }
        .listStyle(.insetGrouped)
    }

    private func eraHeader(_ era: ThinkerEra) -> some View {
        HStack(spacing: 8) {
            Image(systemName: era.systemImage)
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 2) {
                Text(era.rawValue)
                    .font(.headline)
                Text(era.description)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(.vertical, 4)
    }

    @ViewBuilder
    private func thinkerRow(_ thinker: Thinker) -> some View {
        switch mode {
        case .browse:
            NavigationLink(value: thinker) {
                ThinkerRowContent(thinker: thinker, isSelected: false)
            }
        case .select(let onSelect):
            let isSelected = selectedThinkerIds.contains(thinker.id)
            Button {
                if !isSelected {
                    onSelect(thinker)
                    dismiss()
                }
            } label: {
                ThinkerRowContent(thinker: thinker, isSelected: isSelected)
            }
            .disabled(isSelected)
        }
    }
}

/// Row content showing thinker info
struct ThinkerRowContent: View {
    let thinker: Thinker
    let isSelected: Bool

    var body: some View {
        HStack(spacing: 12) {
            // Avatar with color
            ThinkerAvatarView(
                name: thinker.name,
                color: thinker.color,
                imageUrl: thinker.imageUrl,
                size: 50
            )

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(thinker.name)
                        .font(.headline)
                    if isSelected {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    }
                }

                Text(thinker.bio)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(thinker.name). \(thinker.bio)")
        .accessibilityHint(isSelected ? "Already selected" : "Double tap to select")
    }
}

/// Circular avatar view for thinkers
struct ThinkerAvatarView: View {
    let name: String
    let color: String
    let imageUrl: String?
    let size: CGFloat

    private var thinkerColor: Color {
        Color(hex: color) ?? .accentColor
    }

    private var initials: String {
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            let first = parts.first?.first ?? Character(" ")
            let last = parts.last?.first ?? Character(" ")
            return String(first) + String(last)
        }
        return String(name.prefix(2)).uppercased()
    }

    var body: some View {
        Group {
            if let imageUrl = imageUrl, let url = URL(string: imageUrl) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFill()
                    case .failure:
                        initialsView
                    case .empty:
                        ProgressView()
                    @unknown default:
                        initialsView
                    }
                }
            } else {
                initialsView
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .overlay(
            Circle()
                .stroke(thinkerColor, lineWidth: 2)
        )
    }

    private var initialsView: some View {
        ZStack {
            thinkerColor.opacity(0.2)
            Text(initials)
                .font(.system(size: size * 0.4, weight: .semibold))
                .foregroundStyle(thinkerColor)
        }
    }
}

// MARK: - Preview

#Preview("Browse Mode") {
    NavigationStack {
        ThinkerBrowserView(mode: .browse)
    }
}

#Preview("Select Mode") {
    NavigationStack {
        ThinkerBrowserView(
            mode: .select(onSelect: { thinker in
                print("Selected: \(thinker.name)")
            }),
            selectedThinkerIds: []
        )
    }
}
