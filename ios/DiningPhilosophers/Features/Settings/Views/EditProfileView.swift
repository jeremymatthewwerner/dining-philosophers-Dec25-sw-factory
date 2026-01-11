// EditProfileView.swift
// View for editing user profile (display name)
//
// Created by iOS Native Agent - Phase 7

import SwiftUI

/// View for editing user profile information
struct EditProfileView: View {
    @Environment(AuthManager.self) private var authManager
    @Environment(\.dismiss) private var dismiss

    @State private var displayName: String = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var showingSuccess = false

    private var hasChanges: Bool {
        displayName != (authManager.currentUser?.displayName ?? "")
    }

    private var isValid: Bool {
        !displayName.trimmingCharacters(in: .whitespaces).isEmpty
    }

    var body: some View {
        Form {
            Section {
                TextField("Display Name", text: $displayName)
                    .textContentType(.name)
                    .autocorrectionDisabled()
                    .accessibilityLabel("Display name")
                    .accessibilityHint("Enter your display name")
            } header: {
                Text("Profile")
            } footer: {
                Text("This is how other users will see your name in conversations.")
            }

            if let user = authManager.currentUser {
                Section("Account Info") {
                    LabeledContent("Username") {
                        Text("@\(user.username)")
                            .foregroundStyle(.secondary)
                    }
                    .accessibilityLabel("Username: @\(user.username)")

                    LabeledContent("Member Since") {
                        Text(user.createdAt, style: .date)
                            .foregroundStyle(.secondary)
                    }
                    .accessibilityLabel("Member since \(user.createdAt.formatted(date: .long, time: .omitted))")
                }
            }

            if let error = errorMessage {
                Section {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.footnote)
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
                .disabled(isSaving)
            }

            ToolbarItem(placement: .confirmationAction) {
                if isSaving {
                    ProgressView()
                } else {
                    Button("Save") {
                        Task {
                            await saveProfile()
                        }
                    }
                    .disabled(!hasChanges || !isValid)
                }
            }
        }
        .onAppear {
            displayName = authManager.currentUser?.displayName ?? ""
        }
        .alert("Profile Updated", isPresented: $showingSuccess) {
            Button("OK") {
                dismiss()
            }
        } message: {
            Text("Your profile has been updated successfully.")
        }
        .interactiveDismissDisabled(isSaving)
    }

    private func saveProfile() async {
        guard hasChanges && isValid else { return }

        isSaving = true
        errorMessage = nil

        do {
            try await authManager.updateProfile(displayName: displayName.trimmingCharacters(in: .whitespaces))
            showingSuccess = true
        } catch let error as NetworkError {
            errorMessage = error.userMessage
        } catch {
            errorMessage = "Failed to update profile. Please try again."
        }

        isSaving = false
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        EditProfileView()
            .environment(AuthManager())
    }
}
