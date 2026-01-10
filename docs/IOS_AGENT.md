# iOS Native Agent

## Overview

The iOS Native Agent is a specialized AI agent for building native iOS applications using Swift and SwiftUI. It has deep expertise in iOS platform development and integrates with the existing software factory to enable autonomous iOS development alongside the web application.

## Problem Statement

Adding native iOS development to an existing web project traditionally requires:
1. Hiring iOS specialists or contractors
2. Learning a completely different tech stack (Swift, Xcode, UIKit/SwiftUI)
3. Maintaining separate codebases with duplicated business logic
4. Managing App Store submissions and compliance

The iOS Native Agent enables autonomous iOS development without these barriers, working alongside other factory agents to build, test, and maintain native iOS code.

## Design Principles

### 1. Swift-First, Modern iOS
- **Swift 5.9+**: async/await, actors, structured concurrency
- **SwiftUI**: Declarative UI, @Observable, NavigationStack
- **iOS 17+**: Modern APIs, no legacy support burden
- **Swift Package Manager**: Native dependency management

### 2. Mirror Existing Architecture
- Swift models mirror backend Pydantic schemas
- Network layer connects to existing FastAPI endpoints
- Same authentication flow (JWT) as web app
- WebSocket integration for real-time features

### 3. Quality Over Speed
- Proper architecture (MVVM with @Observable)
- Comprehensive testing (XCTest, XCUITest)
- Accessibility from day one
- Localization-ready

## Trigger Mechanism

### Primary: @ios Mention
```yaml
issue_comment:
  types: [created]
# Trigger when comment contains @ios
```

### Manual
```yaml
workflow_dispatch:
  inputs:
    issue_number:
      type: number
      description: 'Issue number to work on'
```

## Expertise Areas

### Swift & SwiftUI
- Async/await, actors, structured concurrency, Sendable
- @Observable for ViewModels
- NavigationStack, custom modifiers
- Combine integration with async/await

### iOS Platform
- Keychain Services for secure storage
- URLSession for networking and WebSockets
- Push Notifications with APNs
- App lifecycle management

### Architecture
- MVVM with @Observable
- Protocol-oriented programming
- Dependency injection via Environment
- Clean separation of concerns

### Build & Distribution
- Xcode project configuration
- Swift Package Manager
- Fastlane automation
- App Store Connect

## Project Structure

```
ios/
├── DiningPhilosophers/
│   ├── App/
│   │   ├── DiningPhilosophersApp.swift
│   │   └── AppDelegate.swift
│   ├── Features/
│   │   ├── Auth/
│   │   │   ├── Views/
│   │   │   │   ├── LoginView.swift
│   │   │   │   └── RegisterView.swift
│   │   │   ├── ViewModels/
│   │   │   │   └── AuthViewModel.swift
│   │   │   └── Services/
│   │   │       └── AuthService.swift
│   │   ├── Conversations/
│   │   │   ├── Views/
│   │   │   │   ├── ConversationListView.swift
│   │   │   │   └── ConversationRow.swift
│   │   │   └── ViewModels/
│   │   │       └── ConversationListViewModel.swift
│   │   ├── Chat/
│   │   │   ├── Views/
│   │   │   │   ├── ChatView.swift
│   │   │   │   └── MessageBubble.swift
│   │   │   ├── ViewModels/
│   │   │   │   └── ChatViewModel.swift
│   │   │   └── Services/
│   │   │       └── WebSocketService.swift
│   │   └── Settings/
│   │       ├── Views/
│   │       │   └── SettingsView.swift
│   │       └── ViewModels/
│   │           └── SettingsViewModel.swift
│   ├── Core/
│   │   ├── Network/
│   │   │   ├── APIClient.swift
│   │   │   ├── APIError.swift
│   │   │   ├── Endpoints.swift
│   │   │   └── WebSocketClient.swift
│   │   ├── Storage/
│   │   │   ├── KeychainService.swift
│   │   │   └── UserDefaultsService.swift
│   │   └── Extensions/
│   │       ├── Date+Extensions.swift
│   │       └── View+Extensions.swift
│   ├── Models/
│   │   ├── User.swift
│   │   ├── Conversation.swift
│   │   ├── Message.swift
│   │   ├── Thinker.swift
│   │   └── WebSocketMessage.swift
│   └── Resources/
│       ├── Assets.xcassets
│       ├── Localizable.strings
│       └── Info.plist
├── DiningPhilosophersTests/
│   ├── ViewModels/
│   │   ├── AuthViewModelTests.swift
│   │   └── ChatViewModelTests.swift
│   └── Services/
│       ├── APIClientTests.swift
│       └── KeychainServiceTests.swift
├── DiningPhilosophersUITests/
│   ├── AuthFlowTests.swift
│   └── ChatFlowTests.swift
└── Package.swift
```

## API Integration

### Type Mapping

The iOS Agent converts TypeScript/Pydantic types to Swift Codable structs:

```swift
// TypeScript (frontend/src/types/index.ts)
interface User {
  id: string;
  username: string;
  display_name: string | null;
  is_admin: boolean;
  total_spend: number;
  // ...
}

// Swift (ios/DiningPhilosophers/Models/User.swift)
struct User: Codable, Identifiable, Sendable {
    let id: String
    let username: String
    let displayName: String?
    let isAdmin: Bool
    let totalSpend: Decimal

    enum CodingKeys: String, CodingKey {
        case id, username
        case displayName = "display_name"
        case isAdmin = "is_admin"
        case totalSpend = "total_spend"
    }
}
```

### Network Layer

```swift
// APIClient with async/await
actor APIClient {
    static let shared = APIClient()
    private let baseURL = URL(string: "https://api.diningphilosophers.ai")!

    func fetch<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        var request = URLRequest(url: baseURL.appending(path: endpoint.path))
        request.httpMethod = endpoint.method.rawValue

        if let token = await TokenStorage.shared.retrieve() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw APIError.invalidResponse
        }

        return try JSONDecoder().decode(T.self, from: data)
    }
}
```

### WebSocket Integration

```swift
// WebSocketClient for real-time chat
actor WebSocketClient {
    private var webSocket: URLSessionWebSocketTask?

    func connect(conversationId: String) async throws {
        let url = URL(string: "wss://api.diningphilosophers.ai/ws/\(conversationId)")!
        var request = URLRequest(url: url)

        if let token = await TokenStorage.shared.retrieve() {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        webSocket = URLSession.shared.webSocketTask(with: request)
        webSocket?.resume()

        await receiveMessages()
    }

    func send(_ message: WSMessage) async throws {
        let data = try JSONEncoder().encode(message)
        try await webSocket?.send(.data(data))
    }

    private func receiveMessages() async {
        guard let webSocket else { return }

        do {
            let message = try await webSocket.receive()
            switch message {
            case .data(let data):
                let wsMessage = try JSONDecoder().decode(WSMessage.self, from: data)
                await handleMessage(wsMessage)
            case .string(let text):
                if let data = text.data(using: .utf8) {
                    let wsMessage = try JSONDecoder().decode(WSMessage.self, from: data)
                    await handleMessage(wsMessage)
                }
            @unknown default:
                break
            }
            await receiveMessages()
        } catch {
            // Handle disconnection
        }
    }
}
```

## Quality Gates

### Build Commands
```bash
# Build for simulator
xcodebuild -scheme DiningPhilosophers \
  -destination 'platform=iOS Simulator,name=iPhone 15' \
  build

# Run tests
xcodebuild test -scheme DiningPhilosophers \
  -destination 'platform=iOS Simulator,name=iPhone 15'

# SwiftLint
swiftlint lint --strict

# SwiftFormat
swiftformat --lint ios/
```

### Code Quality Standards
- No force unwraps (`!`) except where guaranteed
- Explicit error handling (Result or throws)
- All interactive elements have accessibility labels
- All user-facing strings use LocalizedStringKey

## Inter-Agent Communication

### Request Backend Changes
When the iOS app needs new API endpoints or schema changes:
```
@code please add endpoint /api/devices for push notification registration
```

### Request Production Diagnostics
When debugging API issues:
```
@devops please check backend logs for iOS client errors
```

### Escalate Architecture Questions
For decisions affecting both platforms:
```
@pe please review: Should we add real-time typing indicators to the API?
```

## CI/CD (macOS Runners)

For iOS builds, the workflow uses macOS runners:

```yaml
ios-build:
  runs-on: macos-14
  steps:
    - uses: actions/checkout@v4

    - name: Select Xcode
      run: sudo xcode-select -s /Applications/Xcode_15.2.app

    - name: Build
      run: |
        xcodebuild -scheme DiningPhilosophers \
          -destination 'platform=iOS Simulator,name=iPhone 15' \
          build

    - name: Test
      run: |
        xcodebuild test -scheme DiningPhilosophers \
          -destination 'platform=iOS Simulator,name=iPhone 15'
```

## Progress Comment Format

The iOS Agent maintains a progress comment:

```markdown
## 📱 iOS Native Agent Progress

- [x] 📖 Reading issue and understanding iOS requirements
- [x] 🔍 Analyzing backend API for iOS integration
- [x] 📐 Designing Swift data models and architecture
- [ ] 🛠️ Implementing iOS code: Creating ChatView
- [ ] ✅ Running Swift tests and linters
- [ ] 📝 Creating PR

**Status:** Implementing real-time chat with WebSocket...
**Workflow:** [View logs](...)

---
## 📋 Activity Log

| Time | Event |
|------|-------|
| 2026-01-10 12:00 UTC | 🚀 iOS Native Agent started |
| 2026-01-10 12:02 UTC | 📖 Analyzed issue: Add chat feature |
| 2026-01-10 12:05 UTC | 🔍 Reviewed WebSocket protocol |
| 2026-01-10 12:10 UTC | 📐 Designed ChatViewModel architecture |
| 2026-01-10 12:20 UTC | 🛠️ Implementing ChatView with SwiftUI |

---
## 📐 Architecture

### Components
- ChatView: SwiftUI view with message list and input
- ChatViewModel: @Observable with WebSocket connection
- WebSocketClient: Actor for thread-safe WS handling

### Files
- `ios/DiningPhilosophers/Features/Chat/Views/ChatView.swift`
- `ios/DiningPhilosophers/Features/Chat/ViewModels/ChatViewModel.swift`
```

## Escalation

The iOS Agent escalates to Principal Engineer (`@pe`) when:
- Stuck >30min on iOS-specific issue
- Architecture decisions affecting both platforms
- Security decisions (certificate pinning, token handling)
- App Store policy compliance questions

## Success Criteria

1. **Feature Parity**: iOS app covers core functionality
2. **Code Quality**: All code passes SwiftLint, tests pass
3. **Performance**: Smooth 60fps UI, efficient networking
4. **Accessibility**: Full VoiceOver support
5. **Autonomy**: >80% of iOS issues resolved without human intervention
