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
    // Verify we're authenticated first
    await expect(page.getByTestId('new-chat-button')).toBeVisible();

    // Simulate token expiry by setting an invalid token
    // Note: We need to reload to invalidate the in-memory token cache in the API client
    await page.evaluate(() => {
      localStorage.setItem('access_token', 'expired.invalid.token');
    });

    // Reload to force the app to use the invalid token
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // With an invalid token, the app should redirect to login or show auth error
    // The API client now handles 401 responses by clearing auth and redirecting
    await expect(async () => {
      const isOnLoginPage = page.url().includes('/login');
      const hasLoginForm = await page
        .getByTestId('login-form')
        .isVisible()
        .catch(() => false);

      // Should redirect to login page
      expect(isOnLoginPage || hasLoginForm).toBe(true);
    }).toPass({ timeout: 15000 });
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

    // Should still see the conversation topic in the sidebar
    const conversationItem = page.locator('text=Session persistence test');
    await expect(conversationItem).toBeVisible({ timeout: 15000 });

    // Click on the conversation to select it (conversations aren't auto-selected after reload)
    await conversationItem.click();

    // Wait for the chat area to load
    await expect(page.getByTestId('chat-area')).toBeVisible({ timeout: 10000 });

    // Should be able to interact with the conversation
    const messageTextarea = page.getByTestId('message-textarea');
    await expect(messageTextarea).toBeVisible({ timeout: 10000 });
    await expect(messageTextarea).toBeEnabled({ timeout: 10000 });

    // Try sending a message to verify session is still valid
    await messageTextarea.fill('Testing session after reload');
    const sendButton = page.getByTestId('send-button');
    await expect(sendButton).toBeEnabled();
    await sendButton.click();

    // Message should appear (validates session is still active)
    await expect(page.locator('text=Testing session after reload')).toBeVisible(
      {
        timeout: 10000,
      }
    );
  });
});
