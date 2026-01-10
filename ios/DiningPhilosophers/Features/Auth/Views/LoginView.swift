// LoginView.swift
// Login and registration UI
//
// Created by iOS Native Agent

import SwiftUI

/// Login and registration view
struct LoginView: View {
    @Environment(AuthManager.self) private var authManager

    @State private var username = ""
    @State private var password = ""
    @State private var displayName = ""
    @State private var isRegistering = false
    @State private var errorMessage: String?
    @State private var isShowingError = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 32) {
                    // Logo and title
                    headerSection

                    // Form fields
                    formSection

                    // Action button
                    actionButton

                    // Toggle between login/register
                    toggleButton
                }
                .padding()
            }
            .navigationTitle(isRegistering ? "Create Account" : "Sign In")
            .alert("Error", isPresented: $isShowingError) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(errorMessage ?? "An unknown error occurred")
            }
            .disabled(authManager.isLoading)
        }
    }

    // MARK: - View Components

    private var headerSection: some View {
        VStack(spacing: 16) {
            Image(systemName: "bubble.left.and.bubble.right.fill")
                .font(.system(size: 60))
                .foregroundStyle(.tint)

            Text("Dining Philosophers")
                .font(.title)
                .fontWeight(.bold)

            Text("Chat with history's greatest thinkers")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding(.top, 40)
    }

    private var formSection: some View {
        VStack(spacing: 16) {
            TextField("Username", text: $username)
                .textFieldStyle(.roundedBorder)
                .textContentType(.username)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)

            SecureField("Password", text: $password)
                .textFieldStyle(.roundedBorder)
                .textContentType(isRegistering ? .newPassword : .password)

            if isRegistering {
                TextField("Display Name (optional)", text: $displayName)
                    .textFieldStyle(.roundedBorder)
                    .textContentType(.name)
            }
        }
    }

    private var actionButton: some View {
        Button {
            Task {
                await performAuth()
            }
        } label: {
            Group {
                if authManager.isLoading {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .tint(.white)
                } else {
                    Text(isRegistering ? "Create Account" : "Sign In")
                }
            }
            .frame(maxWidth: .infinity)
            .padding()
            .background(isFormValid ? Color.accentColor : Color.gray)
            .foregroundStyle(.white)
            .clipShape(RoundedRectangle(cornerRadius: 10))
        }
        .disabled(!isFormValid || authManager.isLoading)
    }

    private var toggleButton: some View {
        Button {
            withAnimation {
                isRegistering.toggle()
                errorMessage = nil
            }
        } label: {
            Text(isRegistering ? "Already have an account? Sign In" : "Don't have an account? Create one")
                .font(.callout)
        }
    }

    // MARK: - Helpers

    private var isFormValid: Bool {
        !username.trimmingCharacters(in: .whitespaces).isEmpty &&
        !password.isEmpty &&
        password.count >= 6
    }

    private func performAuth() async {
        errorMessage = nil

        do {
            if isRegistering {
                try await authManager.register(
                    username: username.trimmingCharacters(in: .whitespaces),
                    password: password,
                    displayName: displayName.isEmpty ? nil : displayName
                )
            } else {
                try await authManager.login(
                    username: username.trimmingCharacters(in: .whitespaces),
                    password: password
                )
            }
        } catch let error as APIError {
            errorMessage = error.localizedDescription
            isShowingError = true
        } catch {
            errorMessage = error.localizedDescription
            isShowingError = true
        }
    }
}

// MARK: - Preview

#Preview {
    LoginView()
        .environment(AuthManager())
}
