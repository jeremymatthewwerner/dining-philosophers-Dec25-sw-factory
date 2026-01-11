// LanguageSelectionView.swift
// View for selecting user's preferred language
//
// Created by iOS Native Agent - Phase 7

import SwiftUI

/// View for selecting the user's preferred language
struct LanguageSelectionView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AuthManager.self) private var authManager

    @State private var selectedLanguage: SupportedLanguage = .english
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(SupportedLanguage.allCases) { language in
                        Button {
                            selectLanguage(language)
                        } label: {
                            HStack {
                                Text(language.flag)
                                    .font(.title2)
                                    .accessibilityHidden(true)

                                Text(language.displayName)
                                    .foregroundStyle(.primary)

                                Spacer()

                                if selectedLanguage == language {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.accent)
                                        .accessibilityLabel("Selected")
                                }
                            }
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("\(language.displayName)")
                        .accessibilityAddTraits(selectedLanguage == language ? .isSelected : [])
                    }
                } footer: {
                    Text("This language will be used for AI thinker responses in conversations.")
                }
            }
            .navigationTitle("Language")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        Task {
                            await saveLanguage()
                        }
                    }
                    .disabled(isLoading || !hasChanges)
                }
            }
            .alert("Error", isPresented: .constant(errorMessage != nil)) {
                Button("OK") {
                    errorMessage = nil
                }
            } message: {
                Text(errorMessage ?? "")
            }
            .disabled(isLoading)
            .overlay {
                if isLoading {
                    ProgressView("Saving...")
                        .padding()
                        .background(.regularMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }
            .onAppear {
                if let user = authManager.currentUser,
                   let language = SupportedLanguage(rawValue: user.languagePreference) {
                    selectedLanguage = language
                }
            }
        }
    }

    // MARK: - Computed Properties

    private var hasChanges: Bool {
        guard let user = authManager.currentUser else { return false }
        return selectedLanguage.rawValue != user.languagePreference
    }

    // MARK: - Actions

    private func selectLanguage(_ language: SupportedLanguage) {
        withAnimation {
            selectedLanguage = language
        }
    }

    @MainActor
    private func saveLanguage() async {
        isLoading = true
        errorMessage = nil

        do {
            let updatedUser = try await APIClient.shared.updateLanguage(languagePreference: selectedLanguage.rawValue)
            authManager.updateUser(updatedUser)
            dismiss()
        } catch let error as NetworkError {
            errorMessage = error.userMessage
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }
}

// MARK: - Preview

#Preview {
    LanguageSelectionView()
        .environment(AuthManager())
}
