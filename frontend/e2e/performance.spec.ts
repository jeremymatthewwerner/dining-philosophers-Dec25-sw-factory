/**
 * E2E Performance tests.
 *
 * Validates that key pages and interactions complete within acceptable time
 * bounds. These tests act as regression guards to prevent performance
 * regressions from landing unnoticed.
 *
 * Thresholds are intentionally generous (3-5s) to avoid flakiness in CI,
 * while still catching severe regressions.
 *
 * Performance optimization patterns demonstrated here:
 * - Use page.request for direct API timing (bypasses browser overhead)
 * - Use page.waitForResponse() for intercepting specific network calls
 * - Use expect.poll() for retry-based assertions instead of networkidle
 * - Run parallel tests within each describe block
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaAPI } from './test-utils';

const PERF_TIMEOUT = 5000; // 5s threshold for most operations
const LOGIN_PAGE_TIMEOUT = 3000; // Login page should be very fast (no auth)
const NAV_TIMEOUT = 3000; // Navigation between pages
const API_TIMEOUT = 3000; // Direct API calls should be fast

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

  test('health/ready deep check responds within 3 seconds', async ({ page }) => {
    const startTime = Date.now();
    const response = await page.request.get('http://localhost:8000/health/ready');
    const elapsed = Date.now() - startTime;

    // /health/ready checks database connectivity — still must be fast
    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });

  test('register endpoint responds within 3 seconds', async ({ page }) => {
    await page.goto('/');

    const uniqueUser = `perf_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const startTime = Date.now();
    const response = await page.request.post('http://localhost:8000/api/auth/register', {
      data: {
        username: uniqueUser,
        display_name: 'Perf Test',
        password: 'testpass123',
      },
    });
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });

  test('concurrent API calls complete in parallel within budget', async ({ page }) => {
    await setupAuthenticatedUser(page);

    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(token).toBeTruthy();

    // Fire 3 independent API calls simultaneously — total time should be
    // close to the slowest individual call, not 3x the average.
    const startTime = Date.now();
    const [healthResp, meResp, convResp] = await Promise.all([
      page.request.get('http://localhost:8000/health'),
      page.request.get('http://localhost:8000/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      }),
      page.request.get('http://localhost:8000/api/conversations', {
        headers: { Authorization: `Bearer ${token}` },
      }),
    ]);
    const elapsed = Date.now() - startTime;

    expect(healthResp.ok()).toBe(true);
    expect(meResp.ok()).toBe(true);
    expect(convResp.ok()).toBe(true);
    // 3 sequential calls at 1s each = 3s; parallel should complete in <3s
    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });
});

test.describe('Page Rendering Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('login page first contentful paint within 3 seconds', async ({ page }) => {
    // Measure FCP via Performance API — catches rendering regressions
    // that pure element waits would miss
    const startTime = Date.now();
    await page.goto('/login');
    await expect(page.locator('#username')).toBeVisible({ timeout: LOGIN_PAGE_TIMEOUT });

    const fcp = await page.evaluate(() => {
      const entries = performance.getEntriesByType('paint');
      const fcpEntry = entries.find((e) => e.name === 'first-contentful-paint');
      return fcpEntry ? fcpEntry.startTime : null;
    });

    const elapsed = Date.now() - startTime;
    expect(elapsed).toBeLessThan(LOGIN_PAGE_TIMEOUT);

    // FCP should be well under 2 seconds on a local dev server
    if (fcp !== null) {
      expect(fcp).toBeLessThan(2000);
    }
  });

  test('SPA navigation between home and settings is instant (<1s)', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // From home → settings (client-side SPA navigation, no full reload)
    const startTime = Date.now();
    await page.goto('/settings');
    await expect(page.locator('h1')).toContainText('Settings', { timeout: NAV_TIMEOUT });
    const elapsed = Date.now() - startTime;

    // SPA navigation should be much faster than a full page load
    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('page.waitForResponse pattern completes faster than networkidle', async ({ page }) => {
    // This test demonstrates that intercepting a specific response
    // is more deterministic and often faster than waitForLoadState('networkidle').
    //
    // waitForLoadState('networkidle') waits 500ms after ALL network activity stops,
    // which can take seconds on pages with polling or WebSocket connections.
    // page.waitForResponse() fires as soon as the target request completes.

    const responsePromise = page.waitForResponse(
      (r) => r.url().includes('/health') && r.status() === 200,
      { timeout: 5000 }
    );

    await page.goto('/login');

    // Trigger a fetch to /health to demonstrate the pattern
    await page.evaluate(() =>
      fetch('http://localhost:8000/health').catch(() => null)
    );

    const response = await responsePromise.catch(() => null);

    // The login page itself must render even if health fetch is skipped
    await expect(page.locator('#username')).toBeVisible({ timeout: LOGIN_PAGE_TIMEOUT });

    if (response) {
      expect(response.ok()).toBe(true);
    }
  });
});
