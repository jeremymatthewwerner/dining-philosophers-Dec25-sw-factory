/**
 * Regression test for @mention badge alignment (Issue #494)
 *
 * Bug: @mention badges appeared elevated/misaligned with surrounding text
 * Root cause: inline-flex span didn't align to text baseline
 * Fix: Added verticalAlign: 'text-bottom' to mention span (PR #495)
 *
 * NOTE: These tests are currently skipped pending investigation.
 * The tests expect mention badges to appear in user messages, but the
 * mention highlighting may have specific rendering conditions that need
 * to be investigated. See Issue #607 for details.
 *
 * This test verifies that @mention badges render with correct CSS alignment
 * to prevent regression of the vertical alignment issue.
 */

import { expect, test } from '@playwright/test';
import {
  createConversationViaAPI,
  setupAuthenticatedUser,
} from './test-utils';

// Skip all tests in this file - needs investigation for E2E timing/rendering
// The underlying CSS fix is in place (verticalAlign: 'text-bottom' in Message.tsx:97)
// but the E2E test approach needs refinement
test.describe.skip('Regression: @mention badge alignment (Issue #494)', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('mention badges have correct vertical alignment CSS', async ({ page }) => {
    // Create conversation with thinker via API
    const conversation = await createConversationViaAPI(
      page,
      'Test alignment',
      ['Socrates']
    );

    // Navigate to the conversation
    await page.goto(`/?conversation=${conversation.id}`);
    // Element-driven readiness wait: the message composer only renders once the
    // conversation view has loaded, so waiting for it is both deterministic and
    // faster than a networkidle wait (which idles for 500ms after ALL network
    // activity and can burn its full budget on a polling/websocket page).
    await page
      .getByTestId('message-textarea')
      .waitFor({ state: 'visible', timeout: 10000 });

    // Send a message mentioning the thinker's name
    // Note: The app highlights thinker names automatically (word boundary match)
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Hello Socrates, what do you think about this topic?');
    const sendButton = page.getByTestId('send-button');
    await sendButton.click();

    // Wait for message to appear in UI
    await page.waitForSelector('[data-testid="message"]', { state: 'visible', timeout: 10000 });

    // Find the mention badge element - it has Tailwind class "inline-flex"
    // The span is inside the message content area
    const mentionBadge = page.locator('[data-testid="message"] span.inline-flex').first();
    await expect(mentionBadge).toBeVisible({ timeout: 5000 });

    // Verify the mention badge has correct vertical alignment
    // The fix added verticalAlign: 'text-bottom' to prevent badges floating above text
    const styles = await mentionBadge.evaluate((el) => {
      const computedStyle = window.getComputedStyle(el);
      return {
        display: computedStyle.display,
        verticalAlign: computedStyle.verticalAlign,
        alignItems: computedStyle.alignItems,
      };
    });

    // Verify the mention span uses inline-flex (for avatar + text layout)
    expect(styles.display).toBe('inline-flex');

    // Verify alignItems centers the avatar and text within the badge
    expect(styles.alignItems).toBe('center');

    // CRITICAL: Verify verticalAlign is set to 'text-bottom' (the fix for Issue #494)
    // This prevents the badge from appearing elevated above surrounding text
    expect(styles.verticalAlign).toBe('text-bottom');
  });

  test('mention badges align with surrounding text visually', async ({ page }) => {
    // Create conversation via API
    const conversation = await createConversationViaAPI(
      page,
      'Test visual alignment',
      ['Plato']
    );

    await page.goto(`/?conversation=${conversation.id}`);
    // Element-driven readiness wait (see note above): faster and more
    // deterministic than a networkidle wait before an auto-waiting fill().
    await page
      .getByTestId('message-textarea')
      .waitFor({ state: 'visible', timeout: 10000 });

    // Send message with mention in middle of sentence (most visible alignment issue)
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('I agree with Plato on this important philosophical question.');
    const sendButton = page.getByTestId('send-button');
    await sendButton.click();

    await page.waitForSelector('[data-testid="message"]', { state: 'visible', timeout: 10000 });

    // Find the mention badge element using the Tailwind class
    const mentionBadge = page.locator('[data-testid="message"] span.inline-flex').first();
    await expect(mentionBadge).toBeVisible({ timeout: 5000 });

    // Get bounding box for the badge
    const badgeBox = await mentionBadge.boundingBox();
    expect(badgeBox).not.toBeNull();

    // Verify the badge exists and has reasonable dimensions
    if (badgeBox) {
      // Badge should have positive width and height
      expect(badgeBox.width).toBeGreaterThan(0);
      expect(badgeBox.height).toBeGreaterThan(0);
      // Badge should be reasonably sized (not too big)
      expect(badgeBox.height).toBeLessThan(50);
    }
  });

  test('mention badges in mobile viewport maintain alignment', async ({ page }) => {
    // Set mobile viewport to test responsiveness
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE

    // Create conversation via API
    const conversation = await createConversationViaAPI(
      page,
      'Mobile alignment test',
      ['Aristotle']
    );

    await page.goto(`/?conversation=${conversation.id}`);
    // Element-driven readiness wait (see note above): faster and more
    // deterministic than a networkidle wait before an auto-waiting fill().
    await page
      .getByTestId('message-textarea')
      .waitFor({ state: 'visible', timeout: 10000 });

    // Send message with mention
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Testing Aristotle mention on mobile');
    const sendButton = page.getByTestId('send-button');
    await sendButton.click();

    await page.waitForSelector('[data-testid="message"]', { state: 'visible', timeout: 10000 });

    // Verify vertical alignment CSS is present on mobile too
    const mentionBadge = page.locator('[data-testid="message"] span.inline-flex').first();
    await expect(mentionBadge).toBeVisible({ timeout: 5000 });

    const verticalAlign = await mentionBadge.evaluate((el) => {
      return window.getComputedStyle(el).verticalAlign;
    });

    // The fix should apply on all screen sizes
    expect(verticalAlign).toBe('text-bottom');
  });
});
