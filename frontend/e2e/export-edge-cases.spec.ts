/**
 * Export Functionality Edge Cases E2E tests.
 * Tests exporting empty conversations, very long messages, and special characters.
 */

import { test, expect } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createAndNavigateToConversation,
} from './test-utils';

test.describe('Export Edge Cases', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('can export empty conversation without errors', async ({ page }) => {
    // Create a conversation but don't send any messages
    await createAndNavigateToConversation(page, 'Empty export test', [
      'Socrates',
    ]);

    // Open export menu
    const exportButton = page.getByTestId('export-button');
    await expect(exportButton).toBeVisible();
    await exportButton.click();

    // Export menu should appear
    const exportMenu = page.getByTestId('export-menu');
    await expect(exportMenu).toBeVisible();

    // Click HTML export option
    const htmlOption = page.getByTestId('export-html-option');
    await expect(htmlOption).toBeVisible();

    // Set up download promise before clicking
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 });

    await htmlOption.click();

    // Should trigger a download (even for empty conversation)
    const download = await downloadPromise;

    // Verify download occurred
    expect(download).toBeTruthy();
    expect(download.suggestedFilename()).toMatch(/\.html$/);

    // Close menu and verify app is still functional
    await page.keyboard.press('Escape');
    await expect(page.getByTestId('message-textarea')).toBeEnabled();
  });

  test('exports conversation with very long messages', async ({ page }) => {
    // Create a conversation
    await createAndNavigateToConversation(page, 'Long message export test', [
      'Aristotle',
    ]);

    // Send a very long message
    const longMessage = 'A'.repeat(2000) + ' This is a very long message.';
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill(longMessage);
    await page.getByTestId('send-button').click();

    // Wait for message to appear
    await expect(page.locator('text=This is a very long message.')).toBeVisible(
      { timeout: 5000 }
    );

    // Open export menu
    await page.getByTestId('export-button').click();
    await expect(page.getByTestId('export-menu')).toBeVisible();

    // Export as Markdown
    const markdownOption = page.getByTestId('export-markdown-option');
    await expect(markdownOption).toBeVisible();

    const downloadPromise = page.waitForEvent('download', { timeout: 10000 });
    await markdownOption.click();

    // Should successfully export
    const download = await downloadPromise;
    expect(download).toBeTruthy();
    expect(download.suggestedFilename()).toMatch(/\.md$/);

    // App should remain functional
    await expect(page.getByTestId('chat-area')).toBeVisible();
  });

  test('exports conversation with special characters and unicode', async ({
    page,
  }) => {
    // Create a conversation
    await createAndNavigateToConversation(page, 'Special chars export 🧠', [
      'Plato',
    ]);

    // Send message with special characters
    const specialMessage =
      'Test: <script>alert("XSS")</script> & "quotes" & 中文 & émojis 🤔💭';
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill(specialMessage);
    await page.getByTestId('send-button').click();

    // Wait for message to appear
    await expect(page.locator('text=émojis 🤔💭')).toBeVisible({
      timeout: 5000,
    });

    // Open export menu
    await page.getByTestId('export-button').click();
    await expect(page.getByTestId('export-menu')).toBeVisible();

    // Export as HTML
    const htmlOption = page.getByTestId('export-html-option');
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 });
    await htmlOption.click();

    // Should successfully export with special characters
    const download = await downloadPromise;
    expect(download).toBeTruthy();

    // Filename should handle special chars (likely sanitized)
    const filename = download.suggestedFilename();
    expect(filename).toMatch(/\.html$/);

    // App should remain functional
    await expect(page.getByTestId('message-textarea')).toBeEnabled();
  });

  test('can export in both HTML and Markdown formats', async ({ page }) => {
    // Create a conversation with some content
    await createAndNavigateToConversation(page, 'Dual format export test', [
      'Confucius',
    ]);

    // Send a message
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill('Test message for export');
    await page.getByTestId('send-button').click();

    await expect(page.locator('text=Test message for export')).toBeVisible({
      timeout: 5000,
    });

    // Export as HTML first
    await page.getByTestId('export-button').click();
    await expect(page.getByTestId('export-menu')).toBeVisible();

    const htmlDownloadPromise = page.waitForEvent('download', {
      timeout: 10000,
    });
    await page.getByTestId('export-html-option').click();

    const htmlDownload = await htmlDownloadPromise;
    expect(htmlDownload.suggestedFilename()).toMatch(/\.html$/);

    // Wait for menu to close and be ready to open again
    await expect(page.getByTestId('export-menu')).not.toBeVisible({
      timeout: 5000,
    });

    // Export as Markdown
    await page.getByTestId('export-button').click();
    await expect(page.getByTestId('export-menu')).toBeVisible();

    const mdDownloadPromise = page.waitForEvent('download', { timeout: 10000 });
    await page.getByTestId('export-markdown-option').click();

    const mdDownload = await mdDownloadPromise;
    expect(mdDownload.suggestedFilename()).toMatch(/\.md$/);

    // Both downloads should have succeeded
    expect(htmlDownload).toBeTruthy();
    expect(mdDownload).toBeTruthy();

    // Filenames should be different
    expect(htmlDownload.suggestedFilename()).not.toBe(
      mdDownload.suggestedFilename()
    );

    // App should still be functional
    await expect(page.getByTestId('chat-area')).toBeVisible();
    await expect(messageTextarea).toBeEnabled();
  });
});
