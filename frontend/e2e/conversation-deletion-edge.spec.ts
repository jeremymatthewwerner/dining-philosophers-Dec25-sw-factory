/**
 * Conversation Deletion Edge Cases E2E tests.
 * Tests edge cases around deleting conversations.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaUI } from './test-utils';

// TEMPORARILY SKIPPED: These tests are slow due to API calls, causing CI timeout
// TODO: Re-enable after optimizing test performance (issue #526)
test.describe.skip('Conversation Deletion Edge Cases', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('should handle deleting conversation while messages are loading', async ({
    page,
  }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Delete while loading test', 'Plato');
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });

    // Send a message that will trigger AI response
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Tell me about your philosophy');
    await page.getByTestId('send-button').click();

    // Immediately try to delete while AI is responding
    // Wait for network activity to start (message being sent)
    await page.waitForLoadState('networkidle', { timeout: 3000 }).catch(() => {});

    // Open sidebar to access conversation list
    const hamburgerButton = page.getByTestId('mobile-menu-button');
    const isHamburgerVisible = await hamburgerButton.isVisible().catch(() => false);

    if (isHamburgerVisible) {
      await hamburgerButton.click();
      await expect(page.getByTestId('delete-conversation').first()).toBeVisible({
        timeout: 3000,
      }).catch(() => {});
    }

    // Find and click delete button for the conversation
    const deleteButtons = page.getByTestId('delete-conversation');
    const deleteCount = await deleteButtons.count();

    if (deleteCount > 0) {
      await deleteButtons.first().click();

      // Confirm deletion if confirmation dialog appears
      const confirmButton = page.locator('button', { hasText: /delete|confirm/i });
      const confirmVisible = await confirmButton.isVisible({ timeout: 2000 }).catch(() => false);

      if (confirmVisible) {
        await confirmButton.click();
      }

      // Wait for deletion to process (network idle)
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

      // Verify conversation was deleted (either redirected or conversation removed)
      const conversationStillVisible = await page
        .getByTestId('chat-area')
        .isVisible()
        .catch(() => false);

      // Either chat area is gone OR we're at a blank/welcome state
      const welcomeVisible = await page
        .locator('text=/welcome|start.*conversation|create.*chat/i')
        .isVisible()
        .catch(() => false);

      // Should handle gracefully - either shows welcome or conversation is gone
      expect(!conversationStillVisible || welcomeVisible).toBe(true);
    }
  });

  test('should handle deleting the last conversation', async ({ page }) => {
    // Create exactly one conversation
    await createConversationViaUI(page, 'Only conversation', 'Aristotle');
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });

    // Open sidebar
    const hamburgerButton = page.getByTestId('mobile-menu-button');
    const isHamburgerVisible = await hamburgerButton.isVisible().catch(() => false);

    if (isHamburgerVisible) {
      await hamburgerButton.click();
      await expect(page.getByTestId('delete-conversation').first()).toBeVisible({
        timeout: 3000,
      }).catch(() => {});
    }

    // Delete the conversation
    const deleteButton = page.getByTestId('delete-conversation').first();
    await deleteButton.click();

    // Confirm if needed
    const confirmButton = page.locator('button', { hasText: /delete|confirm/i });
    const confirmVisible = await confirmButton.isVisible({ timeout: 2000 }).catch(() => false);

    if (confirmVisible) {
      await confirmButton.click();
    }

    // Wait for deletion (network idle)
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

    // Should show empty state or welcome message
    const emptyStateVisible = await page
      .locator('text=/no conversations|start.*conversation|create.*chat|welcome/i')
      .isVisible({ timeout: 5000 })
      .catch(() => false);

    const chatAreaGone = await page
      .getByTestId('chat-area')
      .isVisible()
      .catch(() => false);

    // Either shows empty state or chat area is gone
    expect(emptyStateVisible || !chatAreaGone).toBe(true);

    // Verify new chat button is still available
    await expect(page.getByTestId('new-chat-button')).toBeVisible();
  });

  test('should handle rapid deletion attempts (clicking delete twice)', async ({
    page,
  }) => {
    // Create a conversation
    await createConversationViaUI(
      page,
      'Rapid delete test',
      'Socrates'
    );
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });

    // Open sidebar
    const hamburgerButton = page.getByTestId('mobile-menu-button');
    const isHamburgerVisible = await hamburgerButton.isVisible().catch(() => false);

    if (isHamburgerVisible) {
      await hamburgerButton.click();
      await expect(page.getByTestId('delete-conversation').first()).toBeVisible({
        timeout: 3000,
      }).catch(() => {});
    }

    // Get delete button
    const deleteButton = page.getByTestId('delete-conversation').first();

    // Click delete rapidly twice
    await deleteButton.click();
    await deleteButton.click({ force: true }).catch(() => {
      // Button might disappear after first click
    });

    // Try to confirm if dialog appears
    const confirmButton = page.locator('button', { hasText: /delete|confirm/i });
    const confirmVisible = await confirmButton.isVisible({ timeout: 2000 }).catch(() => false);

    if (confirmVisible) {
      await confirmButton.click();
      // Try clicking again rapidly
      await confirmButton.click({ force: true }).catch(() => {
        // Might be gone already
      });
    }

    // Wait for operation to complete (network idle)
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

    // Should handle gracefully without errors or duplicate deletions
    // Page should still be functional
    await expect(page.getByTestId('new-chat-button')).toBeVisible();
  });

  test('should handle deleting conversation then creating new one', async ({
    page,
  }) => {
    // Create and delete a conversation
    await createConversationViaUI(
      page,
      'Delete then create',
      'Descartes'
    );
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });

    // Open sidebar and delete
    const hamburgerButton = page.getByTestId('mobile-menu-button');
    const isHamburgerVisible = await hamburgerButton.isVisible().catch(() => false);

    if (isHamburgerVisible) {
      await hamburgerButton.click();
      await expect(page.getByTestId('delete-conversation').first()).toBeVisible({
        timeout: 3000,
      }).catch(() => {});
    }

    const deleteButton = page.getByTestId('delete-conversation').first();
    await deleteButton.click();

    const confirmButton = page.locator('button', { hasText: /delete|confirm/i });
    const confirmVisible = await confirmButton.isVisible({ timeout: 2000 }).catch(() => false);

    if (confirmVisible) {
      await confirmButton.click();
    }

    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

    // Now create a new conversation immediately
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('New after delete');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Add thinker
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Kant');
    await page.getByTestId('add-custom-thinker').click();
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    // Create conversation
    await page.getByTestId('create-button').click();

    // Should successfully create new conversation
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });
  });

  test('should handle deletion when conversation is not currently selected', async ({
    page,
  }) => {
    // This test creates two conversations requiring multiple Claude API validations
    test.slow();
    // Create two conversations
    await createConversationViaUI(page, 'First conversation', 'Plato');
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });

    // Create second conversation
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Second conversation');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Aristotle');
    await page.getByTestId('add-custom-thinker').click();
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    await page.getByTestId('create-button').click();
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });

    // Now on second conversation, delete the first one
    const hamburgerButton = page.getByTestId('mobile-menu-button');
    const isHamburgerVisible = await hamburgerButton.isVisible().catch(() => false);

    if (isHamburgerVisible) {
      await hamburgerButton.click();
      await expect(page.getByTestId('delete-conversation').first()).toBeVisible({
        timeout: 3000,
      }).catch(() => {});
    }

    // Get all delete buttons and delete the first conversation
    const deleteButtons = page.getByTestId('delete-conversation');
    const count = await deleteButtons.count();

    if (count > 1) {
      // Delete first conversation (not currently selected)
      await deleteButtons.first().click();

      const confirmButton = page.locator('button', { hasText: /delete|confirm/i });
      const confirmVisible = await confirmButton.isVisible({ timeout: 2000 }).catch(() => false);

      if (confirmVisible) {
        await confirmButton.click();
      }

      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});

      // Should still show current (second) conversation
      await expect(page.getByTestId('chat-area')).toBeVisible();

      // Verify only one conversation remains
      if (isHamburgerVisible) {
        await hamburgerButton.click();
        await expect(page.getByTestId('delete-conversation').first()).toBeVisible({
          timeout: 3000,
        }).catch(() => {});
      }

      const remainingDeleteButtons = await page.getByTestId('delete-conversation').count();
      expect(remainingDeleteButtons).toBe(1);
    }
  });
});
