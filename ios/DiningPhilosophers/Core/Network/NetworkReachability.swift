// NetworkReachability.swift
// Network reachability monitoring for iOS app
//
// Created by iOS Native Agent - Phase 2

import Foundation
import Network

/// Network reachability status
enum ReachabilityStatus: Equatable, Sendable {
    case unknown
    case connected(ConnectionType)
    case disconnected

    enum ConnectionType: Sendable {
        case wifi
        case cellular
        case wired
        case other

        init(from interface: NWInterface.InterfaceType) {
            switch interface {
            case .wifi:
                self = .wifi
            case .cellular:
                self = .cellular
            case .wiredEthernet:
                self = .wired
            default:
                self = .other
            }
        }
    }

    var isConnected: Bool {
        if case .connected = self { return true }
        return false
    }

    var connectionType: ConnectionType? {
        if case .connected(let type) = self { return type }
        return nil
    }
}

/// Network reachability monitor using NWPathMonitor
@MainActor
final class NetworkReachability: ObservableObject {
    /// Shared singleton instance
    static let shared = NetworkReachability()

    /// Current reachability status (published for SwiftUI)
    @Published private(set) var status: ReachabilityStatus = .unknown

    /// Whether the network is currently reachable
    var isReachable: Bool {
        status.isConnected
    }

    /// Current connection type (if connected)
    var connectionType: ReachabilityStatus.ConnectionType? {
        status.connectionType
    }

    // Private properties
    private let monitor: NWPathMonitor
    private let monitorQueue = DispatchQueue(label: "ai.diningphilosophers.network.monitor")
    private var isMonitoring = false

    // Callbacks for non-SwiftUI usage
    private var statusChangeCallbacks: [(ReachabilityStatus) -> Void] = []

    private init() {
        self.monitor = NWPathMonitor()
    }

    // MARK: - Public API

    /// Start monitoring network reachability
    func startMonitoring() {
        guard !isMonitoring else { return }

        monitor.pathUpdateHandler = { [weak self] path in
            Task { @MainActor [weak self] in
                guard let self else { return }

                let newStatus = Self.statusFromPath(path)

                if newStatus != self.status {
                    self.status = newStatus
                    self.notifyStatusChange(newStatus)
                }
            }
        }

        monitor.start(queue: monitorQueue)
        isMonitoring = true
    }

    /// Stop monitoring network reachability
    func stopMonitoring() {
        guard isMonitoring else { return }

        monitor.cancel()
        isMonitoring = false
    }

    /// Add a callback to be notified of status changes
    /// - Parameter callback: Closure called when status changes
    /// - Returns: A token that can be used to remove the callback
    @discardableResult
    func onStatusChange(_ callback: @escaping (ReachabilityStatus) -> Void) -> UUID {
        let token = UUID()
        statusChangeCallbacks.append(callback)
        return token
    }

    /// Check reachability synchronously
    /// Note: For first check, may return .unknown if monitoring hasn't started
    func checkReachability() -> ReachabilityStatus {
        status
    }

    /// Wait for network to become available with timeout
    /// - Parameter timeout: Maximum time to wait in seconds
    /// - Returns: True if network became available, false if timeout
    func waitForConnection(timeout: TimeInterval = 30.0) async -> Bool {
        // If already connected, return immediately
        if isReachable {
            return true
        }

        // Start monitoring if not already
        if !isMonitoring {
            startMonitoring()
        }

        // Wait for connection with timeout
        return await withCheckedContinuation { continuation in
            var didResume = false

            // Set up timeout
            let timeoutTask = Task {
                try? await Task.sleep(nanoseconds: UInt64(timeout * 1_000_000_000))
                if !didResume {
                    didResume = true
                    continuation.resume(returning: false)
                }
            }

            // Set up status change observer
            onStatusChange { newStatus in
                if newStatus.isConnected && !didResume {
                    didResume = true
                    timeoutTask.cancel()
                    continuation.resume(returning: true)
                }
            }
        }
    }

    // MARK: - Private Helpers

    private static func statusFromPath(_ path: NWPath) -> ReachabilityStatus {
        switch path.status {
        case .satisfied:
            // Determine connection type
            if path.usesInterfaceType(.wifi) {
                return .connected(.wifi)
            } else if path.usesInterfaceType(.cellular) {
                return .connected(.cellular)
            } else if path.usesInterfaceType(.wiredEthernet) {
                return .connected(.wired)
            } else {
                return .connected(.other)
            }

        case .unsatisfied, .requiresConnection:
            return .disconnected

        @unknown default:
            return .unknown
        }
    }

    private func notifyStatusChange(_ status: ReachabilityStatus) {
        for callback in statusChangeCallbacks {
            callback(status)
        }
    }
}

// MARK: - Convenience Extensions

extension NetworkReachability {
    /// Check if using expensive connection (cellular)
    var isExpensiveConnection: Bool {
        connectionType == .cellular
    }

    /// Check if on WiFi
    var isOnWiFi: Bool {
        connectionType == .wifi
    }

    /// Human-readable status description
    var statusDescription: String {
        switch status {
        case .unknown:
            return "Checking network..."
        case .connected(let type):
            switch type {
            case .wifi:
                return "Connected via WiFi"
            case .cellular:
                return "Connected via Cellular"
            case .wired:
                return "Connected via Ethernet"
            case .other:
                return "Connected"
            }
        case .disconnected:
            return "No internet connection"
        }
    }
}

// MARK: - Network Constrained Path Checking

extension NetworkReachability {
    /// Check if network path is constrained (low data mode)
    /// Useful for deciding whether to download large assets
    func isConstrained() -> Bool {
        let path = NWPathMonitor().currentPath
        return path.isConstrained
    }

    /// Check if network path is expensive (metered)
    func isExpensive() -> Bool {
        let path = NWPathMonitor().currentPath
        return path.isExpensive
    }
}
