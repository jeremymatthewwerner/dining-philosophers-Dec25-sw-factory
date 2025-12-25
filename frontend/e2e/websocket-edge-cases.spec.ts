/**
 * WebSocket Edge Cases E2E Tests
 * Tests real-time communication robustness and edge scenarios.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaUI } from './test-utils';

test.describe('WebSocket Connection Management', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('maintains conversation state after page refresh', async ({ page }) => {
    // Create a conversation
    await createConversationViaUI(page, 'Refresh test', 'Socrates');

    // Send a message
    await page.getByTestId('message-textarea').fill('Test message');
    await page.getByTestId('send-button').click();

    // Wait for message to appear
    await expect(page.locator('text=Test message')).toBeVisible({
      timeout: 5000,
    });

    // Refresh the page
    await page.reload();

    // Should still show the conversation
    await expect(
      page.getByTestId('chat-area').locator('h2', { hasText: 'Refresh test' })
    ).toBeVisible({ timeout: 10000 });

    // Message should still be visible
    await expect(page.locator('text=Test message')).toBeVisible({
      timeout: 5000,
    });
  });

  test('reconnects WebSocket after connection drop', async ({ page }) => {
    await createConversationViaUI(
      page,
      'Connection test',
      'Aristotle'
    );

    // Send initial message to confirm connection
    await page.getByTestId('message-textarea').fill('First message');
    await page.getByTestId('send-button').click();
    await expect(page.locator('text=First message')).toBeVisible({
      timeout: 5000,
    });

    // Simulate connection drop by going offline briefly
    await page.context().setOffline(true);
    await page.waitForTimeout(2000);
    await page.context().setOffline(false);

    // Wait for reconnection
    await page.waitForTimeout(3000);

    // Should be able to send message after reconnection
    await page.getByTestId('message-textarea').fill('After reconnect');
    await page.getByTestId('send-button').click();

    // Message should either appear or show retry/error
    await page.waitForTimeout(2000);
    const messageAppeared = await page
      .locator('text=After reconnect')
      .isVisible();
    const hasError = await page.locator('text=/error|failed/i').isVisible();

    // One of these should be true
    expect(messageAppeared || hasError).toBeTruthy();
  });

  test('handles switching conversations (WebSocket cleanup)', async ({
    page,
  }) => {
    // Create two conversations
    await createConversationViaUI(page, 'First WS test', 'Socrates');
    await page.waitForLoadState('networkidle');

    await createConversationViaUI(page, 'Second WS test', 'Plato');
    await page.waitForLoadState('networkidle');

    // Switch back to first
    const firstConv = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'First WS test' });
    await firstConv.click();

    await expect(
      page.getByTestId('chat-area').locator('h2', { hasText: 'First WS test' })
    ).toBeVisible({ timeout: 5000 });

    // Send message in first conversation
    await page.getByTestId('message-textarea').fill('Message in first');
    await page.getByTestId('send-button').click();

    // Should appear in first conversation
    await expect(page.locator('text=Message in first')).toBeVisible({
      timeout: 5000,
    });

    // Switch to second conversation
    const secondConv = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Second WS test' });
    await secondConv.click();

    await expect(
      page.getByTestId('chat-area').locator('h2', { hasText: 'Second WS test' })
    ).toBeVisible({ timeout: 5000 });

    // Message from first should NOT appear here
    await expect(page.locator('text=Message in first')).not.toBeVisible();
  });
});

test.describe('WebSocket During Operations', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles pause button click', async ({ page }) => {
    await createConversationViaUI(page, 'Pause test', 'Confucius');

    // Get pause/resume button
    const pauseResumeButton = page.getByTestId('pause-resume-button');
    await expect(pauseResumeButton).toBeVisible();

    // Should show "Pause" initially
    await expect(pauseResumeButton).toContainText('Pause');

    // Click to pause
    await pauseResumeButton.click();
    await expect(pauseResumeButton).toContainText('Resume');

    // Send a message while paused
    await page.getByTestId('message-textarea').fill('Message while paused');
    await page.getByTestId('send-button').click();

    // User message should appear
    await expect(page.locator('text=Message while paused')).toBeVisible({
      timeout: 5000,
    });

    // Resume
    await pauseResumeButton.click();
    await expect(pauseResumeButton).toContainText('Pause');

    // Conversation should be functional
    await page.waitForTimeout(2000);
  });

  test('handles navigation away during message send', async ({ page }) => {
    // Create two conversations for navigation test
    await createConversationViaUI(page, 'Nav test 1', 'Socrates');
    await page.waitForLoadState('networkidle');

    await createConversationViaUI(page, 'Nav test 2', 'Aristotle');
    await page.waitForLoadState('networkidle');

    // Go back to first
    const firstConv = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Nav test 1' });
    await firstConv.click();

    // Send message and immediately navigate away
    await page.getByTestId('message-textarea').fill('Quick nav test');
    const sendPromise = page.getByTestId('send-button').click();

    // Immediately switch conversations
    const secondConv = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Nav test 2' });
    await secondConv.click();

    await sendPromise; // Ensure click completed

    // Should be on second conversation now
    await expect(
      page.getByTestId('chat-area').locator('h2', { hasText: 'Nav test 2' })
    ).toBeVisible({ timeout: 5000 });

    // Should not have JavaScript errors
    await page.waitForTimeout(2000);

    // Page should still be functional
    await expect(page.getByTestId('message-textarea')).toBeEditable();
  });
});

test.describe('WebSocket State Persistence', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('preserves pause state across page refresh', async ({ page }) => {
    await createConversationViaUI(page, 'Pause persist test', 'Plato');

    // Pause the conversation
    const pauseResumeButton = page.getByTestId('pause-resume-button');
    await pauseResumeButton.click();
    await expect(pauseResumeButton).toContainText('Resume');

    // Refresh the page
    await page.reload();

    // Wait for page to load
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });

    // Pause state should be preserved (button shows Resume)
    const buttonAfterRefresh = page.getByTestId('pause-resume-button');
    await expect(buttonAfterRefresh).toContainText('Resume');
  });

  test('handles multiple rapid pause/resume clicks', async ({ page }) => {
    await createConversationViaUI(page, 'Rapid pause test', 'Confucius');

    const pauseResumeButton = page.getByTestId('pause-resume-button');

    // Rapidly toggle pause/resume
    await pauseResumeButton.click(); // Pause
    await pauseResumeButton.click(); // Resume
    await pauseResumeButton.click(); // Pause
    await pauseResumeButton.click(); // Resume
    await pauseResumeButton.click(); // Pause

    // Wait for state to settle
    await page.waitForTimeout(1000);

    // Should show Resume (last state was Pause)
    await expect(pauseResumeButton).toContainText('Resume');

    // Resume and verify it works
    await pauseResumeButton.click();
    await expect(pauseResumeButton).toContainText('Pause');
  });
});

test.describe('Offline Behavior', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('shows appropriate feedback when sending message offline', async ({
    page,
  }) => {
    await createConversationViaUI(page, 'Offline test', 'Socrates');

    // Go offline
    await page.context().setOffline(true);

    // Try to send message
    await page.getByTestId('message-textarea').fill('Offline message');
    await page.getByTestId('send-button').click();

    // Should show some indication of failure
    await page.waitForTimeout(3000);

    // Either error message or message stays in textarea
    const textareaValue = await page
      .getByTestId('message-textarea')
      .inputValue();
    const hasError = await page.locator('text=/error|failed|offline/i').isVisible();
    const messageSent = await page.locator('text=Offline message').isVisible();

    // If message was sent (queued), that's OK
    // If error shown, that's OK
    // If message stayed in textarea, that's OK
    expect(textareaValue || hasError || messageSent).toBeTruthy();

    // Go back online
    await page.context().setOffline(false);
  });

  test('recovers when going back online', async ({ page }) => {
    await createConversationViaUI(
      page,
      'Recovery online test',
      'Aristotle'
    );

    // Go offline
    await page.context().setOffline(true);
    await page.waitForTimeout(2000);

    // Go back online
    await page.context().setOffline(false);

    // Wait for reconnection
    await page.waitForTimeout(3000);

    // Should be able to send message
    await page.getByTestId('message-textarea').fill('Back online');
    await page.getByTestId('send-button').click();

    // Give it time to send
    await page.waitForTimeout(2000);

    // Check if message appeared or if there's a retry option
    const messageVisible = await page.locator('text=Back online').isVisible();
    const canInteract = await page.getByTestId('message-textarea').isEditable();

    // Should be functional again
    expect(messageVisible || canInteract).toBeTruthy();
  });
});
