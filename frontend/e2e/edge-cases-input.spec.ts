/**
 * Input Edge Cases E2E Tests
 * Tests special characters, extreme inputs, and injection attempts.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, createConversationViaUI } from './test-utils';

test.describe('Special Characters in Topic', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles unicode and emojis in topic', async ({ page }) => {
    const topicWithEmojis = 'Philosophy 🤔 and Wisdom 📚';

    // Open new chat modal
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill(topicWithEmojis);
    await page.getByTestId('next-button').click();

    // Should proceed to thinker selection
    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Add a thinker and create conversation
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Socrates');
    await page.getByTestId('add-custom-thinker').click();
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    await page.getByTestId('create-button').click();

    // Topic should be displayed correctly with emojis
    await expect(
      page.locator('h2', { hasText: topicWithEmojis })
    ).toBeVisible({ timeout: 10000 });
  });

  test('handles special characters in topic (quotes, brackets)', async ({
    page,
  }) => {
    const topicWithSpecialChars = 'What is "truth" & <reality>?';

    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill(topicWithSpecialChars);
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Should handle the special characters without breaking
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Aristotle');
    await page.getByTestId('add-custom-thinker').click();
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    await page.getByTestId('create-button').click();

    // Topic should be properly escaped and displayed
    await expect(page.locator('h2').filter({ hasText: 'truth' })).toBeVisible({
      timeout: 10000,
    });
  });

  test('handles potential SQL injection in topic', async ({ page }) => {
    const sqlInjectionAttempt = "Ethics'; DROP TABLE conversations; --";

    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill(sqlInjectionAttempt);
    await page.getByTestId('next-button').click();

    // Should safely handle the input without database issues
    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Plato');
    await page.getByTestId('add-custom-thinker').click();
    await expect(page.getByTestId('selected-thinker')).toBeVisible({
      timeout: 15000,
    });

    await page.getByTestId('create-button').click();

    // Conversation should be created successfully
    await expect(page.getByTestId('chat-area')).toBeVisible({
      timeout: 10000,
    });
  });
});

test.describe('Special Characters in Messages', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('handles emojis in messages', async ({ page }) => {
    await createConversationViaUI(page, 'Emoji test', 'Confucius');

    const messageWithEmojis = 'Hello! 👋 What do you think? 🤔';
    const textarea = page.getByTestId('message-textarea');
    await textarea.fill(messageWithEmojis);
    await page.getByTestId('send-button').click();

    // Message should appear with emojis intact
    await expect(page.locator(`text=${messageWithEmojis}`)).toBeVisible({
      timeout: 5000,
    });
  });

  test('handles markdown-like syntax in messages', async ({ page }) => {
    await createConversationViaUI(page, 'Markdown test', 'Socrates');

    const messageWithMarkdown = '**bold** _italic_ `code` [link](url)';
    const textarea = page.getByTestId('message-textarea');
    await textarea.fill(messageWithMarkdown);
    await page.getByTestId('send-button').click();

    // Message should appear (markdown may or may not be rendered)
    // We're just testing it doesn't break
    await expect(page.locator('text=/bold.*italic.*code/i')).toBeVisible({
      timeout: 5000,
    });
  });

  test('handles potential XSS in messages', async ({ page }) => {
    await createConversationViaUI(page, 'XSS test', 'Aristotle');

    const xssAttempt = '<script>alert("xss")</script>';
    const textarea = page.getByTestId('message-textarea');
    await textarea.fill(xssAttempt);
    await page.getByTestId('send-button').click();

    // Message should be escaped/sanitized
    // We'll check that the script tag doesn't execute
    // by verifying the page still functions normally
    await expect(page.getByTestId('message-textarea')).toBeVisible();

    // Message should appear as text, not execute
    await page.waitForTimeout(2000);

    // Page should still be functional (no alert popup broke it)
    const messageTextarea = page.getByTestId('message-textarea');
    await expect(messageTextarea).toBeEditable();
  });

  test('handles very long message (10,000+ characters)', async ({ page }) => {
    await createConversationViaUI(page, 'Long message test', 'Plato');

    const longMessage = 'A'.repeat(10000);
    const textarea = page.getByTestId('message-textarea');
    await textarea.fill(longMessage);

    // Should either accept or show error
    const sendButton = page.getByTestId('send-button');
    await sendButton.click();

    // Wait to see if message appears or error shows
    await page.waitForTimeout(3000);

    // Either the message was sent or an error was shown
    // Both are acceptable behaviors for extreme input
    const hasMessage = await page
      .locator('[data-testid="message"]')
      .count()
      .then((count) => count > 0);
    const hasError = await page.locator('text=/too long|maximum/i').isVisible();

    expect(hasMessage || hasError).toBeTruthy();
  });
});

test.describe('Invalid Custom Thinker Names', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('rejects nonsensical thinker name', async ({ page }) => {
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Test topic');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Try to add nonsensical name
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('asdfjkl12345');
    await page.getByTestId('add-custom-thinker').click();

    // Should show error or validation failure
    // Wait for either error message or timeout
    const outcome = await Promise.race([
      page
        .locator('text=/not found|invalid|unknown/i')
        .waitFor({ timeout: 20000 })
        .then(() => 'error-shown'),
      page
        .getByTestId('selected-thinker')
        .waitFor({ timeout: 20000 })
        .then(() => 'accepted'),
    ]).catch(() => 'timeout');

    // Most likely outcome is error or timeout (no thinker added)
    expect(outcome).not.toBe('accepted');
  });

  test('rejects fictional character', async ({ page }) => {
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Fantasy topic');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Try to add fictional character
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Harry Potter');
    await page.getByTestId('add-custom-thinker').click();

    // Should reject fictional characters
    const outcome = await Promise.race([
      page
        .locator('text=/not found|invalid|fictional/i')
        .waitFor({ timeout: 20000 })
        .then(() => 'error-shown'),
      page
        .getByTestId('selected-thinker')
        .waitFor({ timeout: 20000 })
        .then(() => 'accepted'),
    ]).catch(() => 'timeout');

    // Should not accept fictional character
    expect(outcome).not.toBe('accepted');
  });

  test('handles empty custom thinker name', async ({ page }) => {
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Test topic');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Try to add empty name
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('');

    const addButton = page.getByTestId('add-custom-thinker');

    // Button should be disabled or click should do nothing
    const isDisabled = await addButton.isDisabled();
    if (!isDisabled) {
      await addButton.click();
      // Should not add a thinker
      await page.waitForTimeout(1000);
      const thinkerCount = await page.getByTestId('selected-thinker').count();
      expect(thinkerCount).toBe(0);
    } else {
      expect(isDisabled).toBeTruthy();
    }
  });

  test('handles thinker name with only whitespace', async ({ page }) => {
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Test topic');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Try to add whitespace-only name
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('   ');

    const addButton = page.getByTestId('add-custom-thinker');

    // Should either be disabled or reject the input
    const isDisabled = await addButton.isDisabled();
    if (!isDisabled) {
      await addButton.click();
      await page.waitForTimeout(2000);
      // Should not successfully add a thinker
      const outcome = await Promise.race([
        page
          .locator('text=/invalid|required/i')
          .waitFor({ timeout: 3000 })
          .then(() => 'error'),
        page
          .getByTestId('selected-thinker')
          .waitFor({ timeout: 3000 })
          .then(() => 'added'),
      ]).catch(() => 'nothing');

      expect(outcome).not.toBe('added');
    }
  });
});
