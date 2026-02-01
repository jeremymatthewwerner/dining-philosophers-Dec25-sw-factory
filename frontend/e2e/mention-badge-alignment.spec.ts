/**
 * Regression test for @mention badge alignment (Issue #494)
 *
 * Bug: @mention badges appeared elevated/misaligned with surrounding text
 * Root cause: inline-flex span didn't align to text baseline
 * Fix: Added verticalAlign: 'text-bottom' to mention span (PR #495)
 *
 * This test verifies that @mention badges render with correct CSS alignment
 * to prevent regression of the vertical alignment issue.
 */

import { expect, test } from '@playwright/test';
import {
  cleanupTestUser,
  createConversationViaAPI,
  loginViaUI,
  registerViaUI,
  sendMessageViaAPI,
} from './helpers';

test.describe('Regression: @mention badge alignment (Issue #494)', () => {
  const testUsername = `mention-align-${Date.now()}`;
  const testPassword = 'testpass123';

  test.afterEach(async () => {
    await cleanupTestUser(testUsername);
  });

  test('mention badges have correct vertical alignment CSS', async ({ page }) => {
    // Register, login, and create conversation with thinker
    await registerViaUI(page, testUsername, testPassword);
    await loginViaUI(page, testUsername, testPassword);

    const conversationId = await createConversationViaAPI(
      testUsername,
      testPassword,
      'Test alignment',
      ['Socrates']
    );

    // Navigate to the conversation
    await page.goto(`/?conversation=${conversationId}`);
    await page.waitForLoadState('networkidle');

    // Send a message with @mention via API
    await sendMessageViaAPI(
      testUsername,
      testPassword,
      conversationId,
      'Hello @Socrates, what do you think about this topic?'
    );

    // Wait for message to appear in UI
    await page.waitForSelector('.message-content', { state: 'visible', timeout: 10000 });

    // Find the @mention badge element
    const mentionBadge = page.locator('.message-content span[style*="inline-flex"]').first();
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
    // Register, login, and create conversation
    await registerViaUI(page, testUsername, testPassword);
    await loginViaUI(page, testUsername, testPassword);

    const conversationId = await createConversationViaAPI(
      testUsername,
      testPassword,
      'Test visual alignment',
      ['Plato']
    );

    await page.goto(`/?conversation=${conversationId}`);
    await page.waitForLoadState('networkidle');

    // Send message with mention in middle of sentence (most visible alignment issue)
    await sendMessageViaAPI(
      testUsername,
      testPassword,
      conversationId,
      'I agree with @Plato on this important philosophical question.'
    );

    await page.waitForSelector('.message-content', { state: 'visible', timeout: 10000 });

    // Get bounding boxes for text before, badge, and text after
    const messageContent = page.locator('.message-content').first();
    const textBefore = messageContent.locator('text="I agree with "');
    const mentionBadge = messageContent.locator('span[style*="inline-flex"]').first();
    const textAfter = messageContent.locator('text=" on this important"');

    // All elements should exist
    await expect(textBefore).toBeVisible({ timeout: 5000 });
    await expect(mentionBadge).toBeVisible();
    await expect(textAfter).toBeVisible();

    // Get bounding boxes to verify vertical alignment
    const beforeBox = await textBefore.boundingBox();
    const badgeBox = await mentionBadge.boundingBox();
    const afterBox = await textAfter.boundingBox();

    expect(beforeBox).not.toBeNull();
    expect(badgeBox).not.toBeNull();
    expect(afterBox).not.toBeNull();

    if (beforeBox && badgeBox && afterBox) {
      // The badge bottom should be close to the text baseline
      // Allow up to 4px variance due to font rendering differences
      const beforeBottom = beforeBox.y + beforeBox.height;
      const badgeBottom = badgeBox.y + badgeBox.height;
      const afterBottom = afterBox.y + afterBox.height;

      // Badge should not be significantly elevated above surrounding text
      // Before the fix, badge would be 6-8px higher than text
      const maxElevation = 4; // pixels

      expect(Math.abs(badgeBottom - beforeBottom)).toBeLessThanOrEqual(maxElevation);
      expect(Math.abs(badgeBottom - afterBottom)).toBeLessThanOrEqual(maxElevation);
    }
  });

  test('mention badges in mobile viewport maintain alignment', async ({ page }) => {
    // Set mobile viewport to test responsiveness
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE

    // Register, login, and create conversation
    await registerViaUI(page, testUsername, testPassword);
    await loginViaUI(page, testUsername, testPassword);

    const conversationId = await createConversationViaAPI(
      testUsername,
      testPassword,
      'Mobile alignment test',
      ['Aristotle']
    );

    await page.goto(`/?conversation=${conversationId}`);
    await page.waitForLoadState('networkidle');

    await sendMessageViaAPI(
      testUsername,
      testPassword,
      conversationId,
      'Testing @Aristotle mention on mobile'
    );

    await page.waitForSelector('.message-content', { state: 'visible', timeout: 10000 });

    // Verify vertical alignment CSS is present on mobile too
    const mentionBadge = page.locator('.message-content span[style*="inline-flex"]').first();
    await expect(mentionBadge).toBeVisible({ timeout: 5000 });

    const verticalAlign = await mentionBadge.evaluate((el) => {
      return window.getComputedStyle(el).verticalAlign;
    });

    // The fix should apply on all screen sizes
    expect(verticalAlign).toBe('text-bottom');
  });
});
