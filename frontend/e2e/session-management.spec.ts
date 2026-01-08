/**
 * Session Management E2E tests.
 * Tests authentication edge cases: token expiry, refresh, and logout.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaUI } from './test-utils';

test.describe('Session Management', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles expired token gracefully', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Token expiry test', 'Plato');

    // Simulate token expiry by setting an invalid token
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'expired.invalid.token');
    });

    // Try to send a message
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('This should fail gracefully');

    const sendButton = page.getByTestId('send-button');
    await sendButton.click();

    // Wait for one of these indicators to appear (with proper Playwright waiting):
    // 1. Error message text
    // 2. Redirect to login page
    // 3. Error banner element

    // Use Promise.race with expect().toPass() for robust waiting
    await expect(async () => {
      const hasErrorMessage = await page
        .locator('text=/error|unauthorized|expired|login|failed/i')
        .first()
        .isVisible()
        .catch(() => false);

      const isOnLoginPage = page.url().includes('/login');

      const hasErrorBanner = await page
        .getByTestId('error-banner')
        .isVisible()
        .catch(() => false);

      // At least one error handling mechanism should be active
      expect(hasErrorMessage || isOnLoginPage || hasErrorBanner).toBe(true);
    }).toPass({ timeout: 10000 });
  });

  test('can logout mid-conversation without errors', async ({ page }) => {
    // Set up console error listener BEFORE actions
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Create a conversation
    await createConversationViaUI(page, 'Logout test', 'Aristotle');

    // Verify we're in a conversation
    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Clear auth token to simulate logout
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
    });

    // Trigger a navigation or reload
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // Should redirect to login or show unauthenticated state
    await expect(async () => {
      const isOnLoginPage =
        page.url().includes('/login') || page.url().includes('/register');
      const hasLoginForm = await page
        .getByTestId('login-form')
        .isVisible()
        .catch(() => false);
      const hasNewChatButton = await page
        .getByTestId('new-chat-button')
        .isVisible()
        .catch(() => false);

      // Either on login page, has login form, or back to home (unauthenticated)
      expect(isOnLoginPage || hasLoginForm || hasNewChatButton).toBe(true);
    }).toPass({ timeout: 10000 });

    // Filter out expected WebSocket/network closure errors
    const unexpectedErrors = consoleErrors.filter(
      (err) =>
        !err.includes('WebSocket') &&
        !err.includes('network') &&
        !err.includes('Failed to fetch') &&
        !err.includes('ERR_')
    );
    expect(unexpectedErrors).toHaveLength(0);
  });

  test('maintains session across page reload', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Session persistence test', 'Socrates');

    // Get the stored token before reload
    const tokenBeforeReload = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    expect(tokenBeforeReload).toBeTruthy();

    // Reload the page
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // Get the token after reload
    const tokenAfterReload = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    // Token should persist
    expect(tokenAfterReload).toBe(tokenBeforeReload);

    // Should still see the conversation topic somewhere on the page
    await expect(
      page.locator('text=Session persistence test')
    ).toBeVisible({ timeout: 15000 });

    // Should still be able to interact with the conversation
    const messageTextarea = page.getByTestId('message-textarea');
    await expect(messageTextarea).toBeVisible({ timeout: 10000 });

    // Wait for textarea to be ready for input
    await expect(messageTextarea).toBeEnabled({ timeout: 10000 });

    // Try sending a message to verify session is still valid
    await messageTextarea.fill('Testing session after reload');
    const sendButton = page.getByTestId('send-button');
    await expect(sendButton).toBeEnabled();
    await sendButton.click();

    // Message should appear (validates session is still active)
    await expect(page.locator('text=Testing session after reload')).toBeVisible({
      timeout: 10000,
    });
  });
});
