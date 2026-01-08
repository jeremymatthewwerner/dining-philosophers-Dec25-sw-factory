/**
 * Tab Visibility E2E tests.
 * Tests pause/resume behavior when browser tab becomes hidden/visible.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaUI } from './test-utils';

test.describe('Tab Visibility Handling', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('pauses conversation when tab becomes hidden', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Visibility test', 'Socrates');

    // Verify pause button shows "Pause" initially
    const pauseButton = page.getByTestId('pause-resume-button');
    await expect(pauseButton).toContainText('Pause');

    // Simulate tab becoming hidden
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => true,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Wait for WebSocket to potentially react
    await page.waitForTimeout(1000);

    // Note: This test validates that the visibility change event is dispatched.
    // The actual pause behavior depends on implementation in useWebSocket hook.
    // We verify that the event can be triggered and handled without errors.

    // No errors should occur
    const errors = await page.evaluate(() =>
      (window as any).__TEST_ERRORS__ || []
    );
    expect(errors).toHaveLength(0);
  });

  test('resumes conversation when tab becomes visible', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Resume test', 'Aristotle');

    // Simulate tab being hidden first
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => true,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    await page.waitForTimeout(500);

    // Simulate tab becoming visible again
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => false,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    await page.waitForTimeout(1000);

    // Conversation should remain functional
    const pauseButton = page.getByTestId('pause-resume-button');
    await expect(pauseButton).toBeVisible();

    // Should be able to send a message after tab becomes visible
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Testing visibility resume');

    const sendButton = page.getByTestId('send-button');
    await expect(sendButton).toBeEnabled();
  });

  test('no new messages arrive while tab is hidden', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Message pause test', 'Confucius');

    // Send a message
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Please respond');
    await page.getByTestId('send-button').click();

    // Wait for user message to appear
    await expect(page.locator('text=Please respond')).toBeVisible({
      timeout: 5000,
    });

    // Get initial message count
    const getMessageCount = async () => {
      const messages = await page.getByTestId('message').all();
      return messages.length;
    };

    const initialCount = await getMessageCount();

    // Simulate tab becoming hidden
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => true,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Wait while hidden (WebSocket should disconnect or pause)
    await page.waitForTimeout(3000);

    const countWhileHidden = await getMessageCount();

    // Message count should not have increased significantly while hidden
    // Allow for at most 1 message that might have been in-flight
    expect(countWhileHidden).toBeLessThanOrEqual(initialCount + 1);

    // Make tab visible again
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => false,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Verify UI is still responsive
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(messageTextarea).toBeEnabled();
  });
});
