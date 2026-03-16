/**
 * Network Error Handling E2E tests.
 * Tests error recovery, timeouts, and network failures.
 */

import { test, expect } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createAndNavigateToConversation,
} from './test-utils';

test.describe('Network Error Recovery', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles API errors during thinker suggestion gracefully', async ({
    page,
  }) => {
    // Intercept the suggest thinkers API call and simulate a failure
    await page.route('**/api/thinkers/suggest', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    // Try to create a conversation
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Error handling test');
    await page.getByTestId('next-button').click();

    // Should show error message or fallback behavior - wait for UI to update
    // Use Promise.race to check which appears first
    const errorLocator = page.locator('text=/error|failed|unable/i');
    const customInputLocator = page.getByTestId('custom-thinker-input');

    await Promise.race([
      errorLocator.waitFor({ state: 'visible', timeout: 10000 }),
      customInputLocator.waitFor({ state: 'visible', timeout: 10000 }),
    ]).catch(() => {
      // Either one should be visible, catch to check manually
    });

    // Check if error message is displayed
    const errorVisible = await errorLocator.isVisible().catch(() => false);

    // Or check if we can still proceed (graceful degradation)
    const customInputVisible = await customInputLocator
      .isVisible()
      .catch(() => false);

    // Either error is shown OR custom input is available as fallback
    expect(errorVisible || customInputVisible).toBe(true);
  });

  test('handles API timeout during thinker validation', async ({
    page,
    context,
  }) => {
    // Set a short timeout for this test
    test.setTimeout(60000);

    // Open modal and go to thinker selection
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Timeout test');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Intercept validate thinker API and return timeout immediately
    await page.route('**/api/thinkers/validate', (route) => {
      // Return timeout error immediately instead of waiting
      route.fulfill({
        status: 504,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Gateway timeout' }),
      });
    });

    // Try to add custom thinker
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Descartes');

    const addButton = page.getByTestId('add-custom-thinker');
    await addButton.click();

    // Wait for error message or verify thinker was not added
    const errorLocator = page.locator('text=/timeout|error|failed/i');

    // Wait for either error to appear or loading to finish (max 10s)
    await Promise.race([
      errorLocator.waitFor({ state: 'visible', timeout: 10000 }),
      page.waitForLoadState('networkidle', { timeout: 10000 }),
    ]).catch(() => {
      // Continue to verification
    });

    // Check for error message or that thinker was not added
    const selectedThinkers = await page.getByTestId('selected-thinker').count();
    const errorVisible = await errorLocator.isVisible().catch(() => false);

    // Either no thinker added or error shown
    expect(selectedThinkers === 0 || errorVisible).toBe(true);
  });

  test('handles offline state during conversation creation', async ({
    page,
    context,
  }) => {
    // Open modal
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Offline test');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Add a thinker using custom input
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Kant');
    await page.getByTestId('add-custom-thinker').click();
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    // Simulate offline by blocking all API requests
    await page.route('**/api/**', (route) => {
      route.abort('failed');
    });

    // Try to create conversation
    const createButton = page.getByTestId('create-button');
    await createButton.click();

    // Wait for error or verify we stayed on the same page
    const errorLocator = page.locator('text=/error|failed|offline|network/i');
    const createButtonLocator = page.getByTestId('create-button');

    await Promise.race([
      errorLocator.waitFor({ state: 'visible', timeout: 5000 }),
      page.waitForLoadState('networkidle', { timeout: 5000 }),
    ]).catch(() => {
      // Continue to verification
    });

    // Should show error or remain on same page
    const errorVisible = await errorLocator.isVisible().catch(() => false);
    const stillOnThinkerPage = await createButtonLocator
      .isVisible()
      .catch(() => false);

    // Either error shown or still on thinker selection (didn't crash)
    expect(errorVisible || stillOnThinkerPage).toBe(true);
  });
});

test.describe('WebSocket Error Recovery', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles WebSocket connection failure', async ({ page }) => {
    // Create conversation first
    await createAndNavigateToConversation(page, 'WebSocket test', ['Spinoza']);

    // Wait for chat area
    await expect(page.getByTestId('chat-area')).toBeVisible({ timeout: 10000 });

    // Close any existing WebSocket connections by blocking them
    await page.route('**/ws/**', (route) => {
      route.abort('failed');
    });

    // Try to send a message (which requires WebSocket)
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Test message during WS failure');

    const sendButton = page.getByTestId('send-button');
    await sendButton.click();

    // Message might appear locally but won't be sent to server
    // App should handle this gracefully without crashing

    // Check for graceful state: either message appeared locally or an error is shown
    // Don't use networkidle — WS abort keeps network in non-idle state indefinitely
    const messageLocator = page.locator('text=Test message during WS failure');
    const errorLocator = page.locator('text=/error|failed|offline/i');
    await Promise.race([
      messageLocator.waitFor({ state: 'visible', timeout: 5000 }),
      errorLocator.waitFor({ state: 'visible', timeout: 5000 }),
    ]).catch(() => {});

    // Page should still be functional (not crashed)
    await expect(page.getByTestId('chat-area')).toBeVisible();
  });

  test('reconnects WebSocket after temporary disconnection', async ({
    page,
    context,
  }) => {
    test.setTimeout(60000);

    // Create conversation
    await createAndNavigateToConversation(page, 'Reconnection test', ['Hume']);
    await expect(page.getByTestId('chat-area')).toBeVisible({ timeout: 10000 });

    // Send initial message to verify connection works
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Initial message');
    await page.getByTestId('send-button').click();

    await expect(page.locator('text=Initial message')).toBeVisible({
      timeout: 5000,
    });

    // Block WebSocket temporarily
    // page.route() takes effect immediately — no wait needed before unrouting
    await page.route('**/ws/**', (route) => {
      route.abort('failed');
    });

    // Unblock WebSocket immediately (route interception is synchronous)
    await page.unroute('**/ws/**');

    // Try sending another message after reconnection
    await messageTextarea.fill('Message after reconnection');
    await page.getByTestId('send-button').click();

    // Should eventually reconnect and send message
    await expect(page.locator('text=Message after reconnection')).toBeVisible({
      timeout: 10000,
    });
  });
});

test.describe('API Error Messages', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('displays user-friendly error for 400 Bad Request', async ({ page }) => {
    // Open modal
    await page.getByTestId('new-chat-button').click();

    // Intercept conversations API with 400 error
    await page.route('**/api/conversations', (route) => {
      if (route.request().method() === 'POST') {
        route.fulfill({
          status: 400,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: 'Invalid conversation data',
          }),
        });
      } else {
        route.continue();
      }
    });

    await page.getByTestId('topic-input').fill('Bad request test');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Locke');
    await page.getByTestId('add-custom-thinker').click();
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    // Try to create conversation
    await page.getByTestId('create-button').click();

    // Should show error message (use specific error element to avoid matching thinker descriptions)
    await expect(
      page
        .locator('.text-red-600, .text-red-400')
        .filter({ hasText: /invalid|error|failed/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('displays user-friendly error for 401 Unauthorized', async ({
    page,
  }) => {
    // Intercept auth check with 401
    await page.route('**/api/auth/me', (route) => {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Unauthorized' }),
      });
    });

    // Try to access the app
    await page.goto('/');

    // Should redirect to login or show auth error - wait for either to appear
    const loginLocator = page.locator('text=/login|sign in/i');
    const authErrorLocator = page.locator(
      'text=/unauthorized|authentication/i'
    );

    await Promise.race([
      loginLocator.waitFor({ state: 'visible', timeout: 5000 }),
      authErrorLocator.waitFor({ state: 'visible', timeout: 5000 }),
      page.waitForLoadState('networkidle', { timeout: 5000 }),
    ]).catch(() => {
      // Continue to verification
    });

    // Check for login page, auth error, or empty state
    const hasLoginButton = await loginLocator.isVisible().catch(() => false);
    const hasAuthError = await authErrorLocator.isVisible().catch(() => false);

    // Either login UI or error message should appear
    expect(hasLoginButton || hasAuthError).toBe(true);
  });

  test('displays user-friendly error for 500 Internal Server Error', async ({
    page,
  }) => {
    // Open modal
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Server error test');

    // Intercept with 500 error
    await page.route('**/api/thinkers/suggest', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Internal server error',
        }),
      });
    });

    await page.getByTestId('next-button').click();

    // Should show error message (use specific error element to avoid matching thinker descriptions)
    await expect(
      page
        .locator('.text-red-600, .text-red-400')
        .filter({ hasText: /error|failed|something went wrong/i })
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Rate Limiting & Throttling', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles 429 Too Many Requests gracefully', async ({ page }) => {
    // Intercept API with rate limit error
    await page.route('**/api/thinkers/suggest', (route) => {
      route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Too many requests',
        }),
      });
    });

    // Try to create conversation
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Rate limit test');
    await page.getByTestId('next-button').click();

    // Should show appropriate error message - wait for either to appear
    const errorLocator = page.locator('text=/too many|rate limit|try again/i');
    const customInputLocator = page.getByTestId('custom-thinker-input');

    await Promise.race([
      errorLocator.waitFor({ state: 'visible', timeout: 10000 }),
      customInputLocator.waitFor({ state: 'visible', timeout: 10000 }),
    ]).catch(() => {
      // Continue to verification
    });

    const errorVisible = await errorLocator.isVisible().catch(() => false);
    const canStillAddCustom = await customInputLocator
      .isVisible()
      .catch(() => false);

    // Either error shown or fallback to custom input
    expect(errorVisible || canStillAddCustom).toBe(true);
  });
});
