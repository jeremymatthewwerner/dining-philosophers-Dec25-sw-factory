/**
 * E2E test to reproduce issue #88:
 * "Asking to replace a suggested thinker with a new one fails with 'load failed'"
 *
 * Issue details:
 * - When clicking refresh on a thinker suggestion, it fails with "load failed"
 * - Suggestions seem to come back "right away" (suspiciously fast, suggesting possible bug)
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser } from './test-utils';

test.describe('Issue #88: Refresh thinker suggestion fails', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('refresh suggestion should complete without "load failed" error', async ({
    page,
  }) => {
    // Set up network request monitoring
    const apiCalls: {
      url: string;
      startTime: number;
      endTime?: number;
      status?: number;
      error?: string;
    }[] = [];

    page.on('request', (request) => {
      if (request.url().includes('/api/thinkers/suggest')) {
        apiCalls.push({ url: request.url(), startTime: Date.now() });
      }
    });

    page.on('response', (response) => {
      if (response.url().includes('/api/thinkers/suggest')) {
        const call = apiCalls.find(
          (c) => c.url === response.url() && !c.endTime
        );
        if (call) {
          call.endTime = Date.now();
          call.status = response.status();
        }
      }
    });

    page.on('requestfailed', (request) => {
      if (request.url().includes('/api/thinkers/suggest')) {
        const call = apiCalls.find(
          (c) => c.url === request.url() && !c.endTime
        );
        if (call) {
          call.endTime = Date.now();
          call.error = request.failure()?.errorText || 'Unknown error';
        }
        console.log(
          `Request failed: ${request.url()}, error: ${request.failure()?.errorText}`
        );
      }
    });

    // Open new chat modal
    await page.getByTestId('new-chat-button').click();
    const modal = page.getByTestId('new-chat-modal');
    await expect(modal).toBeVisible();

    // Enter a topic
    await page.getByTestId('topic-input').fill('Stoic philosophy and ethics');

    // Click Next to get suggestions
    await page.getByTestId('next-button').click();

    // Wait for thinker suggestions to load
    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Wait for at least one suggestion to appear
    const suggestions = page.getByTestId('thinker-suggestion');
    await expect(suggestions.first()).toBeVisible({ timeout: 30000 });

    // Get the initial suggestion name
    const firstSuggestion = suggestions.first();
    const initialName = await firstSuggestion
      .locator('div.font-medium')
      .textContent();
    console.log(`Initial suggestion: ${initialName}`);

    // Record current API call count
    const apiCallCountBefore = apiCalls.length;

    // Click the refresh button on the first suggestion
    const refreshButton = page.getByTestId('refresh-suggestion').first();
    await expect(refreshButton).toBeVisible();
    await expect(refreshButton).toBeEnabled();

    const refreshStartTime = Date.now();
    await refreshButton.click();

    // Wait for the spinner to appear (indicates refresh is in progress)
    // Note: This might be very fast if there's a bug
    const spinnerAppeared = await page
      .locator('[data-testid="refresh-suggestion"] svg.animate-spin')
      .isVisible()
      .catch(() => false);
    console.log(`Spinner appeared: ${spinnerAppeared}`);

    // Wait for the refresh to complete - either:
    // 1. A new name appears (success)
    // 2. An error message appears (failure)
    // 3. Timeout (hung)

    // Check for error message in the modal
    const errorMessage = page.locator(
      '[data-testid="new-chat-modal"] .text-red-600, [data-testid="new-chat-modal"] .text-red-400'
    );

    // Wait up to 20 seconds for either new suggestion or error
    let refreshSucceeded = false;
    let refreshError: string | null = null;

    try {
      await Promise.race([
        // Wait for suggestion to change
        (async () => {
          // Wait for spinner to disappear and check if name changed
          await page.waitForTimeout(500); // Give some time for state to update
          for (let i = 0; i < 40; i++) {
            const currentSpinner = await page
              .locator('[data-testid="refresh-suggestion"] svg.animate-spin')
              .first()
              .isVisible()
              .catch(() => false);
            if (!currentSpinner) {
              const newName = await firstSuggestion
                .locator('div.font-medium')
                .textContent();
              if (newName && newName !== initialName) {
                console.log(`Suggestion changed: ${initialName} -> ${newName}`);
                refreshSucceeded = true;
                return;
              }
            }
            await page.waitForTimeout(500);
          }
        })(),
        // Check for error message
        (async () => {
          try {
            await expect(errorMessage).toBeVisible({ timeout: 20000 });
            refreshError = await errorMessage.textContent();
            console.log(`Error message appeared: ${refreshError}`);
          } catch {
            // No error message appeared
          }
        })(),
      ]);
    } catch {
      console.log('Timeout waiting for refresh to complete');
    }

    const refreshEndTime = Date.now();
    const refreshDuration = refreshEndTime - refreshStartTime;
    console.log(`Refresh duration: ${refreshDuration}ms`);

    // Check for failed API calls
    const failedCalls = apiCalls.filter((c) => c.error);
    if (failedCalls.length > 0) {
      console.log('Failed API calls:', JSON.stringify(failedCalls, null, 2));
    }

    // Check for suspiciously fast responses (< 500ms suggests mock or cached data)
    const newCalls = apiCalls.slice(apiCallCountBefore);
    for (const call of newCalls) {
      if (call.endTime && call.startTime) {
        const duration = call.endTime - call.startTime;
        console.log(`API call duration: ${duration}ms, status: ${call.status}`);
        if (duration < 500 && call.status === 200) {
          console.warn(
            `SUSPICIOUS: API response came back in ${duration}ms - may indicate mock data`
          );
        }
      }
    }

    // Assertions
    expect(failedCalls.length).toBe(0); // No network failures
    expect(refreshError).toBeNull(); // No error message in UI
    expect(refreshSucceeded).toBe(true); // Suggestion should have changed

    // Verify the suggestion is still visible and has content
    await expect(firstSuggestion).toBeVisible();
    const finalName = await firstSuggestion
      .locator('div.font-medium')
      .textContent();
    expect(finalName).toBeTruthy();
    console.log(`Final suggestion name: ${finalName}`);
  });

  test('multiple rapid refresh clicks should not cause errors', async ({
    page,
  }) => {
    // Open modal and get to thinker step
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Modern economics');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId('thinker-suggestion').first()).toBeVisible({
      timeout: 30000,
    });

    // Rapidly click refresh button multiple times
    const refreshButton = page.getByTestId('refresh-suggestion').first();

    // Click 3 times in rapid succession
    await refreshButton.click();
    await page.waitForTimeout(200);
    await refreshButton.click();
    await page.waitForTimeout(200);
    await refreshButton.click();

    // Wait for all refreshes to complete (or fail)
    await page.waitForTimeout(5000);

    // Check no error message appeared
    const errorMessage = page.locator(
      '[data-testid="new-chat-modal"] .text-red-600, [data-testid="new-chat-modal"] .text-red-400'
    );
    const hasError = await errorMessage.isVisible().catch(() => false);

    if (hasError) {
      const errorText = await errorMessage.textContent();
      console.log(`Error after rapid clicks: ${errorText}`);
    }

    expect(hasError).toBe(false);
  });

  test('suggestion refresh API timing should be reasonable', async ({
    page,
  }) => {
    // Track API call timing
    let apiCallStart: number | null = null;
    let apiCallEnd: number | null = null;

    page.on('request', (request) => {
      if (request.url().includes('/api/thinkers/suggest')) {
        apiCallStart = Date.now();
      }
    });

    page.on('response', (response) => {
      if (response.url().includes('/api/thinkers/suggest')) {
        apiCallEnd = Date.now();
      }
    });

    // Open modal and get to thinker step
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Political philosophy');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId('thinker-suggestion').first()).toBeVisible({
      timeout: 30000,
    });

    // Reset timing for refresh call
    apiCallStart = null;
    apiCallEnd = null;

    // Click refresh
    await page.getByTestId('refresh-suggestion').first().click();

    // Wait for response
    await page.waitForTimeout(10000);

    if (apiCallStart && apiCallEnd) {
      const duration = apiCallEnd - apiCallStart;
      console.log(`Refresh API call duration: ${duration}ms`);

      // A real Claude API call should take at least 1-2 seconds
      // If it's < 500ms, something is wrong (cached/mocked response)
      if (duration < 500) {
        console.warn(
          `SUSPICIOUS: Response too fast (${duration}ms) - may not be hitting real Claude API`
        );
      }

      // If it's > 30s, there's a timeout issue
      if (duration > 30000) {
        console.warn(
          `WARNING: Response too slow (${duration}ms) - may indicate timeout issue`
        );
      }
    } else {
      console.log('Could not measure API timing');
    }
  });
});
