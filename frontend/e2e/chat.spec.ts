/**
 * Chat functionality E2E tests.
 * Tests sending messages, pause/resume, and thinker responses.
 */

import { test, expect } from '@playwright/test';
import { createConversationViaUI, setupAuthenticatedUser } from './test-utils';

test.describe('Chat Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('can send a message in conversation', async ({ page }) => {
    await createConversationViaUI(page, 'Quick test chat', 'Socrates');

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
    await createConversationViaUI(page, 'Pause test', 'Confucius');

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
    await createConversationViaUI(page, 'Topic to delete', 'Aristotle');
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
      page.locator('text=Welcome to Dining Philosophers')
    ).toBeVisible();
  });

  test('can switch between conversations', async ({ page }) => {
    // Create first conversation
    await createConversationViaUI(page, 'First topic', 'Aristotle');
    await expect(page.locator('h2', { hasText: 'First topic' })).toBeVisible();

    // Wait for page to stabilize before creating second conversation
    await page.waitForLoadState('networkidle');

    // Create second conversation
    await createConversationViaUI(page, 'Second topic', 'Socrates');
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

    await createConversationViaUI(page, 'Tell me about ethics', 'Aristotle');

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

    // Wait a moment for thinker to potentially start responding
    await page.waitForTimeout(2000);
    const countBeforePause = await getMessageCount();

    // Pause the conversation
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.click();
    await expect(pauseButton).toContainText('Resume');

    // Wait and verify no new messages appear while paused
    await page.waitForTimeout(5000);
    const countWhilePaused = await getMessageCount();

    // Message count should not have increased significantly while paused
    expect(countWhilePaused).toBeLessThanOrEqual(countBeforePause + 1);

    // Resume the conversation
    await pauseButton.click();
    await expect(pauseButton).toContainText('Pause');

    // Wait for thinker to respond after resume
    let countAfterResume = countWhilePaused;
    const maxWaitTime = 45000;
    const pollInterval = 2000;
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitTime) {
      await page.waitForTimeout(pollInterval);
      countAfterResume = await getMessageCount();
      if (countAfterResume > countWhilePaused) {
        break;
      }
    }

    // Should have more messages after resuming
    expect(countAfterResume).toBeGreaterThan(countWhilePaused);
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

    // Wait for thinker responses
    const thinkerMessages = page.locator('[data-sender-type="thinker"]');
    await expect(thinkerMessages.first()).toBeVisible({ timeout: 60000 });

    // Get all thinker names who responded
    const thinkerNameElements = page.getByTestId('thinker-name');
    await expect(thinkerNameElements.first()).toBeVisible({ timeout: 5000 });

    // Wait a bit more for second thinker to potentially respond
    await page.waitForTimeout(15000);

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
