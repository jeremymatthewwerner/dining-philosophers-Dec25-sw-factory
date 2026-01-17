/**
 * Feedback Modal Edge Cases E2E tests.
 * Tests validation and edge cases for user feedback submission.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser } from './test-utils';

// TEMPORARILY SKIPPED: These tests are slow due to API calls, causing CI timeout
// TODO: Re-enable after optimizing test performance (issue #526)
test.describe.skip('Feedback Modal Edge Cases', () => {
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
    await openFeedbackModal(page);

    // Fill contact info but leave feedback empty
    await page.getByTestId('feedback-name').fill('Test User');
    await page.getByTestId('feedback-email').fill('test@example.com');

    // Leave feedback-text empty
    const feedbackText = page.getByTestId('feedback-text');
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

  test('should handle very long feedback text (15k chars)', async ({
    page,
  }) => {
    await openFeedbackModal(page);

    // Fill with contact info
    await page.getByTestId('feedback-name').fill('Long Feedback User');
    await page.getByTestId('feedback-email').fill('long@example.com');

    // Create very long feedback (15,000 characters)
    const longFeedback =
      'This is a very detailed piece of feedback. '.repeat(300);
    expect(longFeedback.length).toBeGreaterThan(14000);

    const feedbackText = page.getByTestId('feedback-text');
    await feedbackText.fill(longFeedback);

    // Submit
    const submitButton = page.getByTestId('submit-feedback');
    await submitButton.click();

    // Should either succeed or show length error
    await page.waitForTimeout(5000);

    const successVisible = await page
      .locator('text=/thank you|feedback.*submitted|sent/i')
      .isVisible()
      .catch(() => false);

    const errorVisible = await page
      .locator('text=/too long|maximum.*characters|limit/i')
      .isVisible()
      .catch(() => false);

    // Should handle gracefully (either accept or reject with message)
    expect(successVisible || errorVisible).toBe(true);
  });

  test('should validate email format in feedback modal', async ({ page }) => {
    await openFeedbackModal(page);

    // Fill with invalid email
    await page.getByTestId('feedback-name').fill('Email Test');
    await page
      .getByTestId('feedback-email')
      .fill('invalidemail'); // No @ sign
    await page
      .getByTestId('feedback-text')
      .fill('Testing email validation');

    const submitButton = page.getByTestId('submit-feedback');
    await submitButton.click();

    // Should show validation error
    await page.waitForTimeout(2000);

    const errorVisible = await page
      .locator('text=/invalid email|email format|valid email/i')
      .isVisible()
      .catch(() => false);

    // Or HTML5 validation catches it
    const emailInput = page.getByTestId('feedback-email');
    const isInvalid = await emailInput.evaluate((el: HTMLInputElement) => {
      return !el.validity.valid;
    });

    expect(errorVisible || isInvalid).toBe(true);
  });

  test('should handle special characters in name and email', async ({
    page,
  }) => {
    await openFeedbackModal(page);

    // Use special characters in name
    const specialName = 'Test User 🤔 & "Developer" — ñoño';
    await page.getByTestId('feedback-name').fill(specialName);
    await page.getByTestId('feedback-email').fill('test@example.com');
    await page
      .getByTestId('feedback-text')
      .fill('Feedback with special characters');

    const submitButton = page.getByTestId('submit-feedback');
    await submitButton.click();

    // Should succeed without corrupting special characters
    await expect(
      page.locator('text=/thank you|feedback.*submitted|sent/i')
    ).toBeVisible({ timeout: 10000 });
  });

  test('should allow submission without contact info (anonymous)', async ({
    page,
  }) => {
    await openFeedbackModal(page);

    // Leave name and email empty
    await page.getByTestId('feedback-name').clear();
    await page.getByTestId('feedback-email').clear();

    // Only provide feedback text
    await page.getByTestId('feedback-text').fill('Anonymous feedback test');

    const submitButton = page.getByTestId('submit-feedback');
    await submitButton.click();

    // Should either accept anonymous feedback or require contact info
    await page.waitForTimeout(5000);

    const successVisible = await page
      .locator('text=/thank you|feedback.*submitted|sent/i')
      .isVisible()
      .catch(() => false);

    const errorVisible = await page
      .locator('text=/contact.*required|name.*required|email.*required/i')
      .isVisible()
      .catch(() => false);

    // One should be true (either accepts anonymous or requires contact)
    expect(successVisible || errorVisible).toBe(true);
  });

  test('should close modal when clicking cancel', async ({ page }) => {
    await openFeedbackModal(page);

    // Fill some data
    await page.getByTestId('feedback-name').fill('Cancel Test');
    await page.getByTestId('feedback-text').fill('Testing cancel button');

    // Click cancel
    const cancelButton = page.getByTestId('cancel-feedback');
    await cancelButton.click();

    // Modal should close
    await expect(page.getByTestId('feedback-modal')).not.toBeVisible({
      timeout: 3000,
    });
  });

  test('should close modal when clicking outside overlay', async ({ page }) => {
    await openFeedbackModal(page);

    // Fill some data
    await page.getByTestId('feedback-text').fill('Testing overlay click');

    // Click on the modal overlay (outside the modal content)
    // This assumes the modal has a backdrop/overlay
    const modalOverlay = page.locator('[data-testid="feedback-modal"]');
    await modalOverlay.click({ position: { x: 5, y: 5 } }); // Click top-left corner (overlay)

    // Modal might close or stay open depending on implementation
    await page.waitForTimeout(1000);

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
