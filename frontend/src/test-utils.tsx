/**
 * Shared test utilities and helper functions
 *
 * Reduces test duplication across multiple test files by providing
 * reusable builders, factories, and helper functions.
 */

import React from 'react';
import { render as rtlRender, RenderOptions } from '@testing-library/react';
import { AuthProvider, LanguageProvider } from '@/contexts';

/**
 * Custom render function that wraps components with necessary providers.
 *
 * This ensures all components have access to AuthContext and LanguageContext
 * during testing, preventing "useLanguage must be used within a LanguageProvider" errors.
 */
function AllTheProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <LanguageProvider>{children}</LanguageProvider>
    </AuthProvider>
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
