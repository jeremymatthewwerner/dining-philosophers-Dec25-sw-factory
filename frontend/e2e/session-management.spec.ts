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

    // Should either:
    // 1. Show an error message
    // 2. Redirect to login
    // 3. Show auth error banner

    await page.waitForTimeout(2000);

    // Check for any of these indicators
    const hasErrorMessage = await page
      .locator('text=/error|unauthorized|expired|login/i')
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
  });

  test('can logout mid-conversation without errors', async ({ page }) => {
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
    await page.waitForLoadState('networkidle');

    // Should redirect to login or show unauthenticated state
    const isOnLoginPage =
      page.url().includes('/login') || page.url().includes('/register');
    const hasLoginForm = await page
      .getByTestId('login-form')
      .isVisible()
      .catch(() => false);

    expect(isOnLoginPage || hasLoginForm).toBe(true);

    // No errors should have occurred during logout
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // Wait a moment to catch any delayed errors
    await page.waitForTimeout(1000);

    // Filter out expected WebSocket closure errors
    const unexpectedErrors = consoleErrors.filter(
      (err) => !err.includes('WebSocket') && !err.includes('network')
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
    await page.waitForLoadState('networkidle');

    // Get the token after reload
    const tokenAfterReload = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    // Token should persist
    expect(tokenAfterReload).toBe(tokenBeforeReload);

    // Should still see the conversation
    await expect(
      page.locator('text=Session persistence test')
    ).toBeVisible({ timeout: 10000 });

    // Should still be able to interact with the conversation
    const messageTextarea = page.getByTestId('message-textarea');
    await expect(messageTextarea).toBeEnabled();

    // Try sending a message to verify session is still valid
    await messageTextarea.fill('Testing session after reload');
    const sendButton = page.getByTestId('send-button');
    await expect(sendButton).toBeEnabled();
    await sendButton.click();

    // Message should appear (validates session is still active)
    await expect(page.locator('text=Testing session after reload')).toBeVisible(
      { timeout: 5000 }
    );
  });
});
