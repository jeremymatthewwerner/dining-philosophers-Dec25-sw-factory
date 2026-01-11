// ChangePasswordView.swift
// View for changing user password
//
// Created by iOS Native Agent - Phase 7

import SwiftUI

/// View for changing user password
struct ChangePasswordView: View {
    @Environment(AuthManager.self) private var authManager
    @Environment(\.dismiss) private var dismiss

    @State private var currentPassword = ""
    @State private var newPassword = ""
    @State private var confirmPassword = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var showingSuccess = false

    @FocusState private var focusedField: Field?

    enum Field {
        case currentPassword
        case newPassword
        case confirmPassword
    }

    private var isValid: Bool {
        !currentPassword.isEmpty &&
        !newPassword.isEmpty &&
        newPassword.count >= 8 &&
        newPassword == confirmPassword
    }

    private var validationMessage: String? {
        if !currentPassword.isEmpty && !newPassword.isEmpty {
            if newPassword.count < 8 {
                return "New password must be at least 8 characters"
            }
            if !confirmPassword.isEmpty && newPassword != confirmPassword {
                return "Passwords do not match"
            }
        }
        return nil
    }

    var body: some View {
        Form {
            Section {
                SecureField("Current Password", text: $currentPassword)
                    .textContentType(.password)
                    .focused($focusedField, equals: .currentPassword)
                    .accessibilityLabel("Current password")
                    .accessibilityHint("Enter your current password")
            } header: {
                Text("Current Password")
            }

            Section {
                SecureField("New Password", text: $newPassword)
                    .textContentType(.newPassword)
                    .focused($focusedField, equals: .newPassword)
                    .accessibilityLabel("New password")
                    .accessibilityHint("Enter your new password, at least 8 characters")

                SecureField("Confirm Password", text: $confirmPassword)
                    .textContentType(.newPassword)
                    .focused($focusedField, equals: .confirmPassword)
                    .accessibilityLabel("Confirm new password")
                    .accessibilityHint("Re-enter your new password")
            } header: {
                Text("New Password")
            } footer: {
                if let validation = validationMessage {
                    Text(validation)
                        .foregroundStyle(.orange)
                } else {
                    Text("Password must be at least 8 characters long.")
                }
            }

            if let error = errorMessage {
                Section {
                    Text(error)
                        .foregroundStyle(.red)
                        .font(.footnote)
                }
            }

            Section {
                Button {
                    Task {
                        await changePassword()
                    }
                } label: {
                    HStack {
                        Spacer()
                        if isSaving {
                            ProgressView()
                        } else {
                            Text("Change Password")
                        }
                        Spacer()
                    }
                }
                .disabled(!isValid || isSaving)
                .accessibilityLabel("Change password")
                .accessibilityHint(isValid ? "Double tap to change your password" : "Fill in all fields correctly to enable")
            }
        }
        .navigationTitle("Change Password")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Cancel") {
                    dismiss()
                }
                .disabled(isSaving)
            }
        }
        .alert("Password Changed", isPresented: $showingSuccess) {
            Button("OK") {
                dismiss()
            }
        } message: {
            Text("Your password has been changed successfully.")
        }
        .interactiveDismissDisabled(isSaving)
        .onAppear {
            focusedField = .currentPassword
        }
    }

    private func changePassword() async {
        guard isValid else { return }

        isSaving = true
        errorMessage = nil
        focusedField = nil

        do {
            try await authManager.changePassword(
                currentPassword: currentPassword,
                newPassword: newPassword
            )
            showingSuccess = true
        } catch let error as NetworkError {
            errorMessage = error.userMessage
            // Focus on current password if auth failed
            if error.requiresReauth || error == .unauthorized {
                focusedField = .currentPassword
            }
        } catch {
            errorMessage = "Failed to change password. Please try again."
        }

        isSaving = false
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ChangePasswordView()
            .environment(AuthManager())
    }
}
