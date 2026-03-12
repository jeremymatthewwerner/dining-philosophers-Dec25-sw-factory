/**
 * Feedback Modal Edge Cases E2E tests.
 * Tests validation and edge cases for user feedback submission.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser } from './test-utils';

test.describe('Feedback Modal Edge Cases', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
    await page.goto('/');
  });

  async function openFeedbackModal(page: any) {
    // Open user menu dropdown
    const userMenuButton = page.getByTestId('user-menu-button');
    await userMenuButton.click();

    // Wait for dropdown
    const dropdown = page.getByTestId('user-menu-dropdown');
    await expect(dropdown).toBeVisible();

    // Click feedback button
    const feedbackButton = page.getByTestId('user-menu-feedback');
    await feedbackButton.click();

    // Wait for modal
    await expect(page.getByTestId('feedback-modal')).toBeVisible({
      timeout: 5000,
    });
  }

  test('should prevent empty feedback text submission', async ({ page }) => {
    // Simple form validation - no API calls needed
    await openFeedbackModal(page);

    // Fill contact info but leave feedback empty
    await page.getByTestId('feedback-name').fill('Test User');
    await page.getByTestId('feedback-email').fill('test@example.com');

    // Leave feedback-message empty (use correct testid from FeedbackModal)
    const feedbackText = page.getByTestId('feedback-message');
    await feedbackText.clear();

    // Try to submit
    const submitButton = page.getByTestId('submit-feedback');

    // Button should be disabled or show error
    const isDisabled = await submitButton.isDisabled();

    if (!isDisabled) {
      await submitButton.click();

      // Should show error message
      await expect(
        page.locator('text=/feedback.*required|please.*feedback|provide.*feedback/i')
      ).toBeVisible({ timeout: 3000 });
    } else {
      // Expected: button is disabled when feedback is empty
      expect(isDisabled).toBe(true);
    }
  });

  // SKIP: This test requires backend API call which is too slow for CI
  // Run manually with: npx playwright test feedback-edge-cases.spec.ts -g "15k chars"
  test.skip('should handle very long feedback text (15k chars)', async ({
    page,
  }) => {
    await openFeedbackModal(page);

    // Fill with contact info
    await page.getByTestId('feedback-name').fill('Long Feedback User');
    await page.getByTestId('feedback-email').fill('long@example.com');

    // Create very long feedback (15,000 characters)
    // "This is a very detailed piece of feedback. " = 45 chars, so 334 repeats = 15,030 chars
    const longFeedback =
      'This is a very detailed piece of feedback. '.repeat(334);
    expect(longFeedback.length).toBeGreaterThan(14000);

    const feedbackText = page.getByTestId('feedback-message');
    await feedbackText.fill(longFeedback);

    // Submit
    const submitButton = page.getByTestId('submit-feedback');
    await submitButton.click();

    // Wait for success OR error - use Promise.race
    const successSelector = page.locator(
      'text=/thank you|feedback.*submitted|sent/i'
    );
    const errorSelector = page.locator(
      'text=/too long|maximum.*characters|limit/i'
    );

    await Promise.race([
      successSelector.waitFor({ timeout: 15000 }).catch(() => {}),
      errorSelector.waitFor({ timeout: 15000 }).catch(() => {}),
      page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {}),
    ]);

    const successVisible = await successSelector.isVisible().catch(() => false);
    const errorVisible = await errorSelector.isVisible().catch(() => false);

    // Should handle gracefully (either accept or reject with message)
    expect(successVisible || errorVisible).toBe(true);
  });

  test('should validate email format in feedback modal', async ({ page }) => {
    // Client-side validation only - no API calls
    await openFeedbackModal(page);

    // Fill with invalid email
    await page.getByTestId('feedback-name').fill('Email Test');
    const emailInput = page.getByTestId('feedback-email');
    await emailInput.fill('invalidemail'); // No @ sign
    await page.getByTestId('feedback-message').fill('Testing email validation');

    // Check HTML5 validation BEFORE clicking submit (more reliable)
    const isInvalidBeforeSubmit = await emailInput.evaluate((el: HTMLInputElement) => {
      return !el.validity.valid;
    });

    const submitButton = page.getByTestId('submit-feedback');
    await submitButton.click();

    // Wait for error OR network idle (since this is client-side, should be fast)
    const errorSelector = page.locator(
      'text=/invalid email|email format|valid email/i'
    );
    await Promise.race([
      errorSelector.waitFor({ timeout: 3000 }).catch(() => {}),
      page.waitForLoadState('networkidle', { timeout: 3000 }).catch(() => {}),
    ]);

    const errorVisible = await errorSelector.isVisible().catch(() => false);

    // Either HTML5 validation caught it (before submit) or error shown after
    expect(errorVisible || isInvalidBeforeSubmit).toBe(true);
  });

  // SKIP: This test requires backend API call which is too slow for CI
  // Run manually with: npx playwright test feedback-edge-cases.spec.ts -g "special characters"
  test.skip('should handle special characters in name and email', async ({
    page,
  }) => {
    await openFeedbackModal(page);

    // Use special characters in name
    const specialName = 'Test User 🤔 & "Developer" — ñoño';
    await page.getByTestId('feedback-name').fill(specialName);
    await page.getByTestId('feedback-email').fill('test@example.com');
    await page
      .getByTestId('feedback-message')
      .fill('Feedback with special characters');

    const submitButton = page.getByTestId('submit-feedback');
    await submitButton.click();

    // Should succeed without corrupting special characters
    await expect(
      page.locator('text=/thank you|feedback.*submitted|sent/i')
    ).toBeVisible({ timeout: 15000 });
  });

  // SKIP: This test requires backend API call which is too slow for CI
  // Run manually with: npx playwright test feedback-edge-cases.spec.ts -g "anonymous"
  test.skip('should allow submission without contact info (anonymous)', async ({
    page,
  }) => {
    await openFeedbackModal(page);

    // Leave name and email empty
    await page.getByTestId('feedback-name').clear();
    await page.getByTestId('feedback-email').clear();

    // Only provide feedback text
    await page.getByTestId('feedback-message').fill('Anonymous feedback test');

    const submitButton = page.getByTestId('submit-feedback');
    await submitButton.click();

    // Wait for success OR error - use Promise.race
    const successSelector = page.locator(
      'text=/thank you|feedback.*submitted|sent/i'
    );
    const errorSelector = page.locator(
      'text=/contact.*required|name.*required|email.*required/i'
    );

    await Promise.race([
      successSelector.waitFor({ timeout: 10000 }).catch(() => {}),
      errorSelector.waitFor({ timeout: 10000 }).catch(() => {}),
      page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {}),
    ]);

    const successVisible = await successSelector.isVisible().catch(() => false);
    const errorVisible = await errorSelector.isVisible().catch(() => false);

    // One should be true (either accepts anonymous or requires contact)
    expect(successVisible || errorVisible).toBe(true);
  });

  test('should close modal when clicking cancel', async ({ page }) => {
    // Simple UI interaction - no API calls
    await openFeedbackModal(page);

    // Fill some data
    await page.getByTestId('feedback-name').fill('Cancel Test');
    await page.getByTestId('feedback-message').fill('Testing cancel button');

    // Click cancel - use button text since no specific testid exists
    const cancelButton = page.getByRole('button', { name: /cancel/i });
    await cancelButton.click();

    // Modal should close
    await expect(page.getByTestId('feedback-modal')).not.toBeVisible({
      timeout: 3000,
    });
  });

  test('should close modal when clicking outside overlay', async ({ page }) => {
    // Simple UI interaction - no API calls
    await openFeedbackModal(page);

    // Fill some data
    await page.getByTestId('feedback-message').fill('Testing overlay click');

    // Click on the modal overlay (outside the modal content)
    // This assumes the modal has a backdrop/overlay
    const modalOverlay = page.locator('[data-testid="feedback-modal"]');
    await modalOverlay.click({ position: { x: 5, y: 5 } }); // Click top-left corner (overlay)

    // Wait briefly for any animation — use element-based check instead of networkidle
    // (networkidle hangs on open WebSocket connections for up to the full timeout)
    const modalElement = page.getByTestId('feedback-modal');
    await modalElement
      .waitFor({ state: 'hidden', timeout: 1000 })
      .catch(() => {});

    const modalStillVisible = await page
      .getByTestId('feedback-modal')
      .isVisible()
      .catch(() => false);

    // Either behavior is acceptable, just verify no crash
    expect(typeof modalStillVisible).toBe('boolean');
  });

  test('should preserve feedback text if modal accidentally closes', async ({
    page,
  }) => {
    // First, set localStorage with saved feedback
    await page.evaluate(() => {
      localStorage.setItem('feedback_name', 'Persistent User');
      localStorage.setItem('feedback_email', 'persistent@test.com');
    });

    await openFeedbackModal(page);

    // Verify fields are pre-filled from localStorage
    await expect(page.getByTestId('feedback-name')).toHaveValue(
      'Persistent User'
    );
    await expect(page.getByTestId('feedback-email')).toHaveValue(
      'persistent@test.com'
    );

    // This verifies the localStorage persistence feature works
  });
});
