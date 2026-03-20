/**
 * Shared test utilities and helper functions
 *
 * Reduces test duplication across multiple test files by providing
 * reusable builders, factories, and helper functions.
 */

import React from 'react';
import { render as rtlRender, RenderOptions } from '@testing-library/react';
import { AuthProvider, LanguageProvider, ThemeProvider } from '@/contexts';
import type { ConversationThinker } from '@/types';

/**
 * Custom render function that wraps components with necessary providers.
 *
 * This ensures all components have access to AuthContext, LanguageContext, and ThemeContext
 * during testing, preventing "useLanguage must be used within a LanguageProvider" errors.
 */
function AllTheProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <LanguageProvider>{children}</LanguageProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export function render(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return rtlRender(ui, { wrapper: AllTheProviders, ...options });
}

// Re-export everything from React Testing Library
export * from '@testing-library/react';

// Test data constants
export const TEST_USER_ID = 'user-123';
export const TEST_TOKEN = 'jwt-token-123';
export const TEST_TIMESTAMP = '2024-01-15T10:00:00Z';
export const TEST_CONVERSATION_ID = 'conv-123';
export const TEST_MESSAGE_ID = 'msg-1';

/**
 * Create a mock auth response for testing login/register flows.
 *
 * Reduces duplication in api.test.ts where this pattern appears 5+ times.
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock auth response object
 */
export function createAuthResponse(overrides: Record<string, unknown> = {}) {
  return {
    access_token: TEST_TOKEN,
    user: {
      id: TEST_USER_ID,
      username: 'testuser',
      display_name: 'Test User',
      is_admin: false,
      total_spend: 0,
      created_at: TEST_TIMESTAMP,
      ...(typeof overrides.user === 'object' ? overrides.user : {}),
    },
    ...overrides,
  };
}

/**
 * Create a mock thinker message for WebSocket testing.
 *
 * Reduces duplication in useWebSocket.test.tsx where this pattern
 * appears 8+ times with variations.
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock thinker message object
 */
export function createThinkerMessage(overrides: Record<string, unknown> = {}) {
  return {
    type: 'message',
    sender_type: 'thinker',
    sender_name: 'Socrates',
    content: 'I know that I know nothing.',
    message_id: TEST_MESSAGE_ID,
    conversation_id: TEST_CONVERSATION_ID,
    timestamp: TEST_TIMESTAMP,
    cost: 0.001,
    ...overrides,
  };
}

/**
 * Create a mock conversation object for testing.
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock conversation object
 */
export function createMockConversation(
  overrides: Record<string, unknown> = {}
) {
  return {
    id: TEST_CONVERSATION_ID,
    topic: 'Philosophy of Mind',
    status: 'active',
    created_at: TEST_TIMESTAMP,
    message_count: 0,
    total_cost: 0,
    thinkers: [
      {
        name: 'Socrates',
        bio: 'Ancient Greek philosopher',
        positions: 'Knowledge through questioning',
        style: 'Socratic method',
      },
    ],
    ...overrides,
  };
}

/**
 * Helper to set document.hidden property for visibility testing.
 *
 * Reduces duplication in useWebSocket.test.tsx where this pattern
 * appears 6+ times with identical structure.
 *
 * @param hidden - Whether document should be hidden
 */
export function setDocumentHidden(hidden: boolean) {
  Object.defineProperty(document, 'hidden', {
    writable: true,
    configurable: true,
    value: hidden,
  });
}

/**
 * Helper to dispatch visibility change event.
 *
 * Reduces duplication in useWebSocket.test.tsx where this is called
 * 7+ times, usually after setDocumentHidden.
 */
export function dispatchVisibilityChange() {
  document.dispatchEvent(new Event('visibilitychange'));
}

/**
 * Helper to simulate document becoming hidden (tab switch, minimize).
 *
 * Combines setDocumentHidden and dispatchVisibilityChange for convenience.
 */
export function simulateDocumentHidden() {
  setDocumentHidden(true);
  dispatchVisibilityChange();
}

/**
 * Helper to simulate document becoming visible (tab return, restore).
 *
 * Combines setDocumentHidden and dispatchVisibilityChange for convenience.
 */
export function simulateDocumentVisible() {
  setDocumentHidden(false);
  dispatchVisibilityChange();
}

/**
 * Mock localStorage with common auth token setup.
 *
 * Reduces duplication in api.test.ts where localStorage.getItem mock
 * appears 3+ times in beforeEach blocks.
 */
export function setupAuthToken(token: string = TEST_TOKEN) {
  (localStorage.getItem as jest.Mock).mockReturnValue(token);
}

/**
 * Create a mock fetch response for testing API calls.
 *
 * Reduces duplication in api.test.ts where mock fetch setup appears 10+ times.
 *
 * @param data - Response data
 * @param ok - Whether response is successful (default true)
 * @param status - HTTP status code (default 200)
 * @returns Mock fetch response
 */
export function createMockFetchResponse(
  data: unknown,
  ok: boolean = true,
  status: number = 200
) {
  return {
    ok,
    status,
    json: () => Promise.resolve(data),
  };
}

/**
 * Create a mock thinker suggestion for NewChatModal testing.
 *
 * Reduces duplication across component tests where this pattern appears
 * multiple times with similar structure.
 *
 * @param name - Thinker name (default: "Socrates")
 * @returns Mock thinker suggestion object
 */
export function createThinkerSuggestion(name: string = 'Socrates') {
  return {
    name,
    reason: `${name} would be great`,
    profile: {
      name,
      bio: `Bio of ${name}`,
      positions: 'Some positions',
      style: 'Some style',
    },
  };
}

/**
 * Create default props for NewChatModal testing.
 *
 * Reduces duplication in NewChatModal.test.tsx and similar modal tests.
 *
 * @param overrides - Optional prop overrides
 * @returns Default props object
 */
export function createNewChatModalProps(
  overrides: Record<string, unknown> = {}
) {
  return {
    isOpen: true,
    onClose: jest.fn(),
    onCreate: jest.fn().mockResolvedValue(undefined),
    onSuggestThinkers: jest
      .fn()
      .mockResolvedValue([createThinkerSuggestion('Socrates')]),
    onValidateThinker: jest.fn().mockResolvedValue({
      name: 'Custom',
      bio: 'Bio',
      positions: 'Positions',
      style: 'Style',
    }),
    ...overrides,
  };
}

/**
 * Shared mock ConversationThinker array for @mention tests.
 *
 * Eliminates identical 30-line definitions duplicated in both
 * MentionAutocomplete.test.tsx and MessageInput.test.tsx.
 * Contains Socrates, Plato, and Friedrich Nietzsche to test
 * filtering, multi-word name handling, and navigation wrapping.
 */
export const mockConversationThinkers: ConversationThinker[] = [
  {
    id: '1',
    name: 'Socrates',
    bio: 'Greek philosopher',
    positions: 'Knowledge is virtue',
    style: 'Questioning',
    color: '#3B82F6',
    image_url: null,
  },
  {
    id: '2',
    name: 'Plato',
    bio: 'Greek philosopher',
    positions: 'Theory of Forms',
    style: 'Dialogic',
    color: '#10B981',
    image_url: null,
  },
  {
    id: '3',
    name: 'Friedrich Nietzsche',
    bio: 'German philosopher',
    positions: 'Will to power',
    style: 'Aphoristic',
    color: '#EF4444',
    image_url: null,
  },
];

/**
 * Create a mock Thinker object for testing.
 *
 * Reduces duplication of thinker object creation across component tests
 * (ChatArea.test.tsx, NewChatModal.test.tsx, etc.).
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock Thinker object
 */
export function createThinker(overrides: Record<string, unknown> = {}) {
  return {
    id: 'thinker-1',
    name: 'Socrates',
    bio: 'Ancient philosopher',
    positions: 'Socratic method',
    style: 'Questions everything',
    color: '#3B82F6',
    ...overrides,
  };
}

/**
 * Create a mock Conversation object for testing.
 *
 * Reduces duplication of conversation object creation across component tests
 * (ChatArea.test.tsx, MessageList.test.tsx, etc.).
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock Conversation object
 */
export function createConversation(overrides: Record<string, unknown> = {}) {
  return {
    id: TEST_CONVERSATION_ID,
    session_id: 'session-1',
    topic: 'Philosophy of Mind',
    thinkers: [createThinker()],
    messages: [],
    total_cost: 0,
    created_at: TEST_TIMESTAMP,
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Create a mock Message object for testing.
 *
 * Reduces duplication of message object creation across component tests
 * (ChatArea.test.tsx, MessageList.test.tsx, Message.test.tsx, etc.).
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock Message object
 */
export function createMessage(overrides: Record<string, unknown> = {}) {
  return {
    id: TEST_MESSAGE_ID,
    conversation_id: TEST_CONVERSATION_ID,
    sender_type: 'user' as const,
    sender_name: null,
    content: 'Test message content',
    cost: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * Create a mock ConversationSummary object for testing.
 *
 * Reduces duplication of conversation summary object creation in Sidebar tests,
 * ConversationList tests, etc.
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock ConversationSummary object
 */
export function createConversationSummary(
  overrides: Record<string, unknown> = {}
) {
  return {
    id: TEST_CONVERSATION_ID,
    topic: 'Philosophy of Mind',
    thinker_names: ['Socrates'],
    thinkers: [{ name: 'Socrates', image_url: null }],
    message_count: 5,
    total_cost: 0.01,
    created_at: TEST_TIMESTAMP,
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

/**
 * WebSocket Testing Helpers
 *
 * Reduces duplication of WebSocket simulation patterns that appear 49 times
 * in useWebSocket.test.tsx.
 */

/**
 * Create a mock typing indicator message for WebSocket testing.
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock typing indicator message
 */
export function createTypingIndicatorMessage(
  overrides: Record<string, unknown> = {}
) {
  return {
    type: 'typing_indicator',
    thinker_name: 'Socrates',
    thinking_preview: 'Pondering existence...',
    ...overrides,
  };
}

/**
 * Create a mock WebSocket error message for testing.
 *
 * @param overrides - Optional overrides for default values
 * @returns Mock error message
 */
export function createErrorMessage(overrides: Record<string, unknown> = {}) {
  return {
    type: 'error',
    message: 'An error occurred',
    ...overrides,
  };
}

/**
 * Create a mock pause/resume message for WebSocket testing.
 *
 * @param isPaused - Whether the conversation is paused
 * @returns Mock pause/resume message
 */
export function createPauseResumeMessage(isPaused: boolean) {
  return {
    type: isPaused ? 'paused' : 'resumed',
  };
}

/**
 * Helper to simulate a complete WebSocket message flow in tests.
 *
 * Reduces duplication of the "simulateOpen → simulateMessage → assert" pattern
 * that appears many times in useWebSocket.test.tsx.
 *
 * @param mockWsInstance - Mock WebSocket instance
 * @param message - Message to send
 * @param assertions - Optional assertions callback to run after message
 */
export function simulateWebSocketMessage(
  mockWsInstance: {
    simulateOpen: () => void;
    simulateMessage: (data: unknown) => void;
  },
  message: unknown,
  assertions?: () => void
) {
  mockWsInstance.simulateOpen();
  mockWsInstance.simulateMessage(message);
  if (assertions) {
    assertions();
  }
}

/**
 * Helper to simulate a WebSocket connection and send sequence in tests.
 *
 * Encapsulates the common pattern of:
 * 1. Render hook with conversationId
 * 2. Simulate WebSocket open
 * 3. Wait for connection
 * 4. Send messages
 *
 * @param mockWsInstance - Mock WebSocket instance
 * @param conversationId - Conversation ID to connect to
 * @returns Object with helper functions for the test scenario
 */
export function setupWebSocketScenario(
  mockWsInstance: {
    simulateOpen: () => void;
    simulateMessage: (data: unknown) => void;
    simulateClose: () => void;
    simulateError: () => void;
  },
  conversationId: string = TEST_CONVERSATION_ID
) {
  return {
    conversationId,
    sendMessage: (message: unknown) => {
      mockWsInstance.simulateMessage(message);
    },
    connect: () => {
      mockWsInstance.simulateOpen();
    },
    disconnect: () => {
      mockWsInstance.simulateClose();
    },
    triggerError: () => {
      mockWsInstance.simulateError();
    },
  };
}
