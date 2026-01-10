// ChatControlsView.swift
// Speed control and other chat controls
//
// Created by iOS Native Agent

import SwiftUI

/// Available speed options for conversation
enum ConversationSpeed: Double, CaseIterable, Identifiable {
    case normal = 1.0
    case fast = 2.0
    case fastest = 3.0

    var id: Double { rawValue }

    var label: String {
        switch self {
        case .normal: return "1x"
        case .fast: return "2x"
        case .fastest: return "3x"
        }
    }

    var accessibilityLabel: String {
        switch self {
        case .normal: return "Normal speed"
        case .fast: return "Double speed"
        case .fastest: return "Triple speed"
        }
    }
}

/// Speed selector control
struct SpeedControlView: View {
    @Binding var selectedSpeed: ConversationSpeed
    let onSpeedChange: (ConversationSpeed) -> Void

    var body: some View {
        Menu {
            ForEach(ConversationSpeed.allCases) { speed in
                Button {
                    selectedSpeed = speed
                    onSpeedChange(speed)
                } label: {
                    HStack {
                        Text(speed.label)
                        if speed == selectedSpeed {
                            Image(systemName: "checkmark")
                        }
                    }
                }
            }
        } label: {
            HStack(spacing: 4) {
                Image(systemName: "gauge.with.needle")
                Text(selectedSpeed.label)
                    .fontWeight(.medium)
            }
            .font(.caption)
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(.regularMaterial)
            .clipShape(Capsule())
        }
        .accessibilityLabel("Conversation speed")
        .accessibilityValue(selectedSpeed.accessibilityLabel)
        .accessibilityHint("Double tap to change speed")
    }
}

/// Segmented speed control (alternative style)
struct SpeedSegmentedControl: View {
    @Binding var selectedSpeed: ConversationSpeed
    let onSpeedChange: (ConversationSpeed) -> Void

    var body: some View {
        HStack(spacing: 0) {
            ForEach(ConversationSpeed.allCases) { speed in
                Button {
                    selectedSpeed = speed
                    onSpeedChange(speed)
                } label: {
                    Text(speed.label)
                        .font(.caption)
                        .fontWeight(speed == selectedSpeed ? .semibold : .regular)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(speed == selectedSpeed ? Color.accentColor : Color.clear)
                        .foregroundStyle(speed == selectedSpeed ? .white : .primary)
                }
                .accessibilityLabel(speed.accessibilityLabel)
                .accessibilityAddTraits(speed == selectedSpeed ? .isSelected : [])
            }
        }
        .background(Color(.systemGray5))
        .clipShape(Capsule())
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Conversation speed")
    }
}

/// Chat toolbar with all controls
struct ChatToolbarView: View {
    @Binding var speed: ConversationSpeed
    @Binding var isPaused: Bool
    let onSpeedChange: (ConversationSpeed) -> Void
    let onTogglePause: () -> Void

    var body: some View {
        HStack {
            SpeedControlView(selectedSpeed: $speed, onSpeedChange: onSpeedChange)

            Spacer()

            Button {
                onTogglePause()
            } label: {
                Image(systemName: isPaused ? "play.fill" : "pause.fill")
                    .font(.caption)
                    .padding(8)
                    .background(.regularMaterial)
                    .clipShape(Circle())
            }
            .accessibilityLabel(isPaused ? "Resume conversation" : "Pause conversation")
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }
}

// MARK: - Preview

#Preview("Speed Menu") {
    SpeedControlView(
        selectedSpeed: .constant(.normal),
        onSpeedChange: { _ in }
    )
    .padding()
}

#Preview("Speed Segmented") {
    SpeedSegmentedControl(
        selectedSpeed: .constant(.fast),
        onSpeedChange: { _ in }
    )
    .padding()
}

#Preview("Full Toolbar") {
    VStack {
        Spacer()
        ChatToolbarView(
            speed: .constant(.normal),
            isPaused: .constant(false),
            onSpeedChange: { _ in },
            onTogglePause: {}
        )
    }
}
