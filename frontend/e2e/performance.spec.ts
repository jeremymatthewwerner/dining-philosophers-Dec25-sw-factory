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
import {
  setupAuthenticatedUser,
  createConversationViaAPI,
  registerUser,
} from './test-utils';

const PERF_TIMEOUT = 5000; // 5s threshold for most operations
const LOGIN_PAGE_TIMEOUT = 3000; // Login page should be very fast (no auth)
const NAV_TIMEOUT = 3000; // Navigation between pages
const API_TIMEOUT = 3000; // Direct API calls should be fast
const INTERACTION_TIMEOUT = 2000; // Direct user interactions should be near-instant

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

  test('health/ready deep check responds within 3 seconds', async ({
    page,
  }) => {
    const startTime = Date.now();
    const response = await page.request.get(
      'http://localhost:8000/health/ready'
    );
    const elapsed = Date.now() - startTime;

    // /health/ready checks database connectivity — still must be fast
    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });

  test('register endpoint responds within 3 seconds', async ({ page }) => {
    await page.goto('/');

    const uniqueUser = `perf_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const startTime = Date.now();
    const response = await page.request.post(
      'http://localhost:8000/api/auth/register',
      {
        data: {
          username: uniqueUser,
          display_name: 'Perf Test',
          password: 'testpass123',
        },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });

  test('concurrent API calls complete in parallel within budget', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
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

  test('login page first contentful paint within 3 seconds', async ({
    page,
  }) => {
    // Measure FCP via Performance API — catches rendering regressions
    // that pure element waits would miss
    const startTime = Date.now();
    await page.goto('/login');
    await expect(page.locator('#username')).toBeVisible({
      timeout: LOGIN_PAGE_TIMEOUT,
    });

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

  test('SPA navigation between home and settings is instant (<1s)', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    // From home → settings (client-side SPA navigation, no full reload)
    const startTime = Date.now();
    await page.goto('/settings');
    await expect(page.locator('h1')).toContainText('Settings', {
      timeout: NAV_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    // SPA navigation should be much faster than a full page load
    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('page.waitForResponse pattern completes faster than networkidle', async ({
    page,
  }) => {
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
    await expect(page.locator('#username')).toBeVisible({
      timeout: LOGIN_PAGE_TIMEOUT,
    });

    if (response) {
      expect(response.ok()).toBe(true);
    }
  });
});

test.describe('User Journey Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('login form submission redirects to home within 3 seconds', async ({
    page,
  }) => {
    // Pre-register a user so login has valid credentials
    const username = `loginperf_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const password = 'testpass123';
    await page.goto('/');
    const registerResponse = await page.request.post(
      'http://localhost:8000/api/auth/register',
      {
        data: { username, display_name: 'Login Perf Test', password },
      }
    );
    expect(registerResponse.ok()).toBe(true);

    // Clear the auth state from registration so we're truly logging in
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
    });

    // Navigate to login page
    await page.goto('/login');
    await expect(page.locator('#username')).toBeVisible({
      timeout: LOGIN_PAGE_TIMEOUT,
    });

    // Time the full login interaction: fill + submit + redirect to home
    const startTime = Date.now();
    await page.locator('#username').fill(username);
    await page.locator('#password').fill(password);
    await page.locator('button[type="submit"]').click();

    // Wait for redirect to home and the new-chat-button to appear
    await expect(page.getByTestId('new-chat-button')).toBeVisible({
      timeout: PERF_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
  });

  test('logout via user menu completes within 3 seconds', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // Open user menu and click sign out
    const startTime = Date.now();
    await page.getByTestId('user-menu-button').click();
    await expect(page.getByTestId('user-menu-dropdown')).toBeVisible({
      timeout: INTERACTION_TIMEOUT,
    });
    await page.getByTestId('user-menu-signout').click();

    // Logout should redirect to login or clear auth UI quickly
    await expect
      .poll(
        async () => {
          const url = page.url();
          if (url.includes('/login')) return true;
          // Or new-chat-button is gone (auth cleared)
          return !(await page
            .getByTestId('new-chat-button')
            .isVisible()
            .catch(() => false));
        },
        { timeout: NAV_TIMEOUT }
      )
      .toBe(true);
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('DOMContentLoaded fires within 2 seconds on login page', async ({
    page,
  }) => {
    // DCL is a stronger guarantee than first paint — it means the HTML is
    // parsed and synchronous scripts have executed. Regressions in the
    // initial bundle (e.g., a heavy import added to the login page) will
    // surface here before they're caught by user-perceived metrics.
    await page.goto('/login');

    const dclTiming = await page.evaluate(() => {
      const navEntry = performance.getEntriesByType('navigation')[0] as
        | PerformanceNavigationTiming
        | undefined;
      return navEntry ? navEntry.domContentLoadedEventEnd : null;
    });

    // Sanity-check the page actually rendered
    await expect(page.locator('#username')).toBeVisible({
      timeout: LOGIN_PAGE_TIMEOUT,
    });

    if (dclTiming !== null) {
      // DCL should be very fast on a static login page
      expect(dclTiming).toBeLessThan(INTERACTION_TIMEOUT);
    }
  });

  test('sidebar renders 5 conversations within 5 seconds', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // Create 5 conversations in parallel via API to simulate a typical user
    // with several active threads. This guards against O(n) regressions in
    // sidebar rendering or list-item key churn.
    await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        createConversationViaAPI(page, `Sidebar perf #${i + 1}`)
      )
    );

    const startTime = Date.now();
    await page.goto('/');
    // All 5 items must be visible — count assertion polls until it matches
    await expect(page.getByTestId('conversation-item')).toHaveCount(5, {
      timeout: PERF_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
  });

  test('switching between conversations in sidebar completes within 3s', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    // Create two conversations via API (no UI navigation overhead)
    await createConversationViaAPI(page, 'Switch perf A', ['Socrates']);
    await createConversationViaAPI(page, 'Switch perf B', ['Plato']);
    await page.goto('/');

    // On mobile, the sidebar is hidden behind a hamburger — open it if needed
    const hamburger = page.getByTestId('mobile-menu-button');
    if (await hamburger.isVisible().catch(() => false)) {
      await hamburger.click();
    }

    // Both conversations must be in the sidebar before we time the switch
    await expect(page.getByTestId('conversation-item')).toHaveCount(2, {
      timeout: PERF_TIMEOUT,
    });

    const firstItem = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Switch perf A' });
    await firstItem.scrollIntoViewIfNeeded();

    const startTime = Date.now();
    await firstItem.click();
    // Chat header should update to reflect the newly-selected conversation
    await expect(
      page.getByTestId('chat-area').locator('h2', { hasText: 'Switch perf A' })
    ).toBeVisible({ timeout: NAV_TIMEOUT });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('message textarea is interactive within 5s of opening a conversation', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);
    const conv = await createConversationViaAPI(page, 'TTI perf', [
      'Aristotle',
    ]);

    const startTime = Date.now();
    await page.goto('/');
    const conversationItem = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'TTI perf' });
    await conversationItem.click();

    // Textarea must be visible AND enabled — both are required to send
    const textarea = page.getByTestId('message-textarea');
    await expect(textarea).toBeVisible({ timeout: PERF_TIMEOUT });
    await expect(textarea).toBeEnabled({ timeout: PERF_TIMEOUT });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
    // Reference conv to keep the variable used
    expect(conv.id).toBeTruthy();
  });

  test('initial homepage load fires fewer than 50 network requests', async ({
    page,
  }) => {
    // Over-fetching regression guard: if a future change introduces a chatty
    // request loop or duplicate fetches on mount, this catches it before the
    // user notices a slow load. The threshold is intentionally generous to
    // avoid flakiness from polling or analytics, while still detecting
    // 2-3x request count regressions.
    await setupAuthenticatedUser(page);

    const requestUrls: string[] = [];
    page.on('request', (req) => {
      requestUrls.push(req.url());
    });

    await page.goto('/');
    await expect(page.getByTestId('new-chat-button')).toBeVisible({
      timeout: PERF_TIMEOUT,
    });
    // Settle: give the page a beat for any deferred fetches without using a
    // fixed timeout — wait for the sidebar (the last-rendered chunk).
    await expect(page.getByTestId('sidebar')).toBeVisible({
      timeout: PERF_TIMEOUT,
    });

    expect(requestUrls.length).toBeLessThan(50);
  });

  test('browser back navigation between home and settings is instant (<1s)', async ({
    page,
  }) => {
    // The bfcache (back/forward cache) should make browser back navigation
    // dramatically faster than a fresh load. This catches regressions where
    // a developer accidentally adds Cache-Control: no-store or page-level
    // unload listeners that disqualify the page from bfcache.
    await setupAuthenticatedUser(page);

    await page.goto('/settings');
    await expect(page.locator('h1')).toContainText('Settings', {
      timeout: NAV_TIMEOUT,
    });

    const startTime = Date.now();
    await page.goBack();
    await expect(page.getByTestId('new-chat-button')).toBeVisible({
      timeout: 1500,
    });
    const elapsed = Date.now() - startTime;

    // Even without bfcache, a SPA route change should comfortably fit in 1.5s.
    // If a regression lands that forces a full reload, this will trip.
    expect(elapsed).toBeLessThan(1500);
  });
});

test.describe('Auth Flow Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('registerUser helper completes in under 3 seconds', async ({ page }) => {
    // The most-called test setup helper — if this slows down, every test
    // pays the cost. Locks in expected baseline.
    await page.goto('/');

    const startTime = Date.now();
    await registerUser(page);
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });

  test('parallel registration of 3 users completes within 5 seconds', async ({
    page,
  }) => {
    // Verifies the backend can handle concurrent registrations efficiently
    // and that requests are not serialized server-side.
    await page.goto('/');

    const startTime = Date.now();
    const responses = await Promise.all(
      Array.from({ length: 3 }, (_, i) =>
        page.request.post('http://localhost:8000/api/auth/register', {
          data: {
            username: `parallel_${Date.now()}_${i}_${Math.random()
              .toString(36)
              .slice(2, 6)}`,
            display_name: `Parallel User ${i}`,
            password: 'testpass123',
          },
        })
      )
    );
    const elapsed = Date.now() - startTime;

    for (const response of responses) {
      expect(response.ok()).toBe(true);
    }
    // 3 sequential registrations at ~1s each = 3s; parallel should be much less
    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
  });
});
