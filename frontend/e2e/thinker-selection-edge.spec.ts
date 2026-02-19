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

  // SKIP: This test requires Claude API validation which is too slow for CI
  // Run manually with: npx playwright test thinker-selection-edge.spec.ts -g "200 chars"
  test.skip('should handle very long thinker name (200 chars)', async ({ page }) => {
    // Try adding thinker with very long name
    const longName = 'Philosopher '.repeat(15) + 'the Great'; // ~200 chars
    expect(longName.length).toBeGreaterThan(150);

    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill(longName);

    const addButton = page.getByTestId('add-custom-thinker');
    await addButton.click();

    // Wait for either thinker added OR error - use Promise.race with longer timeout
    const thinkerSelector = page.getByTestId('selected-thinker');
    const errorSelector = page.locator('text=/invalid|not found|too long|error/i');

    await Promise.race([
      thinkerSelector.waitFor({ timeout: 60000 }).catch(() => {}),
      errorSelector.waitFor({ timeout: 60000 }).catch(() => {}),
      page.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {}),
    ]);

    // Either validation rejects it, or it's accepted (possibly truncated)
    const thinkerAdded = await thinkerSelector.isVisible().catch(() => false);
    const errorVisible = await errorSelector.isVisible().catch(() => false);

    // Should handle gracefully (either accepts or rejects with message)
    // If API is still loading, check that input is disabled (processing)
    const inputDisabled = await customInput.isDisabled().catch(() => false);
    expect(thinkerAdded || errorVisible || inputDisabled).toBe(true);

    if (thinkerAdded) {
      // Verify the thinker appears (name might be truncated in display)
      const thinkerCard = page.getByTestId('selected-thinker').first();
      await expect(thinkerCard).toBeVisible();
    }
  });

  // SKIP: This test requires Claude API validation which is too slow for CI
  // Run manually with: npx playwright test thinker-selection-edge.spec.ts -g "duplicate"
  test.skip('should prevent adding duplicate thinker to same conversation', async ({
    page,
  }) => {
    // Add first thinker
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Socrates');
    await page.getByTestId('add-custom-thinker').click();

    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 60000,
    });

    // Try adding the same thinker again
    await customInput.clear();
    await customInput.fill('Socrates');
    await page.getByTestId('add-custom-thinker').click();

    // Wait for either error OR loading to finish (network idle)
    const errorSelector = page.locator(
      'text=/already added|duplicate|already selected/i'
    );
    await Promise.race([
      errorSelector.waitFor({ timeout: 10000 }).catch(() => {}),
      page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {}),
    ]);

    // Should either prevent duplicate or show error
    const thinkerCount = await page.getByTestId('selected-thinker').count();
    const errorVisible = await errorSelector.isVisible().catch(() => false);

    // Either only 1 thinker (duplicate prevented) or error shown
    expect(thinkerCount === 1 || errorVisible).toBe(true);
  });

  // SKIP: This test requires Claude API validation which is too slow for CI
  // Run manually with: npx playwright test thinker-selection-edge.spec.ts -g "removing.*re-adding"
  test.skip('should handle removing thinker then re-adding it', async ({ page }) => {
    // Add a thinker
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Plato');
    await page.getByTestId('add-custom-thinker').click();

    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 60000,
    });

    // Remove the thinker - wait for button to be clickable
    const removeButton = page.getByTestId('remove-thinker').first();
    await expect(removeButton).toBeVisible({ timeout: 5000 });
    await removeButton.click();

    // Wait for thinker to be removed (wait for element to detach)
    await expect(page.getByTestId('selected-thinker')).not.toBeVisible({
      timeout: 10000,
    });
    const thinkerCount = await page.getByTestId('selected-thinker').count();
    expect(thinkerCount).toBe(0);

    // Re-add the same thinker
    await customInput.clear();
    await customInput.fill('Plato');
    await page.getByTestId('add-custom-thinker').click();

    // Should successfully add again
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 60000,
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

      // Wait for error OR page heading to remain (both are element-driven)
      const errorSelector = page.locator(
        'text=/select.*thinker|add.*thinker|at least one/i'
      );
      const headingSelector = page.locator('h2', { hasText: 'Select Thinkers' });
      await Promise.race([
        errorSelector.waitFor({ timeout: 5000 }).catch(() => {}),
        headingSelector.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {}),
      ]);

      // Should show error
      const errorVisible = await errorSelector.isVisible().catch(() => false);

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
      // Wait for any client-side validation to complete (element-count assertion
      // with a short timeout is faster than a broad networkidle wait)
      await expect(page.getByTestId('selected-thinker')).toHaveCount(0, {
        timeout: 5000,
      });
    } else {
      // Expected: button is disabled for whitespace input
      expect(isDisabled).toBe(true);
    }
  });

  // SKIP: This test requires Claude API validation which is too slow for CI
  // Run manually with: npx playwright test thinker-selection-edge.spec.ts -g "special characters"
  test.skip('should handle thinker name with special characters', async ({
    page,
  }) => {
    // Try thinker name with special characters
    const specialName = 'René Descartes & "The Thinker"';
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill(specialName);

    await page.getByTestId('add-custom-thinker').click();

    // Wait for either thinker added OR error - use Promise.race with longer timeout
    const thinkerSelector = page.getByTestId('selected-thinker');
    const errorSelector = page.locator('text=/invalid|not found|error/i');

    await Promise.race([
      thinkerSelector.waitFor({ timeout: 60000 }).catch(() => {}),
      errorSelector.waitFor({ timeout: 60000 }).catch(() => {}),
      page.waitForLoadState('networkidle', { timeout: 60000 }).catch(() => {}),
    ]);

    // Should either accept or reject
    const thinkerAdded = await thinkerSelector.isVisible().catch(() => false);
    const errorVisible = await errorSelector.isVisible().catch(() => false);

    // If API is still loading, check that input is disabled (processing)
    const inputDisabled = await customInput.isDisabled().catch(() => false);
    expect(thinkerAdded || errorVisible || inputDisabled).toBe(true);
  });

  // SKIP: This test requires 5+ Claude API validations which is too slow for CI
  // Run manually with: npx playwright test thinker-selection-edge.spec.ts -g "maximum thinker limit"
  test.skip('should handle reaching maximum thinker limit (5)', async ({ page }) => {
    // Add 5 thinkers (maximum)
    const thinkerNames = [
      'Socrates',
      'Plato',
      'Aristotle',
      'Descartes',
      'Kant',
    ];

    const customInput = page.getByTestId('custom-thinker-input');

    for (let i = 0; i < thinkerNames.length; i++) {
      const name = thinkerNames[i];
      await customInput.clear();
      await customInput.fill(name);
      await page.getByTestId('add-custom-thinker').click();

      // Wait for thinker count to increase (event-driven)
      const expectedCount = i + 1;
      await expect
        .poll(
          async () => page.getByTestId('selected-thinker').count(),
          { timeout: 20000 }
        )
        .toBeGreaterThanOrEqual(expectedCount);
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

        // Wait for error or network idle
        const errorSelector = page.locator(
          'text=/maximum|limit|too many|5 thinkers/i'
        );
        await Promise.race([
          errorSelector.waitFor({ timeout: 5000 }).catch(() => {}),
          page
            .waitForLoadState('networkidle', { timeout: 5000 })
            .catch(() => {}),
        ]);

        // Should show max limit error
        const errorVisible = await errorSelector.isVisible().catch(() => false);

        // Count should still be 5 or error shown
        const finalCount = await page.getByTestId('selected-thinker').count();
        expect(finalCount <= 5 || errorVisible).toBe(true);
      } else {
        // Expected: button disabled at max limit
        expect(isDisabled).toBe(true);
      }
    }
  });

  // SKIP: This test requires Claude API for suggestions which is too slow for CI
  // Run manually with: npx playwright test thinker-selection-edge.spec.ts -g "suggested thinker"
  test.skip('should handle accepting suggested thinker then removing it', async ({
    page,
  }) => {
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

      // Wait for removal (element should disappear)
      await expect(page.getByTestId('selected-thinker')).not.toBeVisible({
        timeout: 5000,
      });
      const thinkerCount = await page.getByTestId('selected-thinker').count();
      expect(thinkerCount).toBe(0);
    }
  });
});
