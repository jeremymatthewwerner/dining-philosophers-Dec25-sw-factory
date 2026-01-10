// NetworkMonitor.swift
// Network reachability monitoring using Network framework
//
// Created by iOS Native Agent

import Foundation
import Network
import Combine

/// Network reachability monitor using the Network framework
@MainActor
@Observable
final class NetworkMonitor {
    /// Shared instance for app-wide network monitoring
    static let shared = NetworkMonitor()

    /// Current network status
    private(set) var isConnected = true

    /// Current connection type
    private(set) var connectionType: ConnectionType = .unknown

    /// Publisher for connection status changes
    let statusPublisher = PassthroughSubject<Bool, Never>()

    private let monitor: NWPathMonitor
    private let queue = DispatchQueue(label: "ai.diningphilosophers.networkmonitor")

    private init() {
        monitor = NWPathMonitor()
        startMonitoring()
    }

    deinit {
        stopMonitoring()
    }

    // MARK: - Monitoring Control

    /// Start monitoring network changes
    private func startMonitoring() {
        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor [weak self] in
                guard let self else { return }

                let wasConnected = self.isConnected
                self.isConnected = path.status == .satisfied
                self.connectionType = self.determineConnectionType(path)

                // Notify subscribers if status changed
                if wasConnected != self.isConnected {
                    self.statusPublisher.send(self.isConnected)
                }
            }
        }

        monitor.start(queue: queue)
    }

    /// Stop monitoring network changes
    private func stopMonitoring() {
        monitor.cancel()
    }

    // MARK: - Connection Type Detection

    private func determineConnectionType(_ path: NWPath) -> ConnectionType {
        if path.usesInterfaceType(.wifi) {
            return .wifi
        } else if path.usesInterfaceType(.cellular) {
            return .cellular
        } else if path.usesInterfaceType(.wiredEthernet) {
            return .ethernet
        } else if path.status == .satisfied {
            return .other
        } else {
            return .none
        }
    }

    // MARK: - Convenience Methods

    /// Check if currently connected to network
    var hasConnection: Bool {
        isConnected
    }

    /// Check if on a metered connection (cellular)
    var isMeteredConnection: Bool {
        connectionType == .cellular
    }

    /// Check if on a high-bandwidth connection (WiFi or Ethernet)
    var isHighBandwidth: Bool {
        connectionType == .wifi || connectionType == .ethernet
    }
}

// MARK: - Connection Type

extension NetworkMonitor {
    /// Types of network connections
    enum ConnectionType: String, Sendable {
        case wifi = "WiFi"
        case cellular = "Cellular"
        case ethernet = "Ethernet"
        case other = "Other"
        case none = "None"
        case unknown = "Unknown"

        /// Human-readable description
        var description: String {
            rawValue
        }

        /// Whether this connection type is typically fast
        var isFast: Bool {
            switch self {
            case .wifi, .ethernet:
                return true
            case .cellular, .other:
                return false
            case .none, .unknown:
                return false
            }
        }
    }
}

// MARK: - SwiftUI Integration

#if canImport(SwiftUI)
import SwiftUI

/// Environment key for network monitor
private struct NetworkMonitorKey: EnvironmentKey {
    static let defaultValue: NetworkMonitor = .shared
}

extension EnvironmentValues {
    /// Access to the network monitor from SwiftUI views
    var networkMonitor: NetworkMonitor {
        get { self[NetworkMonitorKey.self] }
        set { self[NetworkMonitorKey.self] = newValue }
    }
}
#endif
