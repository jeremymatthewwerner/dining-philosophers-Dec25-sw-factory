/**
 * Playwright test fixtures for common E2E setup patterns.
 *
 * These fixtures reduce boilerplate and improve test performance by providing
 * pre-configured contexts with authenticated users and conversations ready to use.
 *
 * Usage:
 *   import { test, expect } from './test-fixtures';
 *
 *   // Auth-only fixture: page has authenticated user, new-chat-button visible
 *   test('my test', async ({ authenticatedPage }) => {
 *     await authenticatedPage.getByTestId('new-chat-button').click();
 *   });
 *
 *   // Conversation fixture: page has a conversation open, chat-area visible
 *   test('my chat test', async ({ conversationPage }) => {
 *     await conversationPage.getByTestId('message-textarea').fill('Hello');
 *   });
 *
 * Performance note: Both fixtures use API calls (not UI modal flow) for setup,
 * which saves 15-30s compared to navigating the conversation creation modal.
 */

import { test as base, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createAndNavigateToConversation,
} from './test-utils';

export { expect };

type AuthFixtures = {
  /** Page with authenticated user - new-chat-button is visible */
  authenticatedPage: Page;
};

type ConversationFixtures = {
  /** Page with an open conversation - chat-area is visible */
  conversationPage: Page;
};

/**
 * Extended test with authenticatedPage fixture.
 * Registers a new unique user and navigates to the home page.
 * new-chat-button is visible when the fixture is ready.
 */
export const testWithAuth = base.extend<AuthFixtures>({
  authenticatedPage: async ({ page }, use) => {
    await setupAuthenticatedUser(page);
    await use(page);
  },
});

/**
 * Extended test with conversationPage fixture.
 * Sets up authenticated user and creates a conversation via API (fast path).
 * chat-area is visible when the fixture is ready.
 *
 * Saves ~20s per test vs using the UI modal flow for conversation creation.
 */
export const test = base.extend<ConversationFixtures>({
  conversationPage: async ({ page }, use) => {
    await setupAuthenticatedUser(page);
    await createAndNavigateToConversation(page, 'Test conversation', ['Aristotle']);
    await use(page);
  },
});
