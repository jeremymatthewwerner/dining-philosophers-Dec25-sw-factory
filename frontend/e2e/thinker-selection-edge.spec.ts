/**
 * Thinker Selection Edge Cases E2E tests.
 * Tests edge cases in thinker selection and validation.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser } from './test-utils';

test.describe('Thinker Selection Edge Cases', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);

    // Navigate to thinker selection
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Edge case test');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });
  });

  test('should handle very long thinker name (200 chars)', async ({ page }) => {
    // This test involves Claude API validation which can be slow
    test.slow();
    // Try adding thinker with very long name
    const longName = 'Philosopher '.repeat(15) + 'the Great'; // ~200 chars
    expect(longName.length).toBeGreaterThan(150);

    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill(longName);

    const addButton = page.getByTestId('add-custom-thinker');
    await addButton.click();

    // Wait for validation
    await page.waitForTimeout(8000);

    // Either validation rejects it, or it's accepted (possibly truncated)
    const thinkerAdded = await page
      .getByTestId('selected-thinker')
      .isVisible()
      .catch(() => false);

    const errorVisible = await page
      .locator('text=/invalid|not found|too long|error/i')
      .isVisible()
      .catch(() => false);

    // Should handle gracefully (either accepts or rejects with message)
    expect(thinkerAdded || errorVisible).toBe(true);

    if (thinkerAdded) {
      // Verify the thinker appears (name might be truncated in display)
      const thinkerCard = page.getByTestId('selected-thinker').first();
      await expect(thinkerCard).toBeVisible();
    }
  });

  test('should prevent adding duplicate thinker to same conversation', async ({
    page,
  }) => {
    // This test involves multiple Claude API validations
    test.slow();
    // Add first thinker
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Socrates');
    await page.getByTestId('add-custom-thinker').click();

    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    // Try adding the same thinker again
    await customInput.clear();
    await customInput.fill('Socrates');
    await page.getByTestId('add-custom-thinker').click();

    // Wait for response
    await page.waitForTimeout(5000);

    // Should either prevent duplicate or show error
    const thinkerCount = await page.getByTestId('selected-thinker').count();

    const errorVisible = await page
      .locator('text=/already added|duplicate|already selected/i')
      .isVisible()
      .catch(() => false);

    // Either only 1 thinker (duplicate prevented) or error shown
    expect(thinkerCount === 1 || errorVisible).toBe(true);
  });

  test('should handle removing thinker then re-adding it', async ({ page }) => {
    // This test involves multiple Claude API validations
    test.slow();
    // Add a thinker
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Plato');
    await page.getByTestId('add-custom-thinker').click();

    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    // Remove the thinker
    const removeButton = page.getByTestId('remove-thinker').first();
    await removeButton.click();

    // Verify thinker was removed
    await page.waitForTimeout(1000);
    const thinkerCount = await page.getByTestId('selected-thinker').count();
    expect(thinkerCount).toBe(0);

    // Re-add the same thinker
    await customInput.clear();
    await customInput.fill('Plato');
    await page.getByTestId('add-custom-thinker').click();

    // Should successfully add again
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    const finalCount = await page.getByTestId('selected-thinker').count();
    expect(finalCount).toBe(1);
  });

  test('should prevent creating conversation with no thinkers selected', async ({
    page,
  }) => {
    // Don't add any thinkers, just try to create
    const createButton = page.getByTestId('create-button');

    // Button should be disabled or show error
    const isDisabled = await createButton.isDisabled();

    if (!isDisabled) {
      await createButton.click();
      await page.waitForTimeout(2000);

      // Should show error
      const errorVisible = await page
        .locator('text=/select.*thinker|add.*thinker|at least one/i')
        .isVisible()
        .catch(() => false);

      // Should stay on thinker selection page
      const stillOnPage = await page
        .locator('h2', { hasText: 'Select Thinkers' })
        .isVisible()
        .catch(() => false);

      expect(errorVisible || stillOnPage).toBe(true);
    } else {
      // Expected: button is disabled
      expect(isDisabled).toBe(true);
    }
  });

  test('should handle adding thinker with only whitespace name', async ({
    page,
  }) => {
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('    '); // Only spaces

    const addButton = page.getByTestId('add-custom-thinker');

    // Button should be disabled or do nothing
    const isDisabled = await addButton.isDisabled();

    if (!isDisabled) {
      await addButton.click();
      await page.waitForTimeout(3000);

      // No thinker should be added
      const thinkerCount = await page.getByTestId('selected-thinker').count();
      expect(thinkerCount).toBe(0);
    } else {
      // Expected: button is disabled for whitespace input
      expect(isDisabled).toBe(true);
    }
  });

  test('should handle thinker name with special characters', async ({
    page,
  }) => {
    // This test involves Claude API validation which can be slow
    test.slow();
    // Try thinker name with special characters
    const specialName = 'René Descartes & "The Thinker"';
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill(specialName);

    await page.getByTestId('add-custom-thinker').click();

    // Wait for validation
    await page.waitForTimeout(8000);

    // Should either accept or reject
    const thinkerAdded = await page
      .getByTestId('selected-thinker')
      .isVisible()
      .catch(() => false);

    const errorVisible = await page
      .locator('text=/invalid|not found|error/i')
      .isVisible()
      .catch(() => false);

    // Either succeeds or shows error (both acceptable)
    expect(thinkerAdded || errorVisible).toBe(true);
  });

  test('should handle reaching maximum thinker limit (5)', async ({ page }) => {
    // This test involves 5+ Claude API validations - expect it to be very slow
    test.slow();
    // Add 5 thinkers (maximum)
    const thinkerNames = [
      'Socrates',
      'Plato',
      'Aristotle',
      'Descartes',
      'Kant',
    ];

    const customInput = page.getByTestId('custom-thinker-input');

    for (const name of thinkerNames) {
      await customInput.clear();
      await customInput.fill(name);
      await page.getByTestId('add-custom-thinker').click();

      // Wait for each thinker to be added
      await page.waitForTimeout(5000);
    }

    // Check how many were actually added
    const thinkerCount = await page.getByTestId('selected-thinker').count();

    // Should have 5 or close to 5 (depending on validation success)
    expect(thinkerCount).toBeGreaterThanOrEqual(3);

    if (thinkerCount >= 5) {
      // Try adding 6th thinker
      await customInput.clear();
      await customInput.fill('Nietzsche');
      const addButton = page.getByTestId('add-custom-thinker');

      // Button should be disabled or show error
      const isDisabled = await addButton.isDisabled();

      if (!isDisabled) {
        await addButton.click();
        await page.waitForTimeout(3000);

        // Should show max limit error
        const errorVisible = await page
          .locator('text=/maximum|limit|too many|5 thinkers/i')
          .isVisible()
          .catch(() => false);

        // Count should still be 5 or error shown
        const finalCount = await page.getByTestId('selected-thinker').count();
        expect(finalCount <= 5 || errorVisible).toBe(true);
      } else {
        // Expected: button disabled at max limit
        expect(isDisabled).toBe(true);
      }
    }
  });

  test('should handle accepting suggested thinker then removing it', async ({
    page,
  }) => {
    // This test involves waiting for thinker suggestions from Claude API
    test.slow();
    // Wait for suggestions to load
    const suggestion = page.getByTestId('thinker-suggestion').first();
    const suggestionsExist = await suggestion
      .isVisible({ timeout: 10000 })
      .catch(() => false);

    if (suggestionsExist) {
      // Accept a suggestion
      const acceptButton = page.getByTestId('accept-suggestion').first();
      await acceptButton.click();

      // Wait for thinker to be added
      await expect(page.getByTestId('selected-thinker')).toBeVisible({
        timeout: 5000,
      });

      // Remove it
      const removeButton = page.getByTestId('remove-thinker').first();
      await removeButton.click();

      // Should be removed
      await page.waitForTimeout(1000);
      const thinkerCount = await page.getByTestId('selected-thinker').count();
      expect(thinkerCount).toBe(0);
    }
  });
});
