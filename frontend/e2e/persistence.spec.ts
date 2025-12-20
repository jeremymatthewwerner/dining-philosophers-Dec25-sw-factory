/**
 * Persistence E2E tests.
 * Tests that data persists across page reloads.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser } from './test-utils';

test.describe('Persistence', () => {
  test('conversations persist across page reload', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // Create a conversation
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Test persistence topic');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Add a custom thinker (more reliable than waiting for suggestions)
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.scrollIntoViewIfNeeded();
    await customInput.fill('Aristotle');
    const addButton = page.getByTestId('add-custom-thinker');
    await addButton.scrollIntoViewIfNeeded();
    await addButton.click({ force: true });
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    // Create conversation
    const createButton = page.getByTestId('create-button');
    await createButton.scrollIntoViewIfNeeded();
    await createButton.click();
    await expect(page.getByTestId('chat-area')).toBeVisible({ timeout: 10000 });

    // Verify conversation appears in sidebar
    const conversationItem = page.getByTestId('conversation-item');
    await expect(conversationItem).toBeVisible();

    // Reload the page
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Conversation should still be there
    await expect(page.getByTestId('conversation-item')).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator('text=Test persistence topic')).toBeVisible();
  });
});
