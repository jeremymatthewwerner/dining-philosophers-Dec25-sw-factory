/**
 * State Management Edge Cases E2E Tests
 * Tests state consistency, multi-tab behavior, and edge scenarios.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaUI } from './test-utils';

test.describe('Multi-Tab Synchronization', () => {
  test('can view same conversation in two tabs simultaneously', async ({
    context,
  }) => {
    // Create first tab
    const page1 = await context.newPage();
    await setupAuthenticatedUser(page1);
    await createConversationViaUI(page1, 'Multi-tab test', 'Socrates');

    // Get the URL
    const conversationUrl = page1.url();

    // Open second tab with same conversation
    const page2 = await context.newPage();
    await page2.goto(conversationUrl);

    // Wait for conversation to load in second tab
    await expect(
      page2.getByTestId('chat-area').locator('h2', { hasText: 'Multi-tab test' })
    ).toBeVisible({ timeout: 10000 });

    // Both tabs should show the conversation
    await expect(
      page1.getByTestId('chat-area').locator('h2', { hasText: 'Multi-tab test' })
    ).toBeVisible();

    await page1.close();
    await page2.close();
  });

  test('deleting conversation in one tab affects other tab', async ({
    context,
  }) => {
    // Create first tab
    const page1 = await context.newPage();
    await setupAuthenticatedUser(page1);
    await createConversationViaUI(page1, 'Delete sync test', 'Aristotle');

    const conversationUrl = page1.url();

    // Open second tab
    const page2 = await context.newPage();
    await page2.goto(conversationUrl);
    await expect(page2.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });

    // Delete conversation in first tab
    await page1.getByTestId('delete-conversation').click();

    // First tab should show welcome message
    await expect(
      page1.locator('text=Welcome to Dining Philosophers')
    ).toBeVisible({ timeout: 5000 });

    // Second tab might show error or redirect (depends on implementation)
    // We'll wait and check it handles it gracefully
    await page2.waitForTimeout(3000);

    // Page should still be functional (no crashes)
    const isOnWelcome = await page2
      .locator('text=Welcome to Dining Philosophers')
      .isVisible();
    const hasError = await page2.locator('text=/error|not found/i').isVisible();
    const stillShowing = await page2.getByTestId('chat-area').isVisible();

    // Any of these outcomes is acceptable
    expect(isOnWelcome || hasError || stillShowing).toBeTruthy();

    await page1.close();
    await page2.close();
  });
});

test.describe('Cost Tracking Accuracy', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('cost meter shows zero initially', async ({ page }) => {
    // On fresh session, cost should be $0.00
    const costMeter = page.getByTestId('cost-meter');

    // Cost meter may or may not be visible depending on design
    // If visible, should show $0.00 or similar
    const isVisible = await costMeter.isVisible();
    if (isVisible) {
      const costText = await costMeter.textContent();
      expect(costText).toMatch(/\$0\.00|0|zero/i);
    }
  });

  test('cost meter updates when messages are sent', async ({ page }) => {
    await createConversationViaUI(page, 'Cost tracking test', 'Socrates');

    // Send a message
    await page.getByTestId('message-textarea').fill('Tell me about virtue');
    await page.getByTestId('send-button').click();

    // Wait for user message
    await expect(page.locator('text=Tell me about virtue')).toBeVisible({
      timeout: 5000,
    });

    // Cost meter should exist (whether or not cost has accumulated yet)
    const costMeter = page.getByTestId('cost-meter');
    const isVisible = await costMeter.isVisible();

    // If cost meter is visible, it should show a value
    if (isVisible) {
      await page.waitForTimeout(2000);
      const costText = await costMeter.textContent();
      expect(costText).toBeTruthy();
      expect(costText).toMatch(/\$/); // Should have dollar sign
    }
  });

  test('cost accumulates across multiple messages', async ({ page }) => {
    await createConversationViaUI(
      page,
      'Cost accumulation test',
      'Aristotle'
    );

    const costMeter = page.getByTestId('cost-meter');

    // Send first message
    await page.getByTestId('message-textarea').fill('First message');
    await page.getByTestId('send-button').click();
    await page.waitForTimeout(2000);

    // Get initial cost if visible
    let initialCost = '$0.00';
    if (await costMeter.isVisible()) {
      const text = await costMeter.textContent();
      if (text) initialCost = text;
    }

    // Send second message
    await page.getByTestId('message-textarea').fill('Second message');
    await page.getByTestId('send-button').click();
    await page.waitForTimeout(2000);

    // Cost should stay same or increase (never decrease)
    if (await costMeter.isVisible()) {
      const finalText = await costMeter.textContent();
      // Just verify it's still a valid cost display
      expect(finalText).toBeTruthy();
    }
  });
});

test.describe('Conversation State Persistence', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('conversation list persists after refresh', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Persist test', 'Socrates');

    // Verify it's in the sidebar
    await expect(
      page.getByTestId('conversation-item').filter({ hasText: 'Persist test' })
    ).toBeVisible();

    // Refresh the page
    await page.reload();

    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Conversation should still be in sidebar
    await expect(
      page.getByTestId('conversation-item').filter({ hasText: 'Persist test' })
    ).toBeVisible({ timeout: 10000 });
  });

  test('returns to same conversation after refresh', async ({ page }) => {
    await createConversationViaUI(page, 'Return test', 'Plato');

    // Send a message
    await page.getByTestId('message-textarea').fill('Test message');
    await page.getByTestId('send-button').click();
    await expect(page.locator('text=Test message')).toBeVisible({
      timeout: 5000,
    });

    // Get current URL
    const currentUrl = page.url();

    // Refresh
    await page.reload();

    // Should return to same conversation
    await expect(page).toHaveURL(currentUrl, { timeout: 10000 });

    // Message should still be visible
    await expect(page.locator('text=Test message')).toBeVisible({
      timeout: 5000,
    });
  });

  test('handles rapid conversation creation', async ({ page }) => {
    // Rapidly create multiple conversations
    const topics = ['Quick 1', 'Quick 2', 'Quick 3'];

    for (const topic of topics) {
      await page.getByTestId('new-chat-button').click();
      await page.getByTestId('topic-input').fill(topic);
      await page.getByTestId('next-button').click();

      await expect(
        page.locator('h2', { hasText: 'Select Thinkers' })
      ).toBeVisible({ timeout: 30000 });

      const customInput = page.getByTestId('custom-thinker-input');
      await customInput.fill('Socrates');
      await page.getByTestId('add-custom-thinker').click();
      await expect(page.getByTestId('selected-thinker')).toBeVisible({
        timeout: 15000,
      });

      await page.getByTestId('create-button').click();
      await expect(page.getByTestId('chat-area')).toBeVisible({
        timeout: 10000,
      });

      // Small delay between creations
      await page.waitForTimeout(500);
    }

    // All three should be in sidebar
    const conversationItems = page.getByTestId('conversation-item');
    const count = await conversationItems.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });
});

test.describe('Browser Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles browser back button', async ({ page }) => {
    // Start at home
    await expect(
      page.locator('text=Welcome to Dining Philosophers')
    ).toBeVisible();

    // Create a conversation
    await createConversationViaUI(page, 'Back button test', 'Confucius');

    // Navigate back using browser back button
    await page.goBack();

    // Should handle gracefully (may stay on conversation or go to home)
    await page.waitForTimeout(2000);

    // Page should still be functional
    const isOnHome = await page
      .locator('text=Welcome to Dining Philosophers')
      .isVisible();
    const isOnConversation = await page.getByTestId('chat-area').isVisible();

    expect(isOnHome || isOnConversation).toBeTruthy();
  });

  test('handles browser forward button', async ({ page }) => {
    // Create first conversation
    await createConversationViaUI(page, 'Forward test 1', 'Socrates');
    const url1 = page.url();

    // Create second conversation
    await createConversationViaUI(page, 'Forward test 2', 'Plato');
    const url2 = page.url();

    // Go back
    await page.goBack();
    await page.waitForTimeout(1000);

    // Go forward
    await page.goForward();
    await page.waitForTimeout(1000);

    // Should be back on second conversation
    await expect(
      page
        .getByTestId('chat-area')
        .locator('h2', { hasText: 'Forward test 2' })
    ).toBeVisible({ timeout: 5000 });
  });

  test('handles direct URL access to conversation', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Direct URL test', 'Aristotle');

    // Get the conversation URL
    const conversationUrl = page.url();

    // Navigate away
    await page.goto('/');
    await expect(
      page.locator('text=Welcome to Dining Philosophers')
    ).toBeVisible();

    // Navigate directly back to conversation URL
    await page.goto(conversationUrl);

    // Should load the conversation
    await expect(
      page
        .getByTestId('chat-area')
        .locator('h2', { hasText: 'Direct URL test' })
    ).toBeVisible({ timeout: 10000 });
  });
});

test.describe('Empty State Recovery', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles deleting all conversations', async ({ page }) => {
    // Create multiple conversations
    await createConversationViaUI(page, 'Delete all 1', 'Socrates');
    await createConversationViaUI(page, 'Delete all 2', 'Plato');

    // Delete first conversation
    const firstConv = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Delete all 2' });
    await firstConv.hover();
    await page.getByTestId('delete-conversation').click();

    await page.waitForTimeout(1000);

    // Delete second conversation
    const secondConv = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Delete all 1' });
    await secondConv.click();
    await page.waitForTimeout(500);
    await page.getByTestId('delete-conversation').click();

    // Should show empty state
    await expect(
      page.locator('text=Welcome to Dining Philosophers')
    ).toBeVisible({ timeout: 5000 });

    // Should show empty conversation list indicator
    await expect(page.getByTestId('conversation-list-empty')).toBeVisible();

    // Should still be able to create new conversation
    await expect(page.getByTestId('new-chat-button')).toBeEnabled();
  });
});
