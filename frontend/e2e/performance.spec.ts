/**
 * E2E Performance tests.
 *
 * Validates that key pages and interactions complete within acceptable time
 * bounds. These tests act as regression guards to prevent performance
 * regressions from landing unnoticed.
 *
 * Thresholds are intentionally generous (3-5s) to avoid flakiness in CI,
 * while still catching severe regressions.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaAPI } from './test-utils';

const PERF_TIMEOUT = 5000; // 5s threshold for most operations
const LOGIN_PAGE_TIMEOUT = 3000; // Login page should be very fast (no auth)
const NAV_TIMEOUT = 3000; // Navigation between pages

test.describe('Page Load Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('login page loads within 3 seconds', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/login');
    await expect(page.locator('#username')).toBeVisible({
      timeout: LOGIN_PAGE_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    // Login page (static, no auth) must be fast
    expect(elapsed).toBeLessThan(LOGIN_PAGE_TIMEOUT);
  });

  test('register page loads within 3 seconds', async ({ page }) => {
    const startTime = Date.now();
    await page.goto('/register');
    await expect(page.locator('#username')).toBeVisible({
      timeout: LOGIN_PAGE_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(LOGIN_PAGE_TIMEOUT);
  });

  test('authenticated homepage loads within 5 seconds', async ({ page }) => {
    const startTime = Date.now();
    await setupAuthenticatedUser(page);
    // setupAuthenticatedUser already navigates to '/' — wait for key UI element
    await expect(page.getByTestId('new-chat-button')).toBeVisible({
      timeout: PERF_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
  });

  test('sidebar renders within 5 seconds on authenticated load', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    const startTime = Date.now();
    await expect(page.getByTestId('sidebar')).toBeVisible({
      timeout: PERF_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
  });
});

test.describe('Interaction Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('conversation list renders within 5 seconds after creating conversation', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    // Create conversation via API (no UI overhead)
    await createConversationViaAPI(page, 'Performance test conversation');

    // Measure how fast the sidebar populates after navigation
    const startTime = Date.now();
    await page.goto('/');
    await expect(page.getByTestId('conversation-item')).toBeVisible({
      timeout: PERF_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
  });

  test('navigating to settings page completes within 3 seconds', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    const startTime = Date.now();
    await page.goto('/settings');
    await expect(page.locator('h1')).toContainText('Settings', {
      timeout: NAV_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('new conversation modal opens within 2 seconds', async ({ page }) => {
    await setupAuthenticatedUser(page);

    const newChatButton = page.getByTestId('new-chat-button');
    await expect(newChatButton).toBeVisible();

    const startTime = Date.now();
    await newChatButton.click();
    await expect(page.getByTestId('topic-input')).toBeVisible({
      timeout: 2000,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(2000);
  });
});

test.describe('API Response Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('auth/me endpoint responds within 3 seconds', async ({ page }) => {
    await setupAuthenticatedUser(page);

    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    expect(token).toBeTruthy();

    const startTime = Date.now();
    const response = await page.request.get(
      'http://localhost:8000/api/auth/me',
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('conversations list endpoint responds within 3 seconds', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    expect(token).toBeTruthy();

    const startTime = Date.now();
    const response = await page.request.get(
      'http://localhost:8000/api/conversations',
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('health endpoint responds within 2 seconds', async ({ page }) => {
    const startTime = Date.now();
    const response = await page.request.get('http://localhost:8000/health');
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(2000);
  });

  test('user registration endpoint completes within 2 seconds', async ({
    page,
  }) => {
    const uniqueUsername = `perf_reg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const startTime = Date.now();
    const response = await page.request.post(
      'http://localhost:8000/api/auth/register',
      {
        data: {
          username: uniqueUsername,
          display_name: 'Perf Test User',
          password: 'testpass123',
        },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(2000);
  });

  test('conversation creation via API completes within 3 seconds', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    expect(token).toBeTruthy();

    const startTime = Date.now();
    const response = await page.request.post(
      'http://localhost:8000/api/conversations',
      {
        data: {
          topic: 'Performance test conversation',
          thinkers: [
            {
              name: 'Aristotle',
              bio: 'Greek philosopher.',
              positions: 'Virtue ethics',
              style: 'Analytical',
            },
          ],
        },
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('thinker suggestions endpoint responds within 3 seconds', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    expect(token).toBeTruthy();

    const startTime = Date.now();
    const response = await page.request.post(
      'http://localhost:8000/api/thinkers/suggest',
      {
        data: { topic: 'philosophy of mind' },
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });
});
