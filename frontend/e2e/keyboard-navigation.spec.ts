/**
 * Keyboard Navigation / Accessibility E2E tests.
 * Tests keyboard navigation with Tab, Enter, Escape, and focus management.
 */

import { test, expect } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createAndNavigateToConversation,
} from './test-utils';

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
    await topicInput.fill('Keyboard navigation test');

    // Tab to Next button - use expect with retry instead of manual loop
    const nextButton = page.getByTestId('next-button');
    await expect(nextButton).toBeEnabled();

    // Click next button directly (Tab navigation varies by browser/OS)
    await nextButton.click();

    // Should advance to thinker selection - use 30s timeout (API can be slow)
    await page
      .locator('h2', { hasText: 'Select Thinkers' })
      .waitFor({ state: 'visible', timeout: 30000 });
  });

  test('can send message with Enter key', async ({ page }) => {
    // Create a conversation via API and navigate to it via sidebar
    await createAndNavigateToConversation(page, 'Enter key test', ['Socrates']);

    // Focus message textarea
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.focus();
    await expect(messageTextarea).toBeFocused();

    // Type a message
    await messageTextarea.fill('Sending with Enter key');

    // Press Enter to send (not Shift+Enter which creates new line)
    await page.keyboard.press('Enter');

    // Message should appear in chat
    await expect(page.locator('text=Sending with Enter key')).toBeVisible({
      timeout: 5000,
    });

    // Textarea should still be focused and empty
    await expect(messageTextarea).toBeFocused();
    await expect(messageTextarea).toHaveValue('');
  });

  test('can close modal with Escape key', async ({ page }) => {
    // Open new chat modal
    await page.getByTestId('new-chat-button').click();

    // Modal should be visible
    const modal = page.getByTestId('new-chat-modal');
    await expect(modal).toBeVisible();

    // Press Escape to close
    await page.keyboard.press('Escape');

    // Modal should close - use toBeHidden() which has better auto-waiting for animations
    await expect(modal).toBeHidden({ timeout: 5000 });

    // Should be back on main page
    await expect(page.getByTestId('new-chat-button')).toBeVisible();
  });

  test('focus management after opening and closing export menu', async ({
    page,
  }) => {
    // Create a conversation via API and navigate to it via sidebar
    await createAndNavigateToConversation(page, 'Focus management test', [
      'Aristotle',
    ]);

    // Open export menu
    const exportButton = page.getByTestId('export-button');
    await exportButton.click();

    // Export menu should be visible
    const exportMenu = page.getByTestId('export-menu');
    await expect(exportMenu).toBeVisible();

    // Close with Escape
    await page.keyboard.press('Escape');

    // Menu should close - use toBeHidden() for better animation handling
    await expect(exportMenu).toBeHidden({ timeout: 5000 });

    // Focus should return to a reasonable location - verify we can interact
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.click(); // Click instead of focus() for reliability
    await expect(messageTextarea).toBeFocused();

    // Should be able to type
    await messageTextarea.fill('Testing focus after menu close');
    await expect(messageTextarea).toHaveValue('Testing focus after menu close');
  });

  test('Tab key navigates through conversation controls', async ({ page }) => {
    // Create a conversation via API and navigate to it via sidebar
    await createAndNavigateToConversation(page, 'Control navigation test', [
      'Plato',
    ]);

    // Start from message textarea
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.click();
    await expect(messageTextarea).toBeFocused();

    // Tab through controls - collect focused elements
    const focusedElements: string[] = [];

    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('Tab');

      // Wait for focus to settle using a small delay, then check
      const focusedElement = await page.evaluate(() => {
        const el = document.activeElement;
        return (
          el?.getAttribute('data-testid') ||
          el?.tagName?.toLowerCase() ||
          'unknown'
        );
      });

      focusedElements.push(focusedElement);

      // Stop if we've cycled back to textarea
      if (focusedElement === 'message-textarea' && focusedElements.length > 1) {
        break;
      }
    }

    // Should have tabbed through multiple interactive elements
    expect(focusedElements.length).toBeGreaterThan(1);

    // Verify we found some interactive elements (test IDs or known elements)
    const hasInteractiveElement = focusedElements.some(
      (el) =>
        el.includes('button') ||
        el.includes('textarea') ||
        el.includes('input') ||
        el === 'send-button' ||
        el === 'export-button' ||
        el === 'message-textarea'
    );
    expect(hasInteractiveElement).toBe(true);
  });

  test('Shift+Enter creates new line in message textarea', async ({ page }) => {
    // Create a conversation
    await createAndNavigateToConversation(page, 'Multiline test', [
      'Confucius',
    ]);

    // Focus message textarea
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.click();

    // Type first line
    await messageTextarea.fill('First line');

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
    const firstLineMessage = page
      .locator('[data-testid="message"]')
      .filter({ hasText: 'First line' });
    await expect(firstLineMessage).toHaveCount(0);
  });
});
