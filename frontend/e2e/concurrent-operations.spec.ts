/**
 * Concurrent Operations E2E tests.
 * Tests multi-tab scenarios and rapid conversation switching.
 */

import { test, expect } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createConversationViaUI,
  createConversationViaAPI,
} from './test-utils';

test.describe('Concurrent Operations', () => {
  test('can switch between conversations rapidly without errors', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    // Create 3 conversations
    await createConversationViaUI(page, 'First conversation', 'Socrates');
    await expect(
      page.locator('h2', { hasText: 'First conversation' })
    ).toBeVisible();

    await createConversationViaUI(page, 'Second conversation', 'Aristotle');
    await expect(
      page.locator('h2', { hasText: 'Second conversation' })
    ).toBeVisible();

    await createConversationViaUI(page, 'Third conversation', 'Plato');
    await expect(
      page.locator('h2', { hasText: 'Third conversation' })
    ).toBeVisible();

    // Verify all 3 conversations exist in sidebar
    const conversationItems = page.getByTestId('conversation-item');
    await expect(conversationItems).toHaveCount(3);

    // Rapidly switch between them
    for (let i = 0; i < 3; i++) {
      // Click first conversation and wait for it to be active
      await page
        .getByTestId('conversation-item')
        .filter({ hasText: 'First conversation' })
        .click();
      await expect(page.locator('h2', { hasText: 'First conversation' })).toBeVisible();

      // Click second conversation and wait for it to be active
      await page
        .getByTestId('conversation-item')
        .filter({ hasText: 'Second conversation' })
        .click();
      await expect(page.locator('h2', { hasText: 'Second conversation' })).toBeVisible();

      // Click third conversation and wait for it to be active
      await page
        .getByTestId('conversation-item')
        .filter({ hasText: 'Third conversation' })
        .click();
      await expect(page.locator('h2', { hasText: 'Third conversation' })).toBeVisible();
    }

    // After rapid switching, app should still be functional
    await expect(page.getByTestId('chat-area')).toBeVisible();
    await expect(page.getByTestId('message-textarea')).toBeEnabled();
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();

    // Verify no duplicate conversations were created
    await expect(conversationItems).toHaveCount(3);
  });

  test('handles rapid conversation creation', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // Try creating multiple conversations in quick succession
    const conversationPromises = [
      createConversationViaAPI(page, 'Rapid conv 1', ['Socrates']),
      createConversationViaAPI(page, 'Rapid conv 2', ['Aristotle']),
      createConversationViaAPI(page, 'Rapid conv 3', ['Plato']),
    ];

    // Wait for all to complete
    const conversations = await Promise.all(conversationPromises);

    // Verify all were created
    expect(conversations).toHaveLength(3);
    expect(conversations[0].topic).toBe('Rapid conv 1');
    expect(conversations[1].topic).toBe('Rapid conv 2');
    expect(conversations[2].topic).toBe('Rapid conv 3');

    // Reload to see them in the UI
    await page.reload();
    await page.waitForLoadState('networkidle');

    // All 3 should appear in sidebar
    const conversationItems = page.getByTestId('conversation-item');
    await expect(conversationItems).toHaveCount(3, { timeout: 10000 });

    // Verify each conversation is clickable and functional
    await page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Rapid conv 1' })
      .click();
    await expect(page.locator('h2', { hasText: 'Rapid conv 1' })).toBeVisible();

    await page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Rapid conv 2' })
      .click();
    await expect(page.locator('h2', { hasText: 'Rapid conv 2' })).toBeVisible();
  });

  test('handles rapid message sending in same conversation', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    // Create a conversation
    await createConversationViaUI(page, 'Rapid messages test', 'Confucius');

    const messageTextarea = page.getByTestId('message-textarea');
    const sendButton = page.getByTestId('send-button');

    // Send 5 messages rapidly
    const messages = [
      'First message',
      'Second message',
      'Third message',
      'Fourth message',
      'Fifth message',
    ];

    for (const msg of messages) {
      await messageTextarea.fill(msg);
      await sendButton.click();
      // Wait for the message to appear before sending next
      await expect(page.locator(`text=${msg}`)).toBeVisible({ timeout: 5000 });
    }

    // Wait for all user messages to appear using polling assertion
    const userMessages = page.locator('[data-sender-type="user"]');
    await expect
      .poll(async () => await userMessages.count(), {
        timeout: 10000,
      })
      .toBe(5);

    // All 5 messages should be visible
    for (const msg of messages) {
      await expect(page.locator(`text=${msg}`)).toBeVisible();
    }

    // Should have exactly 5 user messages (no duplicates)
    const count = await userMessages.count();
    expect(count).toBe(5);
  });
});
