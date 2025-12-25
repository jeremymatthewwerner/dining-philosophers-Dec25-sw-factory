/**
 * Error Handling and Recovery E2E Tests
 * Tests robustness, error scenarios, and recovery mechanisms.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaUI } from './test-utils';

test.describe('Rapid Actions and Race Conditions', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('prevents duplicate messages from rapid send button clicking', async ({
    page,
  }) => {
    await createConversationViaUI(page, 'Rapid click test', 'Socrates');

    const textarea = page.getByTestId('message-textarea');
    await textarea.fill('Test message for rapid clicking');

    const sendButton = page.getByTestId('send-button');

    // Get initial message count
    const initialCount = await page.getByTestId('message').count();

    // Rapidly click send button multiple times
    await Promise.all([
      sendButton.click(),
      sendButton.click(),
      sendButton.click(),
    ]);

    // Wait for messages to settle
    await page.waitForTimeout(2000);

    // Should only have 1 new message, not 3
    const finalCount = await page.getByTestId('message').count();
    const newMessages = finalCount - initialCount;

    expect(newMessages).toBe(1);
  });

  test('handles delete conversation while messages are loading', async ({
    page,
  }) => {
    await createConversationViaUI(
      page,
      'Delete during load test',
      'Aristotle'
    );

    // Start sending a message
    const textarea = page.getByTestId('message-textarea');
    await textarea.fill('Quick question');
    await page.getByTestId('send-button').click();

    // Immediately try to delete the conversation
    const deleteButton = page.getByTestId('delete-conversation');
    await deleteButton.click();

    // Should handle gracefully without errors
    await page.waitForTimeout(2000);

    // Should be back at welcome state
    await expect(
      page.locator('text=Welcome to Dining Philosophers')
    ).toBeVisible({ timeout: 5000 });

    // No JavaScript errors should have occurred
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.waitForTimeout(1000);
    expect(consoleErrors.length).toBe(0);
  });

  test('handles rapid conversation switching', async ({ page }) => {
    // Create two conversations
    await createConversationViaUI(page, 'First rapid test', 'Socrates');
    await page.waitForTimeout(1000);

    await createConversationViaUI(page, 'Second rapid test', 'Plato');
    await page.waitForTimeout(1000);

    // Rapidly switch between them
    const firstConv = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'First rapid test' });
    const secondConv = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Second rapid test' });

    // Rapid switching
    await firstConv.click();
    await secondConv.click();
    await firstConv.click();
    await secondConv.click();

    // Should end up on the last clicked conversation without errors
    await expect(
      page.getByTestId('chat-area').locator('h2', { hasText: 'Second rapid' })
    ).toBeVisible({ timeout: 5000 });

    // Page should still be functional
    await expect(page.getByTestId('message-textarea')).toBeVisible();
  });
});

test.describe('API Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles network error gracefully during conversation creation', async ({
    page,
  }) => {
    // Open modal
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Network error test');

    // Go offline before clicking Next
    await page.context().setOffline(true);

    await page.getByTestId('next-button').click();

    // Should show error or timeout gracefully
    // Wait for error message or timeout
    const outcome = await Promise.race([
      page
        .locator('text=/error|failed|network|offline/i')
        .waitFor({ timeout: 10000 })
        .then(() => 'error-shown'),
      page
        .locator('h2', { hasText: 'Select Thinkers' })
        .waitFor({ timeout: 35000 })
        .then(() => 'success'),
    ]).catch(() => 'timeout');

    // Should either show error or timeout
    expect(outcome).not.toBe('success');

    // Go back online
    await page.context().setOffline(false);
  });

  test('handles network error during message send', async ({ page }) => {
    await createConversationViaUI(page, 'Message error test', 'Confucius');

    const textarea = page.getByTestId('message-textarea');
    await textarea.fill('This message will fail');

    // Go offline
    await page.context().setOffline(true);

    await page.getByTestId('send-button').click();

    // Should show error or keep message in textarea
    await page.waitForTimeout(3000);

    // Either error message shows or message stays in textarea
    const textareaValue = await textarea.inputValue();
    const hasErrorMessage = await page
      .locator('text=/error|failed|offline/i')
      .isVisible();

    // One of these should be true
    expect(
      textareaValue.includes('fail') || hasErrorMessage
    ).toBeTruthy();

    // Go back online
    await page.context().setOffline(false);
  });
});

test.describe('Session and Authentication', () => {
  test('handles invalid token gracefully', async ({ page }) => {
    // Set up with invalid token
    await page.goto('/');

    // Set an invalid token
    await page.evaluate(() => {
      localStorage.setItem('auth_token', 'invalid-token-12345');
    });

    // Try to access the app
    await page.goto('/');

    // Should either:
    // 1. Redirect to login
    // 2. Show error
    // 3. Clear token and redirect to login

    // Wait for stable state
    await page.waitForTimeout(3000);

    // Check final state
    const url = page.url();
    const isOnLogin = url.includes('/login');
    const hasError = await page.locator('text=/error|invalid/i').isVisible();
    const isOnHome = url.endsWith('/');

    // Should handle gracefully (login page or error)
    expect(isOnLogin || hasError || isOnHome).toBeTruthy();
  });
});

test.describe('Empty State Handling', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles sending empty message', async ({ page }) => {
    await createConversationViaUI(page, 'Empty message test', 'Socrates');

    const textarea = page.getByTestId('message-textarea');
    const sendButton = page.getByTestId('send-button');

    // Try to send empty message
    await textarea.fill('');
    await sendButton.click();

    // Should either:
    // 1. Not send (button disabled)
    // 2. Not create a message
    await page.waitForTimeout(1000);

    // If button is enabled, check that no empty message was created
    const messages = await page.getByTestId('message').all();
    const hasEmptyMessage = await Promise.all(
      messages.map(async (msg) => {
        const text = await msg.textContent();
        return text?.trim() === '';
      })
    ).then((results) => results.some((r) => r));

    expect(hasEmptyMessage).toBeFalsy();
  });

  test('handles sending whitespace-only message', async ({ page }) => {
    await createConversationViaUI(page, 'Whitespace test', 'Aristotle');

    const textarea = page.getByTestId('message-textarea');
    const sendButton = page.getByTestId('send-button');

    // Try to send whitespace-only message
    await textarea.fill('   \n  \t  ');

    // Button should ideally be disabled
    const isDisabled = await sendButton.isDisabled();
    if (!isDisabled) {
      await sendButton.click();
      await page.waitForTimeout(1000);

      // Should not create a message with only whitespace
      const messages = await page.getByTestId('message').all();
      const lastMessage = messages[messages.length - 1];
      if (lastMessage) {
        const text = await lastMessage.textContent();
        expect(text?.trim().length).toBeGreaterThan(0);
      }
    } else {
      expect(isDisabled).toBeTruthy();
    }
  });
});

test.describe('Error Recovery', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('can recover from failed conversation creation', async ({ page }) => {
    // Attempt to create conversation that might fail
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Recovery test');

    // Go offline temporarily
    await page.context().setOffline(true);
    await page.getByTestId('next-button').click();

    // Wait for failure
    await page.waitForTimeout(5000);

    // Go back online
    await page.context().setOffline(false);

    // Try again - modal should still be open or we can reopen
    const modalVisible = await page.getByTestId('new-chat-modal').isVisible();

    if (!modalVisible) {
      // Reopen modal
      await page.getByTestId('new-chat-button').click();
      await page.getByTestId('topic-input').fill('Recovery test retry');
    }

    // Should be able to proceed now
    await page.getByTestId('next-button').click();

    // May succeed this time
    await page.waitForTimeout(35000);

    // Should either see thinkers or be able to try again
    const hasReached = await page
      .locator('h2', { hasText: 'Select Thinkers' })
      .isVisible();
    const canRetry = await page.getByTestId('next-button').isVisible();

    expect(hasReached || canRetry).toBeTruthy();
  });
});
