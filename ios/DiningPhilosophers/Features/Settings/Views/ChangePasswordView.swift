// ChangePasswordView.swift
// View for changing user's password
//
// Created by iOS Native Agent - Phase 7

import SwiftUI

/// View for changing the user's password
struct ChangePasswordView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var currentPassword = ""
    @State private var newPassword = ""
    @State private var confirmPassword = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingSuccessAlert = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    SecureField("Current Password", text: $currentPassword)
                        .textContentType(.password)
                        .accessibilityLabel("Current password")
                } header: {
                    Text("Current Password")
                } footer: {
                    Text("Enter your current password to verify your identity.")
                }

                Section {
                    SecureField("New Password", text: $newPassword)
                        .textContentType(.newPassword)
                        .accessibilityLabel("New password")

                    SecureField("Confirm Password", text: $confirmPassword)
                        .textContentType(.newPassword)
                        .accessibilityLabel("Confirm new password")
                } header: {
                    Text("New Password")
                } footer: {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Password must be at least 8 characters long.")
                        if !passwordsMatch && !confirmPassword.isEmpty {
                            Text("Passwords do not match.")
                                .foregroundStyle(.red)
                        }
                    }
                }
            }
            .navigationTitle("Change Password")
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
                            await changePassword()
                        }
                    }
                    .disabled(!isValid || isLoading)
                }
            }
            .alert("Error", isPresented: .constant(errorMessage != nil)) {
                Button("OK") {
                    errorMessage = nil
                }
            } message: {
                Text(errorMessage ?? "")
            }
            .alert("Password Changed", isPresented: $showingSuccessAlert) {
                Button("OK") {
                    dismiss()
                }
            } message: {
                Text("Your password has been changed successfully.")
            }
            .disabled(isLoading)
            .overlay {
                if isLoading {
                    ProgressView("Changing password...")
                        .padding()
                        .background(.regularMaterial)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }
        }
    }

    // MARK: - Computed Properties

    private var passwordsMatch: Bool {
        newPassword == confirmPassword
    }

    private var isValid: Bool {
        !currentPassword.isEmpty &&
        newPassword.count >= 8 &&
        passwordsMatch
    }

    // MARK: - Actions

    @MainActor
    private func changePassword() async {
        guard isValid else { return }

        isLoading = true
        errorMessage = nil

        do {
            try await APIClient.shared.changePassword(
                currentPassword: currentPassword,
                newPassword: newPassword
            )
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
    ChangePasswordView()
}
