// ConnectionStatusBanner.swift
// Banner showing WebSocket connection status
//
// Created by iOS Native Agent

import SwiftUI

/// Banner displaying connection status when disconnected or reconnecting
struct ConnectionStatusBanner: View {
    let connectionState: WebSocketConnectionState

    var body: some View {
        Group {
            switch connectionState {
            case .connected:
                EmptyView()

            case .connecting:
                bannerContent(
                    icon: "wifi",
                    message: "Connecting...",
                    color: .orange,
                    showProgress: true
                )

            case .disconnected:
                bannerContent(
                    icon: "wifi.slash",
                    message: "Disconnected - Tap to reconnect",
                    color: .red,
                    showProgress: false
                )

            case .reconnecting(let attempt):
                bannerContent(
                    icon: "arrow.triangle.2.circlepath",
                    message: "Reconnecting (attempt \(attempt)/5)...",
                    color: .orange,
                    showProgress: true
                )
            }
        }
        .animation(.easeInOut(duration: 0.3), value: connectionState)
    }

    private func bannerContent(
        icon: String,
        message: String,
        color: Color,
        showProgress: Bool
    ) -> some View {
        HStack(spacing: 8) {
            if showProgress {
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    .scaleEffect(0.8)
            } else {
                Image(systemName: icon)
            }

            Text(message)
                .font(.caption)
                .fontWeight(.medium)

            Spacer()
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(color)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(message)
    }
}

/// Compact connection indicator (small dot in toolbar)
struct ConnectionIndicator: View {
    let connectionState: WebSocketConnectionState

    var body: some View {
        Circle()
            .fill(indicatorColor)
            .frame(width: 8, height: 8)
            .overlay {
                if isAnimating {
                    Circle()
                        .stroke(indicatorColor.opacity(0.5), lineWidth: 2)
                        .scaleEffect(1.5)
                        .opacity(0)
                        .animation(
                            .easeOut(duration: 1.0)
                                .repeatForever(autoreverses: false),
                            value: isAnimating
                        )
                }
            }
            .accessibilityLabel(accessibilityLabel)
    }

    private var indicatorColor: Color {
        switch connectionState {
        case .connected:
            return .green
        case .connecting, .reconnecting:
            return .orange
        case .disconnected:
            return .red
        }
    }

    private var isAnimating: Bool {
        switch connectionState {
        case .connecting, .reconnecting:
            return true
        default:
            return false
        }
    }

    private var accessibilityLabel: String {
        switch connectionState {
        case .connected:
            return "Connected"
        case .connecting:
            return "Connecting"
        case .disconnected:
            return "Disconnected"
        case .reconnecting(let attempt):
            return "Reconnecting, attempt \(attempt)"
        }
    }
}

/// New messages indicator shown when user has scrolled up
struct NewMessagesIndicator: View {
    let messageCount: Int
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 6) {
                Image(systemName: "arrow.down")
                    .font(.caption2)

                Text(messageCount == 1 ? "1 new message" : "\(messageCount) new messages")
                    .font(.caption)
                    .fontWeight(.medium)
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color.accentColor)
            .clipShape(Capsule())
            .shadow(radius: 4)
        }
        .transition(.move(edge: .bottom).combined(with: .opacity))
        .accessibilityLabel("\(messageCount) new messages, tap to scroll to bottom")
    }
}

// MARK: - Preview

#Preview("Disconnected") {
    VStack {
        ConnectionStatusBanner(connectionState: .disconnected)
        Spacer()
    }
}

#Preview("Reconnecting") {
    VStack {
        ConnectionStatusBanner(connectionState: .reconnecting(attempt: 2))
        Spacer()
    }
}

#Preview("Indicator") {
    HStack(spacing: 20) {
        ConnectionIndicator(connectionState: .connected)
        ConnectionIndicator(connectionState: .connecting)
        ConnectionIndicator(connectionState: .disconnected)
    }
    .padding()
}

#Preview("New Messages") {
    VStack {
        Spacer()
        NewMessagesIndicator(messageCount: 3, onTap: {})
            .padding()
    }
}
