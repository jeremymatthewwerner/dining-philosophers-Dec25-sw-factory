/**
 * Chat functionality E2E tests.
 * Tests sending messages, pause/resume, and thinker responses.
 */

import { test, expect } from '@playwright/test';
import {
  createAndNavigateToConversation,
  setupAuthenticatedUser,
} from './test-utils';

test.describe('Chat Functionality', () => {
  test.describe.configure({ mode: 'parallel' });

  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('can send a message in conversation', async ({ page }) => {
    await createAndNavigateToConversation(page, 'Quick test chat', [
      'Socrates',
    ]);

    // Type and send a message
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Hello, this is a test message!');

    const sendButton = page.getByTestId('send-button');
    await sendButton.click();

    // Message should appear in the chat
    await expect(
      page.locator('text=Hello, this is a test message!')
    ).toBeVisible({ timeout: 5000 });
  });

  test('pause/resume button toggles UI state', async ({ page }) => {
    await createAndNavigateToConversation(page, 'Pause test', ['Confucius']);

    // Pause button should be visible
    const pauseResumeButton = page.getByTestId('pause-resume-button');
    await expect(pauseResumeButton).toBeVisible();
    await expect(pauseResumeButton).toContainText('Pause');

    // Click to pause
    await pauseResumeButton.click();
    await expect(pauseResumeButton).toContainText('Resume');

    // Click to resume
    await pauseResumeButton.click();
    await expect(pauseResumeButton).toContainText('Pause');
  });

  test('can delete a conversation', async ({ page }) => {
    // Create a conversation to delete
    await createAndNavigateToConversation(page, 'Topic to delete', [
      'Aristotle',
    ]);
    await expect(
      page.locator('h2', { hasText: 'Topic to delete' })
    ).toBeVisible();

    // Verify conversation is in sidebar
    const conversationItem = page.getByTestId('conversation-item');
    await expect(conversationItem).toBeVisible();

    // Click delete button
    const deleteButton = page.getByTestId('delete-conversation');
    await deleteButton.click();

    // Conversation should be removed from sidebar
    await expect(conversationItem).not.toBeVisible({ timeout: 5000 });

    // Should show empty state or welcome message
    await expect(
      page.locator('text=Welcome to dining philosophers')
    ).toBeVisible();
  });

  test('can switch between conversations', async ({ page }) => {
    // Create first conversation
    await createAndNavigateToConversation(page, 'First topic', ['Aristotle']);
    await expect(page.locator('h2', { hasText: 'First topic' })).toBeVisible();

    // Create second conversation (API creation is atomic, no stability wait needed)
    await createAndNavigateToConversation(page, 'Second topic', ['Socrates']);
    await expect(page.locator('h2', { hasText: 'Second topic' })).toBeVisible();

    // Both conversations should be in sidebar
    const conversationItems = page.getByTestId('conversation-item');
    await expect(conversationItems).toHaveCount(2);

    // Click on first conversation in sidebar
    const firstConvItem = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'First topic' });
    await firstConvItem.scrollIntoViewIfNeeded();
    await firstConvItem.click();
    await expect(
      page.getByTestId('chat-area').locator('h2', { hasText: 'First topic' })
    ).toBeVisible();

    // Click on second conversation in sidebar
    const secondConvItem = page
      .getByTestId('conversation-item')
      .filter({ hasText: 'Second topic' });
    await secondConvItem.scrollIntoViewIfNeeded();
    await secondConvItem.click();
    await expect(
      page.getByTestId('chat-area').locator('h2', { hasText: 'Second topic' })
    ).toBeVisible();

    // Sidebar should still show both conversations
    await expect(conversationItems).toHaveCount(2);
  });
});

test.describe('Thinker Responses', () => {
  // SKIP: Flaky in CI - depends on Claude API response times which can timeout
  // TODO: Mock Claude API or add better retry logic
  test.skip('pause actually stops thinker responses', async ({ page }) => {
    test.setTimeout(90000);
    await setupAuthenticatedUser(page);

    await createAndNavigateToConversation(page, 'Tell me about ethics', [
      'Aristotle',
    ]);

    // Send a message to trigger thinker response
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('What is virtue?');
    await page.getByTestId('send-button').click();

    // Wait for user message to appear
    await expect(page.locator('text=What is virtue?')).toBeVisible({
      timeout: 5000,
    });

    // Get initial message count
    const getMessageCount = async () => {
      const messages = await page.getByTestId('message').all();
      return messages.length;
    };

    // Wait for potential thinker response to start - use network idle instead of arbitrary wait
    await page
      .waitForLoadState('networkidle', { timeout: 5000 })
      .catch(() => {});
    const countBeforePause = await getMessageCount();

    // Pause the conversation
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.click();
    await expect(pauseButton).toContainText('Resume');

    // Wait and verify no new messages appear while paused - use shorter check
    await page
      .waitForLoadState('networkidle', { timeout: 3000 })
      .catch(() => {});
    const countWhilePaused = await getMessageCount();

    // Message count should not have increased significantly while paused
    expect(countWhilePaused).toBeLessThanOrEqual(countBeforePause + 1);

    // Resume the conversation
    await pauseButton.click();
    await expect(pauseButton).toContainText('Pause');

    // Wait for thinker to respond after resume - reduced from 45s to 30s
    await expect
      .poll(async () => await getMessageCount(), {
        message: 'Expected message count to increase after resume',
        timeout: 30000,
        intervals: [2000, 2000, 2000],
      })
      .toBeGreaterThan(countWhilePaused);
  });

  // SKIP: Flaky in CI - depends on Claude API response times which can timeout
  // TODO: Mock Claude API or add better retry logic
  test.skip('sends message and receives responses from multiple thinkers', async ({
    page,
  }) => {
    test.setTimeout(120000);
    await setupAuthenticatedUser(page);

    // Create conversation with multiple thinkers
    const newChatButton = page.getByTestId('new-chat-button');
    await newChatButton.click({ force: true });
    await page.getByTestId('topic-input').fill('Philosophy of knowledge');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Add first thinker (Socrates)
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.scrollIntoViewIfNeeded();
    await customInput.fill('Socrates');
    const addButton = page.getByTestId('add-custom-thinker');
    await addButton.scrollIntoViewIfNeeded();
    await addButton.click();
    await expect(page.getByTestId('selected-thinker').first()).toBeVisible({
      timeout: 15000,
    });

    // Add second thinker (Aristotle)
    await customInput.scrollIntoViewIfNeeded();
    await customInput.fill('Aristotle');
    await addButton.scrollIntoViewIfNeeded();
    await addButton.click();
    await expect(page.getByTestId('selected-thinker')).toHaveCount(2, {
      timeout: 15000,
    });

    // Create the conversation
    const createButton = page.getByTestId('create-button');
    await createButton.scrollIntoViewIfNeeded();
    await createButton.click();
    await expect(page.getByTestId('chat-area')).toBeVisible({ timeout: 10000 });

    // Send a message
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('What is the nature of knowledge?');
    const sendButton = page.getByTestId('send-button');
    await sendButton.click();

    // User message should appear immediately
    await expect(
      page.locator('text=What is the nature of knowledge?')
    ).toBeVisible({ timeout: 5000 });

    // Wait for thinker responses - reduced from 60s to 30s (still allows for API latency)
    const thinkerMessages = page.locator('[data-sender-type="thinker"]');
    await expect(thinkerMessages.first()).toBeVisible({ timeout: 30000 });

    // Get all thinker names who responded
    const thinkerNameElements = page.getByTestId('thinker-name');
    await expect(thinkerNameElements.first()).toBeVisible({ timeout: 5000 });

    // Wait for second thinker to potentially respond - poll for count to stabilize
    await expect
      .poll(async () => await thinkerNameElements.count(), {
        message: 'Expected at least one thinker to respond',
        timeout: 15000,
        intervals: [2000, 2000, 2000],
      })
      .toBeGreaterThanOrEqual(1);

    // Collect unique thinker names that responded
    const thinkerNamesCount = await thinkerNameElements.count();
    const respondedThinkers = new Set<string>();
    for (let i = 0; i < thinkerNamesCount; i++) {
      const name = await thinkerNameElements.nth(i).textContent();
      if (name) respondedThinkers.add(name);
    }

    console.log(
      `Thinkers who responded: ${Array.from(respondedThinkers).join(', ')}`
    );

    // Verify at least one thinker responded
    expect(respondedThinkers.size).toBeGreaterThanOrEqual(1);

    // Verify the thinker messages have content
    const firstThinkerMessage = thinkerMessages.first();
    const messageContent = await firstThinkerMessage.textContent();
    expect(messageContent).toBeTruthy();
    expect(messageContent!.length).toBeGreaterThan(10);
  });
});
