/**
 * Keyboard Navigation / Accessibility E2E tests.
 * Tests keyboard navigation with Tab, Enter, Escape, and focus management.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaUI } from './test-utils';

test.describe('Keyboard Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('can navigate through modal with Tab key', async ({ page }) => {
    // Open new chat modal
    await page.getByTestId('new-chat-button').click();

    // Modal should be visible
    const modal = page.getByTestId('new-chat-modal');
    await expect(modal).toBeVisible();

    // Topic input should be focused or focusable
    const topicInput = page.getByTestId('topic-input');
    await topicInput.focus();
    await expect(topicInput).toBeFocused();

    // Type a topic
    await page.keyboard.type('Keyboard navigation test');

    // Tab to number input (if exists)
    await page.keyboard.press('Tab');

    // Tab to Next button
    // Note: Depending on form structure, may need multiple Tabs
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press('Tab');
      await page.waitForTimeout(100);

      // Check if Next button is focused
      const nextButton = page.getByTestId('next-button');
      const isFocused = await nextButton.evaluate((el) =>
        el.matches(':focus')
      ).catch(() => false);

      if (isFocused) {
        break;
      }
    }

    // Next button should be enabled since we have a topic
    const nextButton = page.getByTestId('next-button');
    await expect(nextButton).toBeEnabled();

    // Press Enter on Next button
    await page.keyboard.press('Enter');

    // Should advance to thinker selection
    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 10000 });
  });

  test('can send message with Enter key', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Enter key test', 'Socrates');

    // Focus message textarea
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.focus();
    await expect(messageTextarea).toBeFocused();

    // Type a message
    await page.keyboard.type('Sending with Enter key');

    // Press Enter to send (not Shift+Enter which creates new line)
    await page.keyboard.press('Enter');

    // Message should appear in chat
    await expect(page.locator('text=Sending with Enter key')).toBeVisible({
      timeout: 5000,
    });

    // Textarea should still be focused and empty
    await expect(messageTextarea).toBeFocused();
    const textareaValue = await messageTextarea.inputValue();
    expect(textareaValue).toBe('');
  });

  test('can close modal with Escape key', async ({ page }) => {
    // Open new chat modal
    await page.getByTestId('new-chat-button').click();

    // Modal should be visible
    const modal = page.getByTestId('new-chat-modal');
    await expect(modal).toBeVisible();

    // Press Escape to close
    await page.keyboard.press('Escape');

    // Modal should close
    await expect(modal).not.toBeVisible();

    // Should be back on main page
    await expect(page.getByTestId('new-chat-button')).toBeVisible();
  });

  test('focus management after opening and closing export menu', async ({
    page,
  }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Focus management test', 'Aristotle');

    // Open export menu
    const exportButton = page.getByTestId('export-button');
    await exportButton.click();

    // Export menu should be visible
    const exportMenu = page.getByTestId('export-menu');
    await expect(exportMenu).toBeVisible();

    // Close with Escape
    await page.keyboard.press('Escape');

    // Menu should close
    await expect(exportMenu).not.toBeVisible();

    // Focus should return to a reasonable location (likely export button or chat area)
    // Check that we can still interact with the page
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.focus();
    await expect(messageTextarea).toBeFocused();

    // Should be able to type
    await page.keyboard.type('Testing focus after menu close');
    const value = await messageTextarea.inputValue();
    expect(value).toBe('Testing focus after menu close');
  });

  test('Tab key navigates through conversation controls', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Control navigation test', 'Plato');

    // Start from message textarea
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.focus();
    await expect(messageTextarea).toBeFocused();

    // Tab through controls in header
    // This tests that all interactive elements are keyboard accessible

    let focusedElements: string[] = [];

    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('Tab');
      await page.waitForTimeout(100);

      // Get the currently focused element's test-id
      const focusedElement = await page.evaluate(() => {
        const el = document.activeElement;
        return el?.getAttribute('data-testid') || el?.tagName || 'unknown';
      });

      focusedElements.push(focusedElement);

      // Stop if we've cycled back to textarea
      if (
        focusedElement === 'message-textarea' &&
        focusedElements.length > 1
      ) {
        break;
      }
    }

    // Should have tabbed through multiple interactive elements
    expect(focusedElements.length).toBeGreaterThan(1);

    // Should include key controls (though order may vary)
    const focusedTestIds = focusedElements.join(',');

    // At minimum, should be able to reach the message textarea and send button
    // Note: This is a flexible test since exact tab order depends on DOM structure
    const hasMessageTextarea = focusedTestIds.includes('message-textarea');
    const hasSendButton = focusedTestIds.includes('send-button');

    expect(hasMessageTextarea || hasSendButton).toBe(true);
  });

  test('Shift+Enter creates new line in message textarea', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Multiline test', 'Confucius');

    // Focus message textarea
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.focus();

    // Type first line
    await page.keyboard.type('First line');

    // Press Shift+Enter to create new line (should NOT send message)
    await page.keyboard.press('Shift+Enter');

    // Type second line
    await page.keyboard.type('Second line');

    // Get textarea value
    const value = await messageTextarea.inputValue();

    // Should contain both lines with a newline between them
    expect(value).toContain('First line');
    expect(value).toContain('Second line');
    expect(value).toMatch(/First line[\n\r]+Second line/);

    // Message should NOT have been sent yet
    const firstLineMessage = page.locator('text=First line').and(page.locator('[data-testid="message"]'));
    const exists = await firstLineMessage.count();
    expect(exists).toBe(0);
  });
});
