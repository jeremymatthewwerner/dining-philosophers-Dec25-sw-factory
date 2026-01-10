// ChatControlsView.swift
// Chat controls including speed slider and pause/resume
//
// Created by iOS Native Agent

import SwiftUI

/// View displaying chat controls (speed, pause/resume)
struct ChatControlsView: View {
    @Binding var speed: Double
    @Binding var isPaused: Bool
    let onSpeedChange: (Double) -> Void
    let onTogglePause: () -> Void

    @State private var isExpanded = false

    var body: some View {
        VStack(spacing: 0) {
            // Toggle button to expand/collapse controls
            Button {
                withAnimation(.spring(response: 0.3)) {
                    isExpanded.toggle()
                }
            } label: {
                HStack {
                    Image(systemName: "slider.horizontal.3")
                    Text("Controls")
                        .font(.caption)
                    Spacer()
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption)
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
                .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)

            if isExpanded {
                VStack(spacing: 16) {
                    // Speed control
                    speedControl

                    // Pause/Resume button
                    pauseResumeButton
                }
                .padding()
                .background(.regularMaterial)
                .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .background(.regularMaterial)
    }

    // MARK: - View Components

    private var speedControl: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Conversation Speed")
                    .font(.subheadline)
                    .fontWeight(.medium)
                Spacer()
                Text(speedLabel)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(.secondary.opacity(0.2))
                    .clipShape(Capsule())
            }

            HStack {
                Image(systemName: "tortoise")
                    .foregroundStyle(.secondary)
                    .font(.caption)

                Slider(value: $speed, in: 0.5...3.0, step: 0.25) { editing in
                    if !editing {
                        onSpeedChange(speed)
                    }
                }
                .tint(.accentColor)

                Image(systemName: "hare")
                    .foregroundStyle(.secondary)
                    .font(.caption)
            }
        }
    }

    private var pauseResumeButton: some View {
        Button {
            onTogglePause()
        } label: {
            HStack {
                Image(systemName: isPaused ? "play.fill" : "pause.fill")
                Text(isPaused ? "Resume Conversation" : "Pause Conversation")
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(isPaused ? Color.accentColor : Color.secondary.opacity(0.2))
            .foregroundStyle(isPaused ? .white : .primary)
            .clipShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
    }

    private var speedLabel: String {
        switch speed {
        case ...0.5:
            return "0.5x (Slow)"
        case 0.75:
            return "0.75x"
        case 1.0:
            return "1x (Normal)"
        case 1.25:
            return "1.25x"
        case 1.5:
            return "1.5x"
        case 2.0:
            return "2x (Fast)"
        case 2.5:
            return "2.5x"
        case 3.0...:
            return "3x (Very Fast)"
        default:
            return "\(String(format: "%.2g", speed))x"
        }
    }
}

// MARK: - Preview

#Preview {
    VStack {
        Spacer()
        ChatControlsView(
            speed: .constant(1.0),
            isPaused: .constant(false),
            onSpeedChange: { _ in },
            onTogglePause: { }
        )
    }
}
