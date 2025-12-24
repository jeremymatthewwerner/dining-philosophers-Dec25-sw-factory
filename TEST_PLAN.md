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

## 9. Backend Integration Tests

### 9.1 Authentication & Authorization

**test_logout** (backend/tests/test_api.py:198-204)
- Validates POST /auth/logout endpoint
- Verifies successful logout response message
- Edge case: Logout works without authentication (stateless JWT)

**test_login_after_registration** (backend/tests/test_integration_workflows.py:262-280)
- Register user → Login with same credentials
- Verifies token validity after login
- Validates authentication flow continuity

### 9.2 Conversation Management

**test_conversation_color_assignment_edge_cases** (backend/tests/test_api.py:428-480)
- Tests color assignment with 5 thinkers (maximum allowed)
- Validates custom color preservation (not overwritten by default)
- Edge case: All 5 thinkers receive unique colors from color array

**test_conversation_deletion_with_messages** (backend/tests/test_api.py:482-533)
- Creates conversation with 3 messages
- Deletes conversation and verifies cascade delete
- Edge case: Messages are deleted when parent conversation is deleted

**test_unauthorized_conversation_access** (backend/tests/test_api.py:535-577)
- User A creates conversation, User B attempts access
- Tests GET, POST (send message), DELETE from unauthorized user
- Validates: All operations return 404 (conversation isolation)

**test_send_message_to_nonexistent_conversation** (backend/tests/test_api.py:579-590)
- Attempts to POST message to invalid conversation ID
- Validates 404 response with "Conversation not found" error

### 9.3 Full User Journey Workflows

**test_full_user_journey** (backend/tests/test_integration_workflows.py:73-180)
- Complete 9-step workflow:
  1. Register user
  2. Verify user info (GET /auth/me)
  3. Create conversation with 2 thinkers
  4. Send 3 messages
  5. List conversations
  6. Get conversation with messages
  7. Delete conversation
  8. Verify deletion (list and get)
  9. Logout
- Validates: Entire user lifecycle from registration to cleanup

**test_multiple_users_isolated_conversations** (backend/tests/test_integration_workflows.py:182-260)
- Two users each create separate conversations
- Each user lists their conversations (sees only their own)
- User A attempts to access User B's conversation (blocked)
- Validates: Session-based conversation isolation

---

## Tricky Areas Requiring Extra Attention

1. **Message splitting timing** - Ensure delays feel natural, not too fast or slow
2. **Concurrent thinker responses** - Race conditions when multiple thinkers respond
3. **WebSocket state management** - Connection/disconnection edge cases
4. **Mention detection** - Avoid false positives (common words matching names)
5. **Extended thinking streaming** - Token accumulation and display throttling
6. **Conversation switching** - Clean up state from previous conversation
7. **Cross-user isolation** - Users must not access other users' conversations or sessions
