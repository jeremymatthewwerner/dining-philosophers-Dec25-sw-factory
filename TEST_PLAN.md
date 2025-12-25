# Test Plan - Dining Philosophers

This document outlines all features requiring testing, their test cases, and edge conditions.

## 1. Conversation Management

### 1.1 Create Conversation
**Setup**: Clean browser state, backend running
**Happy Path**:
- [ ] Click "New Chat" opens modal
- [ ] Enter topic and number of thinkers
- [ ] System suggests appropriate thinkers
- [ ] Accept suggestions creates conversation
- [ ] Conversation appears in sidebar

**Edge Cases**:
- [ ] Empty topic validation
- [ ] Invalid thinker count (0, negative, > max)
- [ ] API failure during thinker suggestions
- [ ] Network timeout handling

### 1.2 List Conversations
**Happy Path**:
- [ ] Conversations display in sidebar
- [ ] Sorted by most recent
- [ ] Shows thinker avatars
- [ ] Shows message count and cost

**Edge Cases**:
- [ ] Empty conversation list
- [ ] Very long conversation names (truncation + tooltip)
- [ ] Many conversations (scrolling)

### 1.3 Select Conversation
**Happy Path**:
- [ ] Click conversation loads messages
- [ ] Status indicator updates (running/paused/inactive)
- [ ] WebSocket connects

**Edge Cases**:
- [ ] Switch between conversations rapidly
- [ ] Select conversation while another is loading

### 1.4 Delete Conversation
**Happy Path**:
- [ ] Delete button appears on hover
- [ ] Click deletes conversation
- [ ] Conversation removed from sidebar
- [ ] If current, redirects to welcome state

**Edge Cases**:
- [ ] Delete while messages loading
- [ ] Delete the only conversation

## 2. Thinker Selection

### 2.1 Suggest Thinkers
**Happy Path**:
- [ ] Topic generates relevant suggestions
- [ ] Multiple thinkers with diverse viewpoints
- [ ] Profile info displayed (bio, style)

**Edge Cases**:
- [ ] Very niche topic
- [ ] Ambiguous topic
- [ ] API timeout

### 2.2 Swap Thinker
**Happy Path**:
- [ ] Swap button requests new suggestion
- [ ] New thinker replaces old one

### 2.3 Custom Thinker
**Happy Path**:
- [ ] Type custom name validates against real person
- [ ] Profile generated for valid person

**Edge Cases**:
- [ ] Fictional character (should fail validation)
- [ ] Misspelled name
- [ ] Very obscure historical figure

## 3. Chat Interface

### 3.1 Send Message
**Happy Path**:
- [ ] Type message and send
- [ ] Message appears in chat
- [ ] Thinkers respond

**Edge Cases**:
- [ ] Empty message
- [ ] Very long message
- [ ] Rapid message sending
- [ ] Send while disconnected

### 3.2 Receive Messages
**Happy Path**:
- [ ] Messages appear in real-time
- [ ] Auto-scroll to new messages
- [ ] Thinker name and avatar displayed
- [ ] Timestamp and cost shown

**Edge Cases**:
- [ ] Many messages at once
- [ ] Very long messages
- [ ] Messages with special characters

### 3.3 Message Splitting
**Happy Path**:
- [ ] Long responses split into multiple bubbles
- [ ] Bubbles appear with typing delay between them
- [ ] Can be interleaved with other messages

**Edge Cases**:
- [ ] Very short response (no split needed)
- [ ] Response with no sentence boundaries
- [ ] Pause during multi-bubble delivery

### 3.4 Mention Highlighting
**Happy Path**:
- [ ] Thinker names in messages are highlighted
- [ ] Inline avatar appears with name
- [ ] Works for full name and first name

**Edge Cases**:
- [ ] Partial name match
- [ ] Name in different case
- [ ] Multiple mentions in one message
- [ ] Self-mention (thinker mentioning themselves)

### 3.5 Typing Indicators
**Happy Path**:
- [ ] Shows when thinker is typing
- [ ] Displays thinking preview (extended thinking)
- [ ] Updates in real-time
- [ ] Disappears when message sent

**Edge Cases**:
- [ ] Multiple thinkers typing simultaneously
- [ ] Very long thinking preview text

## 4. Pause/Resume

### 4.1 Pause Conversation
**Happy Path**:
- [ ] Pause button pauses all thinkers
- [ ] Status indicator shows paused
- [ ] No new messages while paused

### 4.2 Resume Conversation
**Happy Path**:
- [ ] Resume button resumes thinkers
- [ ] Messages start flowing again

## 5. Cost Tracking

### 5.1 Cost Meter
**Happy Path**:
- [ ] Shows cumulative cost since page load
- [ ] Updates in real-time with new messages

**Edge Cases**:
- [ ] Very high cost (formatting)
- [ ] Zero cost

### 5.2 Per-Message Cost
**Happy Path**:
- [ ] Each thinker message shows cost
- [ ] Cost breakdown per bubble (when split)

## 6. Real-Time Communication

### 6.1 WebSocket Connection
**Happy Path**:
- [ ] Connects when conversation selected
- [ ] Reconnects on disconnect

**Edge Cases**:
- [ ] Server restart
- [ ] Network interruption
- [ ] Browser tab sleep/wake

### 6.2 Multiple Thinkers Responding
**Happy Path**:
- [ ] Multiple thinkers can respond concurrently
- [ ] No message loss or ordering issues

## 7. Navigation & State

### 7.1 Browser Refresh
**Happy Path**:
- [ ] Conversation persists after refresh
- [ ] Returns to same conversation

### 7.2 Direct URL Access
**Happy Path**:
- [ ] Can access conversation by URL (if implemented)

## 8. Error Handling

### 8.1 API Errors
- [ ] Graceful error display
- [ ] Retry options where appropriate

### 8.2 Network Errors
- [ ] Offline indicator
- [ ] Reconnection handling

---

## Tricky Areas Requiring Extra Attention

1. **Message splitting timing** - Ensure delays feel natural, not too fast or slow
2. **Concurrent thinker responses** - Race conditions when multiple thinkers respond
3. **WebSocket state management** - Connection/disconnection edge cases
4. **Mention detection** - Avoid false positives (common words matching names)
5. **Extended thinking streaming** - Token accumulation and display throttling
6. **Conversation switching** - Clean up state from previous conversation

---

## E2E Edge Case Tests (Added Dec 25, 2025)

### Form Validation Tests (frontend/e2e/form-validation.spec.ts)
Comprehensive input validation and edge cases for all forms.

**New Conversation Form:**
- **Next button disabled with empty topic** - Validates required field enforcement
- **Validates whitespace-only topic** - Ensures whitespace doesn't bypass validation
- **Accepts very short topic (1 character)** - Tests minimum length boundary
- **Handles very long topic (500+ characters)** - Tests maximum length handling
- **Create button disabled without selected thinkers** - Validates thinker requirement

**Registration Form:**
- **Shows error for empty username** - HTML5 validation or custom error
- **Shows error for empty display name** - Required field validation
- **Shows error for mismatched passwords** - Password confirmation logic
- **Accepts username with valid characters** - Format validation (underscores, numbers)
- **Shows error for short password** - Minimum password length enforcement

**Login Form:**
- **Shows error for empty credentials** - Required field validation
- **Shows error for invalid credentials** - Authentication error handling

### Input Edge Cases Tests (frontend/e2e/edge-cases-input.spec.ts)
Tests special characters, extreme inputs, and security validation.

**Special Characters in Topic:**
- **Handles unicode and emojis in topic** - Emoji support (🤔 📚)
- **Handles special characters in topic** - Quotes, brackets, ampersands
- **Handles potential SQL injection in topic** - Security: `'; DROP TABLE` attempts

**Special Characters in Messages:**
- **Handles emojis in messages** - Message emoji support (👋 🤔)
- **Handles markdown-like syntax in messages** - **bold**, _italic_, `code`, [links]
- **Handles potential XSS in messages** - Security: `<script>` tag sanitization
- **Handles very long message (10,000+ characters)** - Extreme length handling

**Invalid Custom Thinker Names:**
- **Rejects nonsensical thinker name** - Validation: "asdfjkl12345"
- **Rejects fictional character** - Validation: "Harry Potter" should fail
- **Handles empty custom thinker name** - Empty input handling
- **Handles thinker name with only whitespace** - Whitespace-only validation

### Error Handling Tests (frontend/e2e/error-handling.spec.ts)
Robustness testing and error recovery scenarios.

**Rapid Actions and Race Conditions:**
- **Prevents duplicate messages from rapid send button clicking** - Click spam protection
- **Handles delete conversation while messages are loading** - Race condition handling
- **Handles rapid conversation switching** - State cleanup on rapid navigation

**API Error Handling:**
- **Handles network error during conversation creation** - Offline API call handling
- **Handles network error during message send** - Offline message sending

**Session and Authentication:**
- **Handles invalid token gracefully** - Expired/invalid JWT handling

**Empty State Handling:**
- **Handles sending empty message** - Empty message rejection
- **Handles sending whitespace-only message** - Whitespace message rejection

**Error Recovery:**
- **Can recover from failed conversation creation** - Retry after network failure

### WebSocket Edge Cases Tests (frontend/e2e/websocket-edge-cases.spec.ts)
Real-time communication robustness and connection management.

**WebSocket Connection Management:**
- **Maintains conversation state after page refresh** - State persistence
- **Reconnects WebSocket after connection drop** - Auto-reconnection logic
- **Handles switching conversations (WebSocket cleanup)** - Proper connection cleanup

**WebSocket During Operations:**
- **Handles pause button click** - Pause/resume during active connection
- **Handles navigation away during message send** - Mid-send navigation cleanup

**WebSocket State Persistence:**
- **Preserves pause state across page refresh** - Pause state persistence
- **Handles multiple rapid pause/resume clicks** - Rapid toggle handling

**Offline Behavior:**
- **Shows appropriate feedback when sending message offline** - Offline error handling
- **Recovers when going back online** - Reconnection and message retry

### State Management Edge Cases Tests (frontend/e2e/state-edge-cases.spec.ts)
Multi-tab behavior, state consistency, and navigation edge cases.

**Multi-Tab Synchronization:**
- **Can view same conversation in two tabs simultaneously** - Multi-tab support
- **Deleting conversation in one tab affects other tab** - Cross-tab state sync

**Cost Tracking Accuracy:**
- **Cost meter shows zero initially** - Initial state validation
- **Cost meter updates when messages are sent** - Real-time cost tracking
- **Cost accumulates across multiple messages** - Cost accumulation logic

**Conversation State Persistence:**
- **Conversation list persists after refresh** - Browser refresh persistence
- **Returns to same conversation after refresh** - Active conversation restoration
- **Handles rapid conversation creation** - Stress test: multiple quick creations

**Browser Navigation:**
- **Handles browser back button** - Back button navigation
- **Handles browser forward button** - Forward button navigation
- **Handles direct URL access to conversation** - Deep linking support

**Empty State Recovery:**
- **Handles deleting all conversations** - Empty state after mass deletion

### Test Coverage Summary

**Total new E2E tests added:** 66 tests across 5 files

**Coverage areas:**
- ✅ Form validation and input constraints
- ✅ Special characters and unicode handling
- ✅ Security (SQL injection, XSS attempts)
- ✅ Extreme inputs (very long text, rapid actions)
- ✅ Network errors and offline scenarios
- ✅ WebSocket connection management
- ✅ Multi-tab synchronization
- ✅ Browser navigation (back/forward/refresh)
- ✅ State persistence and recovery
- ✅ Race conditions and concurrent operations

**Edge cases now comprehensively tested:**
- Empty/whitespace inputs
- Maximum length inputs
- Rapid repeated actions (spam clicking, rapid switching)
- Network disconnection and recovery
- Invalid authentication tokens
- Multi-tab concurrent operations
- Browser history navigation
- Cost tracking accuracy
- Pause state persistence
