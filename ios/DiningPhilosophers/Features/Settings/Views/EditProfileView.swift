// EditProfileView.swift
// View for editing user profile (display name)
//
// Created by iOS Native Agent - Phase 7

import SwiftUI

/// View for editing user's display name
struct EditProfileView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AuthManager.self) private var authManager

    @State private var displayName: String = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingSuccessAlert = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Display Name", text: $displayName)
                        .textContentType(.name)
                        .autocorrectionDisabled()
                        .accessibilityLabel("Display name")
                        .accessibilityHint("Enter your display name")
                } header: {
                    Text("Display Name")
                } footer: {
                    Text("This is how your name will appear in conversations.")
                }

                if let user = authManager.currentUser {
                    Section("Account Info") {
                        LabeledContent("Username") {
                            Text("@\(user.username)")
                                .foregroundStyle(.secondary)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
            }
            .navigationTitle("Edit Profile")
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
                            await saveProfile()
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
            .alert("Profile Updated", isPresented: $showingSuccessAlert) {
                Button("OK") {
                    dismiss()
                }
            } message: {
                Text("Your display name has been updated.")
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
                if let user = authManager.currentUser {
                    displayName = user.displayName ?? user.username
                }
            }
        }
    }

    // MARK: - Computed Properties

    private var hasChanges: Bool {
        guard let user = authManager.currentUser else { return false }
        let currentName = user.displayName ?? user.username
        return displayName != currentName && !displayName.trimmingCharacters(in: .whitespaces).isEmpty
    }

    // MARK: - Actions

    @MainActor
    private func saveProfile() async {
        isLoading = true
        errorMessage = nil

        do {
            let updatedUser = try await APIClient.shared.updateProfile(displayName: displayName.trimmingCharacters(in: .whitespaces))
            authManager.updateUser(updatedUser)
            showingSuccessAlert = true
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
    EditProfileView()
        .environment(AuthManager())
}
