/**
 * Persistence E2E tests.
 * Tests that data persists across page reloads.
 */

import { test, expect } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createConversationViaAPI,
} from './test-utils';

test.describe('Persistence', () => {
  test('conversations persist across page reload', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // Create a conversation via API (faster than UI modal flow)
    await createConversationViaAPI(page, 'Test persistence topic', [
      'Aristotle',
    ]);

    // Reload to pick up the newly created conversation
    await page.goto('/');

    // Conversation should be visible in sidebar
    const conversationItem = page.getByTestId('conversation-item');
    await expect(conversationItem).toBeVisible({ timeout: 10000 });
    // Use .last() because ScrollingText renders hidden measurement span first, visible span second
    await expect(
      page.locator('text=Test persistence topic').last()
    ).toBeVisible();

    // Click on the conversation to enter it
    await conversationItem.click();
    await expect(page.getByTestId('chat-area')).toBeVisible({ timeout: 10000 });

    // Reload the page
    await page.reload();

    // Conversation should still be there after reload
    await expect(page.getByTestId('conversation-item')).toBeVisible({
      timeout: 10000,
    });
    // Use .last() because ScrollingText renders hidden measurement span first, visible span second
    await expect(
      page.locator('text=Test persistence topic').last()
    ).toBeVisible();
  });
});
