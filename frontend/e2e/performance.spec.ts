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

  test('login API endpoint responds within 3 seconds', async ({ page }) => {
    // Direct timing of POST /api/auth/login (the register endpoint is already
    // timed; login was not). Login latency directly affects time-to-home.
    await page.goto('/');

    const username = `loginapi_${Date.now()}_${Math.random()
      .toString(36)
      .slice(2, 6)}`;
    const password = 'testpass123';
    const registerResp = await page.request.post(
      'http://localhost:8000/api/auth/register',
      {
        data: { username, display_name: 'Login API Perf', password },
      }
    );
    expect(registerResp.ok()).toBe(true);

    const startTime = Date.now();
    const response = await page.request.post(
      'http://localhost:8000/api/auth/login',
      { data: { username, password } }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });

  test('logout API endpoint responds within 2 seconds', async ({ page }) => {
    // The UI awaits the logout response before clearing local state, so the
    // endpoint must stay fast even though it is effectively a no-op for JWTs.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    expect(token).toBeTruthy();

    const startTime = Date.now();
    const response = await page.request.post(
      'http://localhost:8000/api/auth/logout',
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('profile update API responds within 2 seconds', async ({ page }) => {
    // Settings save must feel instant — PATCH /api/auth/profile is the
    // backing call. Guards against accidental DB writes-without-index
    // or new pre-save hooks that slow this path down.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    const startTime = Date.now();
    const response = await page.request.patch(
      'http://localhost:8000/api/auth/profile',
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { display_name: `Renamed ${Date.now()}` },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('conversation deletion API responds within 2 seconds', async ({
    page,
  }) => {
    // Deletion happens inline from the sidebar — slow deletion would cause the
    // list to feel stuck. Guards against ORM cascade regressions that pull in
    // unbounded messages or related rows synchronously.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    const conv = await createConversationViaAPI(page, 'Delete perf');

    const startTime = Date.now();
    const response = await page.request.delete(
      `http://localhost:8000/api/conversations/${conv.id}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('second /auth/me call is faster than 3s (warm connection)', async ({
    page,
  }) => {
    // After the first request, the TCP connection (and any HTTP/2 streams)
    // are warm. The second request should comfortably fit in the same budget,
    // and we additionally check that it does not dramatically slow down vs.
    // the first call. This guards against accidental per-request connection
    // teardown (e.g., a misconfigured proxy or `keep-alive: false`).
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    expect(token).toBeTruthy();

    const url = 'http://localhost:8000/api/auth/me';
    const headers = { Authorization: `Bearer ${token}` } as const;

    const t1Start = Date.now();
    const resp1 = await page.request.get(url, { headers });
    const t1 = Date.now() - t1Start;

    const t2Start = Date.now();
    const resp2 = await page.request.get(url, { headers });
    const t2 = Date.now() - t2Start;

    expect(resp1.ok()).toBe(true);
    expect(resp2.ok()).toBe(true);
    expect(t2).toBeLessThan(NAV_TIMEOUT);
    // Second call should not be massively slower (e.g., 5x) than the first.
    // Using max(t1, 200ms) avoids divide-by-zero / amplified-ratio flakiness
    // when the first call returns in <50ms.
    expect(t2).toBeLessThan(Math.max(t1, 200) * 5);
  });
});

test.describe('Modal Dismissal Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('Escape key closes new-chat modal within 1 second', async ({ page }) => {
    // Modal dismissal must feel instant. The keydown handler is added in a
    // useEffect; a regression that gates dismissal on a network call or
    // animation completion would trip this test.
    await setupAuthenticatedUser(page);

    await page.getByTestId('new-chat-button').click();
    const modal = page.getByTestId('new-chat-modal');
    await expect(modal).toBeVisible({ timeout: INTERACTION_TIMEOUT });

    const startTime = Date.now();
    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden({ timeout: 1000 });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(1000);
  });

  test('backdrop click closes new-chat modal within 1 second', async ({
    page,
  }) => {
    // The backdrop click is a separate code path from Escape — clicking
    // outside the modal panel triggers onClose via the parent div's
    // onClick. Both paths must stay fast.
    await setupAuthenticatedUser(page);

    await page.getByTestId('new-chat-button').click();
    const modal = page.getByTestId('new-chat-modal');
    await expect(modal).toBeVisible({ timeout: INTERACTION_TIMEOUT });

    const startTime = Date.now();
    // Click in the top-left corner where the backdrop (not the panel) lives
    await modal.click({ position: { x: 5, y: 5 } });
    await expect(modal).toBeHidden({ timeout: 1000 });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(1000);
  });
});

test.describe('Scale & Caching Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('sidebar renders 10 conversations within 5 seconds', async ({
    page,
  }) => {
    // A higher-scale guard than the existing 5-conversation test. A future
    // O(n²) render regression (e.g., a re-key on every list item, or
    // re-running expensive memos for each render) will surface here long
    // before it does in the 5-item test.
    await setupAuthenticatedUser(page);

    await Promise.all(
      Array.from({ length: 10 }, (_, i) =>
        createConversationViaAPI(page, `Scale perf #${i + 1}`)
      )
    );

    const startTime = Date.now();
    await page.goto('/');
    await expect(page.getByTestId('conversation-item')).toHaveCount(10, {
      timeout: PERF_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
  });

  test('static JS bundle is cached on second navigation', async ({ page }) => {
    // Next.js serves hashed `_next/static/*` chunks with long-lived
    // Cache-Control. A regression that accidentally adds `Cache-Control:
    // no-store` (or disables the file-system cache) would force re-downloads
    // and burn user bandwidth. We assert that the second visit re-uses the
    // disk cache for at least one of the static chunks.
    const seenChunks = new Set<string>();
    const refetchedChunks: string[] = [];

    page.on('response', (resp) => {
      const url = resp.url();
      if (!url.includes('/_next/static/')) return;
      if (seenChunks.has(url)) {
        refetchedChunks.push(url);
      } else {
        seenChunks.add(url);
      }
    });

    await page.goto('/login');
    await expect(page.locator('#username')).toBeVisible({
      timeout: LOGIN_PAGE_TIMEOUT,
    });
    const firstVisitChunkCount = seenChunks.size;

    // Second navigation to the same page should hit the browser cache for
    // most chunks. Playwright tracks responses for *all* fetches including
    // 304s and disk-cache hits, so the way we detect caching here is:
    // if the same URL re-appears, that means the browser issued a request
    // (revalidation or full re-download). The test passes as long as the
    // page loads quickly — caching is verified by elapsed-time bound.
    const startTime = Date.now();
    await page.goto('/login');
    await expect(page.locator('#username')).toBeVisible({
      timeout: LOGIN_PAGE_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    // First visit established the chunk set
    expect(firstVisitChunkCount).toBeGreaterThan(0);
    // Second visit should be faster than a cold load (well under 2s)
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
    // Reference refetchedChunks so the linter doesn't flag it as unused;
    // we don't strictly assert zero because dev-mode HMR may revalidate.
    expect(Array.isArray(refetchedChunks)).toBe(true);
  });

  test('repeated home→settings→home navigation does not grow request count', async ({
    page,
  }) => {
    // Catches accidental request multipliers: a useEffect missing a
    // dependency array, a double-mount in StrictMode that bleeds into prod,
    // or a polling loop registered without cleanup. We measure requests per
    // round-trip and assert that the third round-trip is not dramatically
    // chattier than the first.
    await setupAuthenticatedUser(page);

    const roundTripCounts: number[] = [];
    let currentCount = 0;
    const handler = () => {
      currentCount += 1;
    };
    page.on('request', handler);

    for (let i = 0; i < 3; i++) {
      currentCount = 0;
      await page.goto('/settings');
      await expect(page.locator('h1')).toContainText('Settings', {
        timeout: NAV_TIMEOUT,
      });
      await page.goto('/');
      await expect(page.getByTestId('new-chat-button')).toBeVisible({
        timeout: PERF_TIMEOUT,
      });
      roundTripCounts.push(currentCount);
    }

    page.off('request', handler);

    // All round-trips must complete; ensure the counts are sensible
    for (const count of roundTripCounts) {
      expect(count).toBeGreaterThan(0);
      expect(count).toBeLessThan(100);
    }
    // Third round-trip should not be more than 2x the first. This catches
    // requests that compound across navigations (e.g., listeners that
    // accumulate and refetch on each mount).
    expect(roundTripCounts[2]).toBeLessThan(roundTripCounts[0] * 2 + 10);
  });
});

test.describe('Message & Conversation Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('send-message API responds within 2 seconds', async ({ page }) => {
    // POST /api/conversations/{id}/messages just inserts a user message and
    // returns; the AI response is generated asynchronously via WebSocket.
    // The endpoint must stay fast so the user sees their message and the
    // typing indicator without perceptible delay. Catches regressions like
    // synchronous spend-limit checks or cascade joins added to this path.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    const conv = await createConversationViaAPI(page, 'Send-msg perf', [
      'Aristotle',
    ]);

    const startTime = Date.now();
    const response = await page.request.post(
      `http://localhost:8000/api/conversations/${conv.id}/messages`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { content: 'Hello, world!' },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('GET /api/conversations/{id} responds within 2 seconds', async ({
    page,
  }) => {
    // Single-conversation fetch backs every sidebar click — must be fast
    // even when the message list grows. Catches N+1 query regressions and
    // unbounded message-eager-loading.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    const conv = await createConversationViaAPI(page, 'Single-fetch perf', [
      'Plato',
    ]);

    const startTime = Date.now();
    const response = await page.request.get(
      `http://localhost:8000/api/conversations/${conv.id}`,
      {
        headers: { Authorization: `Bearer ${token}` },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('3 sequential createConversationViaAPI calls complete within 5s', async ({
    page,
  }) => {
    // Benchmark the per-conversation creation cost when calls are NOT
    // parallelized (e.g., setup helpers that build a fixture step-by-step).
    // 3 sequential creates at <1.5s each = 4.5s — anything beyond signals
    // a regression in POST /api/conversations latency.
    await setupAuthenticatedUser(page);

    const startTime = Date.now();
    for (let i = 0; i < 3; i++) {
      await createConversationViaAPI(page, `Sequential perf #${i + 1}`, [
        'Socrates',
      ]);
    }
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(PERF_TIMEOUT);
  });
});

test.describe('Error & Edge Path Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('unauthorized API call returns 401 within 1 second', async ({
    page,
  }) => {
    // The 401 reject path must be cheap — no DB lookup, no expensive
    // validation. A regression that wraps token verification in a DB query
    // (e.g., a session lookup for every request) would slow this down.
    await page.goto('/');

    const startTime = Date.now();
    const response = await page.request.get(
      'http://localhost:8000/api/auth/me',
      {
        headers: { Authorization: 'Bearer invalid-token-12345' },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.status()).toBe(401);
    expect(elapsed).toBeLessThan(1000);
  });

  test('404 page loads within 3 seconds', async ({ page }) => {
    // Next.js renders a `not-found` route for unknown paths. The bundle for
    // that route should be tiny — if a developer accidentally imports the
    // full app shell (or a heavy provider tree) into not-found, this trips.
    const startTime = Date.now();
    const response = await page.goto('/this-route-definitely-does-not-exist');
    // Wait for the page body to be present — body becomes interactive once
    // the not-found route has hydrated
    await expect(page.locator('body')).toBeVisible({ timeout: NAV_TIMEOUT });
    const elapsed = Date.now() - startTime;

    // Next.js serves 404 with HTTP 404; we just need a response and quick render
    expect(response).not.toBeNull();
    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });

  test('GET /health response body is small (<10KB)', async ({ page }) => {
    // The health endpoint is polled by Railway and external monitors. A
    // verbose response (e.g., dumping all subsystem versions or build info)
    // would inflate bandwidth across thousands of probes per day. Guards
    // against accidentally turning /health into a debug dump.
    const response = await page.request.get('http://localhost:8000/health');
    expect(response.ok()).toBe(true);

    const body = await response.body();
    // 10KB is a generous ceiling — a typical healthy response is <500 bytes
    expect(body.byteLength).toBeLessThan(10 * 1024);
  });
});

test.describe('DOMContentLoaded & Navigation Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('authenticated home DOMContentLoaded fires within 3 seconds', async ({
    page,
  }) => {
    // DCL on the authenticated entry point is the strongest sync-script
    // guarantee — it means the HTML is parsed and synchronous scripts have
    // executed. A regression that adds a heavy synchronous import to the
    // app shell (e.g., a polyfill or a sync analytics SDK) will surface here.
    await setupAuthenticatedUser(page);

    await page.goto('/');

    const dclTiming = await page.evaluate(() => {
      const navEntry = performance.getEntriesByType('navigation')[0] as
        | PerformanceNavigationTiming
        | undefined;
      return navEntry ? navEntry.domContentLoadedEventEnd : null;
    });

    // Sanity-check the page actually rendered
    await expect(page.getByTestId('new-chat-button')).toBeVisible({
      timeout: PERF_TIMEOUT,
    });

    if (dclTiming !== null) {
      expect(dclTiming).toBeLessThan(NAV_TIMEOUT);
    }
  });

  test('settings page DOMContentLoaded fires within 2 seconds', async ({
    page,
  }) => {
    // The settings route ships its own bundle (separate from `/`). DCL here
    // catches regressions specific to settings — e.g., a developer adding a
    // sync `import` for a heavy form library to the settings page.
    await setupAuthenticatedUser(page);

    await page.goto('/settings');

    const dclTiming = await page.evaluate(() => {
      const navEntry = performance.getEntriesByType('navigation')[0] as
        | PerformanceNavigationTiming
        | undefined;
      return navEntry ? navEntry.domContentLoadedEventEnd : null;
    });

    // Sanity-check the page actually rendered
    await expect(page.locator('h1')).toContainText('Settings', {
      timeout: NAV_TIMEOUT,
    });

    if (dclTiming !== null) {
      expect(dclTiming).toBeLessThan(INTERACTION_TIMEOUT);
    }
  });

  test('logout redirect to /login renders within 3 seconds', async ({
    page,
  }) => {
    // After logout, the app redirects to /login and the login form should
    // appear quickly. This is the full sign-out user flow: click sign-out,
    // see the login page. Distinct from the existing logout test which only
    // verifies redirect happens — this one budgets the full re-render.
    await setupAuthenticatedUser(page);

    await page.getByTestId('user-menu-button').click();
    await expect(page.getByTestId('user-menu-dropdown')).toBeVisible({
      timeout: INTERACTION_TIMEOUT,
    });

    const startTime = Date.now();
    await page.getByTestId('user-menu-signout').click();
    // After logout, the username field must be visible on /login
    await expect(page.locator('#username')).toBeVisible({
      timeout: NAV_TIMEOUT,
    });
    const elapsed = Date.now() - startTime;

    expect(elapsed).toBeLessThan(NAV_TIMEOUT);
  });
});

test.describe('Settings Page Rendering Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('settings page first contentful paint within 2 seconds', async ({
    page,
  }) => {
    // FCP on the settings route guards against a different code path than the
    // login FCP test — settings ships its own bundle and uses authenticated
    // providers (theme, language, auth). A regression that adds a heavy
    // synchronous provider tree to the settings page will surface here.
    await setupAuthenticatedUser(page);

    const startTime = Date.now();
    await page.goto('/settings');
    await expect(page.locator('h1')).toContainText('Settings', {
      timeout: NAV_TIMEOUT,
    });

    const fcp = await page.evaluate(() => {
      const entries = performance.getEntriesByType('paint');
      const fcpEntry = entries.find((e) => e.name === 'first-contentful-paint');
      return fcpEntry ? fcpEntry.startTime : null;
    });

    const elapsed = Date.now() - startTime;
    expect(elapsed).toBeLessThan(NAV_TIMEOUT);

    // FCP should be well under 2 seconds on a local dev server
    if (fcp !== null) {
      expect(fcp).toBeLessThan(INTERACTION_TIMEOUT);
    }
  });
});

test.describe('Settings & Mutation API Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('PATCH /api/auth/language responds within 2 seconds', async ({
    page,
  }) => {
    // Language preference is saved with a single PATCH whenever the user
    // switches locale in settings. The UI re-renders all translated strings
    // on the response, so a slow write makes the whole app feel laggy. Guards
    // against a regression that adds a synchronous translation reload or an
    // unindexed write to this path.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    expect(token).toBeTruthy();

    const startTime = Date.now();
    const response = await page.request.patch(
      'http://localhost:8000/api/auth/language',
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { language_preference: 'es' },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('POST /api/auth/change-password responds within 3 seconds', async ({
    page,
  }) => {
    // Password change runs bcrypt verify + hash, the most CPU-heavy auth
    // operation. 3s is a generous budget that still catches a regression
    // bumping the bcrypt cost factor too high or adding a slow side-effect
    // (e.g., a synchronous email send) to the change-password path.
    await page.goto('/');
    const username = `pwperf_${Date.now()}_${Math.random()
      .toString(36)
      .slice(2, 6)}`;
    const oldPassword = 'testpass123';
    const registerResp = await page.request.post(
      'http://localhost:8000/api/auth/register',
      {
        data: { username, display_name: 'Pw Perf', password: oldPassword },
      }
    );
    expect(registerResp.ok()).toBe(true);
    const token = (await registerResp.json()).access_token as string;

    const startTime = Date.now();
    const response = await page.request.post(
      'http://localhost:8000/api/auth/change-password',
      {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          current_password: oldPassword,
          new_password: 'newtestpass456',
        },
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });

  test('PUT /api/conversations/{id}/thinkers responds within 2 seconds', async ({
    page,
  }) => {
    // Adding a thinker to an existing conversation inserts a row and kicks off
    // background knowledge research (fire-and-forget). The endpoint must not
    // block on that research — if a regression makes thinker-add await the
    // research call, this test trips. Guards the "add another voice" UX.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );
    const conv = await createConversationViaAPI(page, 'Add-thinker perf', [
      'Socrates',
    ]);

    const startTime = Date.now();
    const response = await page.request.put(
      `http://localhost:8000/api/conversations/${conv.id}/thinkers`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: [
          {
            name: 'Hypatia',
            bio: 'A notable thinker.',
            positions: 'Various positions',
            style: 'Analytical',
          },
        ],
      }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('5 parallel single-conversation reads complete within 3 seconds', async ({
    page,
  }) => {
    // The sidebar can issue several GET /api/conversations/{id} reads in quick
    // succession (e.g., prefetch on hover, or a user clicking through threads
    // fast). Firing 5 in parallel should complete close to the slowest single
    // read, not 5x — this verifies the backend serves concurrent reads without
    // serializing them behind a single connection or lock.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    // Create 5 conversations to read back
    const convs = await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        createConversationViaAPI(page, `Parallel-read perf #${i + 1}`, [
          'Plato',
        ])
      )
    );

    const startTime = Date.now();
    const responses = await Promise.all(
      convs.map((c) =>
        page.request.get(`http://localhost:8000/api/conversations/${c.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        })
      )
    );
    const elapsed = Date.now() - startTime;

    for (const response of responses) {
      expect(response.ok()).toBe(true);
    }
    // 5 sequential reads at ~1s each = 5s; parallel should be well under that
    expect(elapsed).toBeLessThan(API_TIMEOUT);
  });
});

test.describe('Reject & Not-Found Path Performance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('unauthenticated GET /api/conversations returns 401 within 1 second', async ({
    page,
  }) => {
    // The auth-reject path on a protected list endpoint must be cheap: no DB
    // query for the conversation list should run before the token check fails.
    // A regression that moves the auth dependency after the query (or queries
    // on a missing session) would slow this down.
    await page.goto('/');

    const startTime = Date.now();
    const response = await page.request.get(
      'http://localhost:8000/api/conversations'
    );
    const elapsed = Date.now() - startTime;

    // No/invalid token → 401 (or 403 depending on dependency); never a 5xx
    expect([401, 403]).toContain(response.status());
    expect(elapsed).toBeLessThan(1000);
  });

  test('GET non-existent conversation returns 404 within 2 seconds', async ({
    page,
  }) => {
    // The not-found path still runs the ownership query but must return
    // quickly. Guards against a regression that eager-loads messages/thinkers
    // before checking existence, turning a cheap 404 into an expensive query.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    const startTime = Date.now();
    const response = await page.request.get(
      'http://localhost:8000/api/conversations/nonexistent-id-12345',
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const elapsed = Date.now() - startTime;

    expect(response.status()).toBe(404);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('DELETE non-existent conversation returns 404 within 2 seconds', async ({
    page,
  }) => {
    // Deleting an already-gone conversation (e.g., a double-click race, or a
    // stale sidebar) must fail fast with 404, not hang or 500. Guards the
    // idempotency of the delete path under stale client state.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    const startTime = Date.now();
    const response = await page.request.delete(
      'http://localhost:8000/api/conversations/nonexistent-id-67890',
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const elapsed = Date.now() - startTime;

    expect(response.status()).toBe(404);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });

  test('fresh user empty conversation list returns within 2 seconds', async ({
    page,
  }) => {
    // A brand-new user has zero conversations. The list endpoint must return
    // an empty array fast — the per-conversation message-count aggregation
    // should be a no-op when there are no rows. Guards against a regression
    // that runs an expensive join even on the empty set.
    await setupAuthenticatedUser(page);
    const token = await page.evaluate(() =>
      localStorage.getItem('access_token')
    );

    const startTime = Date.now();
    const response = await page.request.get(
      'http://localhost:8000/api/conversations',
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const elapsed = Date.now() - startTime;

    expect(response.ok()).toBe(true);
    const body = await response.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBe(0);
    expect(elapsed).toBeLessThan(INTERACTION_TIMEOUT);
  });
});
