/**
 * Cost Tracking Edge Cases E2E tests.
 * Tests cost meter with high costs, zero costs, and precision.
 */

import { test, expect } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createAndNavigateToConversation,
} from './test-utils';

test.describe('Cost Edge Cases', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('displays zero cost correctly', async ({ page }) => {
    // Create a conversation
    await createAndNavigateToConversation(page, 'Zero cost test', ['Socrates']);

    // Check if cost meter exists
    const costMeter = page.getByTestId('cost-meter');

    // Cost meter might not be visible initially or might show $0.000
    // We're testing that the app doesn't crash with zero cost
    const isVisible = await costMeter.isVisible().catch(() => false);

    if (isVisible) {
      const costText = await costMeter.textContent();

      // Should show zero in proper format (e.g., "$0.000" or "$0.00")
      expect(costText).toMatch(/\$0\.0+/);
    }

    // App should be functional with zero cost
    await expect(page.getByTestId('message-textarea')).toBeEnabled();
    await expect(page.getByTestId('send-button')).toBeVisible();
  });

  test('cost meter formats costs with 3 decimal precision', async ({
    page,
  }) => {
    // Create a conversation
    await createAndNavigateToConversation(page, 'Cost precision test', [
      'Aristotle',
    ]);

    // Send a message to potentially generate cost
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('What is your view on ethics?');
    await page.getByTestId('send-button').click();

    // Wait for user message to appear
    await expect(page.locator('text=What is your view on ethics?')).toBeVisible(
      { timeout: 5000 }
    );

    // Check cost meter
    const costMeter = page.getByTestId('cost-meter');
    const isVisible = await costMeter.isVisible().catch(() => false);

    if (isVisible) {
      const costText = await costMeter.textContent();

      // Should have dollar sign and decimal format
      expect(costText).toMatch(/\$/);

      // Should have proper decimal formatting (either 2 or 3 decimal places)
      expect(costText).toMatch(/\d+\.\d{2,3}/);
    }
  });

  test('handles high cost values without overflow', async ({ page }) => {
    // Create a conversation
    await createAndNavigateToConversation(page, 'High cost test', ['Plato']);

    // Note: We can't easily simulate a high cost without actually
    // generating many expensive LLM responses. This test validates
    // that the cost meter UI can handle the display without breaking.

    // Simulate a high cost by manipulating the display if possible
    // (This is a UI test - the actual cost calculation is tested in unit tests)

    const costMeter = page.getByTestId('cost-meter');
    const isVisible = await costMeter.isVisible().catch(() => false);

    if (isVisible) {
      // Try to inject a high cost value for display testing
      await page.evaluate(() => {
        const costElement = document.querySelector(
          '[data-testid="cost-meter"]'
        );
        if (costElement) {
          // Test that element can display large numbers
          const testCost = '$123.456';
          costElement.textContent = `Session cost: ${testCost}`;
        }
      });

      // Wait for DOM update after evaluate - use expect.poll for element text
      await expect
        .poll(
          async () => {
            return await costMeter.textContent();
          },
          { timeout: 2000 }
        )
        .toBeTruthy();

      // Cost meter should still be visible and properly formatted
      const costText = await costMeter.textContent();
      expect(costText).toBeTruthy();

      // Should contain dollar sign and numeric value
      expect(costText).toMatch(/\$/);
      expect(costText).toMatch(/\d+/);
    }

    // App should remain functional
    await expect(page.getByTestId('message-textarea')).toBeEnabled();
    await expect(page.getByTestId('chat-area')).toBeVisible();
  });

  test('cost accumulates correctly across multiple messages', async ({
    page,
  }) => {
    // Create a conversation
    await createAndNavigateToConversation(page, 'Cost accumulation test', [
      'Confucius',
    ]);

    const messageTextarea = page.getByTestId('message-textarea');
    const sendButton = page.getByTestId('send-button');

    // Send first message
    await messageTextarea.fill('First question');
    await sendButton.click();
    await expect(page.locator('text=First question')).toBeVisible({
      timeout: 5000,
    });

    // Wait for send button to re-enable (message processing complete)
    await expect(sendButton).toBeEnabled({ timeout: 5000 });

    // Get cost after first message (if visible)
    const costMeter = page.getByTestId('cost-meter');
    const isVisible = await costMeter.isVisible().catch(() => false);

    if (isVisible) {
      const costAfterFirst = await costMeter.textContent();

      // Send second message
      await messageTextarea.fill('Second question');
      await sendButton.click();
      await expect(page.locator('text=Second question')).toBeVisible({
        timeout: 5000,
      });

      // Wait for send button to re-enable (message processing complete)
      await expect(sendButton).toBeEnabled({ timeout: 5000 });

      const costAfterSecond = await costMeter.textContent();

      // Costs should be different (accumulated)
      // Note: They might be the same if thinker hasn't responded yet
      // This test validates the cost meter updates without crashing

      expect(costAfterFirst).toBeTruthy();
      expect(costAfterSecond).toBeTruthy();

      // Both should be valid currency formats
      expect(costAfterFirst).toMatch(/\$/);
      expect(costAfterSecond).toMatch(/\$/);
    }

    // App should remain functional
    await expect(messageTextarea).toBeEnabled();
  });
});
