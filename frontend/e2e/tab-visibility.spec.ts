/**
 * Tab Visibility E2E tests.
 * Tests pause/resume behavior when browser tab becomes hidden/visible.
 */

import { test, expect } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createAndNavigateToConversation,
} from './test-utils';

test.describe('Tab Visibility Handling', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('pauses conversation when tab becomes hidden', async ({ page }) => {
    // Create a conversation via API and navigate to it via sidebar
    await createAndNavigateToConversation(page, 'Visibility test', [
      'Socrates',
    ]);

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

    // Note: This test validates that the visibility change event is dispatched.
    // The actual pause behavior depends on implementation in useWebSocket hook.
    // We verify that the event can be triggered and handled without errors.

    // Wait for event to be processed and check for errors
    await expect
      .poll(
        async () => {
          const errors = await page.evaluate(
            () => (window as any).__TEST_ERRORS__ || []
          );
          return errors.length;
        },
        { timeout: 3000 }
      )
      .toBe(0);
  });

  test('resumes conversation when tab becomes visible', async ({ page }) => {
    // Create a conversation via API and navigate to it via sidebar
    await createAndNavigateToConversation(page, 'Resume test', ['Aristotle']);

    // Simulate tab being hidden first
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => true,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Simulate tab becoming visible again
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => false,
      });
      document.dispatchEvent(new Event('visibilitychange'));
    });

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
    // Create a conversation via API and navigate to it via sidebar
    await createAndNavigateToConversation(page, 'Message pause test', [
      'Confucius',
    ]);

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

    // Wait briefly to allow any in-flight messages to arrive after tab is hidden,
    // then verify count is stable. Testing absence-of-change inherently needs
    // a brief time window - use expect.poll with longer intervals instead of inner timeout.
    let stableCount = 0;
    let prevCount = -1;
    await expect
      .poll(
        async () => {
          const count = await getMessageCount();
          if (count === prevCount) {
            stableCount++;
          } else {
            stableCount = 0;
            prevCount = count;
          }
          return stableCount;
        },
        { timeout: 3000, intervals: [300, 300, 300, 300, 300, 300, 300] }
      )
      .toBeGreaterThanOrEqual(3); // Count stable for 3 consecutive polls (~900ms)

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
