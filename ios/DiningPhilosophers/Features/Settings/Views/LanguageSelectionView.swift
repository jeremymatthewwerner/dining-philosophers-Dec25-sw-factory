// LanguageSelectionView.swift
// View for selecting and syncing language preference
//
// Created by iOS Native Agent - Phase 7

import SwiftUI

/// View for selecting language preference with backend sync
struct LanguageSelectionView: View {
    @Environment(AuthManager.self) private var authManager
    @Environment(ThemeManager.self) private var themeManager
    @Environment(\.dismiss) private var dismiss

    @State private var selectedLanguage: AppLanguage = .system
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var showingRestartAlert = false

    private var hasChanges: Bool {
        selectedLanguage != themeManager.language
    }

    var body: some View {
        Form {
            Section {
                ForEach(AppLanguage.allCases) { language in
                    Button {
                        selectedLanguage = language
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(language.displayName)
                                    .foregroundStyle(.primary)

                                if language != .system {
                                    Text(language.nativeDisplayName)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }
                            }

                            Spacer()

                            if selectedLanguage == language {
                                Image(systemName: "checkmark")
                                    .foregroundStyle(.accentColor)
                            }
                        }
                    }
                    .accessibilityLabel(language.displayName)
                    .accessibilityAddTraits(selectedLanguage == language ? .isSelected : [])
                }
            } header: {
                Text("Language")
            } footer: {
                Text("Changing the language will update how thinkers respond and may require restarting the app for full effect.")
            }

            if let error = errorMessage {
                Section {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.footnote)
                }
            }
        }
        .navigationTitle("Language")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if isSaving {
                    ProgressView()
                } else {
                    Button("Save") {
                        Task {
                            await saveLanguage()
                        }
                    }
                    .disabled(!hasChanges)
                }
            }
        }
        .onAppear {
            selectedLanguage = themeManager.language
        }
        .alert("Language Updated", isPresented: $showingRestartAlert) {
            Button("OK") {
                dismiss()
            }
        } message: {
            Text("Your language preference has been updated. Some changes may require restarting the app.")
        }
        .interactiveDismissDisabled(isSaving)
    }

    private func saveLanguage() async {
        guard hasChanges else { return }

        isSaving = true
        errorMessage = nil

        do {
            // Update on backend
            try await authManager.updateLanguagePreference(selectedLanguage.apiCode)

            // Update local theme manager
            themeManager.language = selectedLanguage

            showingRestartAlert = true
        } catch let error as NetworkError {
            errorMessage = error.userMessage
        } catch {
            errorMessage = "Failed to update language. Please try again."
        }

        isSaving = false
    }
}

// MARK: - AppLanguage Extensions

extension AppLanguage {
    /// Native name for the language (in that language)
    var nativeDisplayName: String {
        switch self {
        case .system: return ""
        case .english: return "English"
        case .spanish: return "Espanol"
        case .french: return "Francais"
        case .german: return "Deutsch"
        case .japanese: return "Nihongo"
        case .chinese: return "Zhongwen"
        }
    }

    /// API code to send to backend
    var apiCode: String {
        switch self {
        case .system: return "en" // Default to English
        case .english: return "en"
        case .spanish: return "es"
        case .french: return "fr"
        case .german: return "de"
        case .japanese: return "ja"
        case .chinese: return "zh"
        }
    }

    /// Create from API language code
    init(apiCode: String) {
        switch apiCode.lowercased() {
        case "en": self = .english
        case "es": self = .spanish
        case "fr": self = .french
        case "de": self = .german
        case "ja": self = .japanese
        case "zh": self = .chinese
        default: self = .english
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        LanguageSelectionView()
            .environment(AuthManager())
            .environment(ThemeManager())
    }
}
