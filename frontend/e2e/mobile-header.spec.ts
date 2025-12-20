/**
 * E2E tests for mobile header behavior.
 * Tests sticky positioning, control accessibility, and various mobile viewports.
 */

import { test, expect, devices } from '@playwright/test';
import { createConversationViaUI, setupAuthenticatedUser } from './test-utils';

test.describe('Mobile Header Behavior', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('header stays visible during scroll on iPhone SE', async ({ page }) => {
    // Set viewport to iPhone SE (375x667)
    await page.setViewportSize({ width: 375, height: 667 });

    await createConversationViaUI(page, 'Mobile scroll test', 'Socrates');

    // Wait for chat area to be visible
    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    // Get header element
    const header = chatArea.locator('div').first(); // Header is first div in chat-area
    await expect(header).toBeVisible();

    // Verify header has sticky positioning
    const headerStyles = await header.evaluate((el) => {
      const styles = window.getComputedStyle(el);
      return {
        position: styles.position,
        top: styles.top,
        zIndex: styles.zIndex,
      };
    });
    expect(headerStyles.position).toBe('sticky');
    expect(headerStyles.top).toBe('0px');

    // Send multiple messages to create scrollable content
    const messageTextarea = page.getByTestId('message-textarea');
    const sendButton = page.getByTestId('send-button');

    for (let i = 1; i <= 10; i++) {
      await messageTextarea.fill(
        `Test message ${i} to create scrollable content`
      );
      await sendButton.click();
      // Wait for message to appear
      await expect(page.locator(`text=Test message ${i}`)).toBeVisible({
        timeout: 5000,
      });
    }

    // Get the messages container for scrolling
    const messagesContainer = page
      .locator('[data-testid="message-list"]')
      .or(
        chatArea
          .locator('div')
          .filter({ has: page.locator('[data-testid="message"]') })
      );

    // Scroll down in the chat area
    await messagesContainer.evaluate((el) => {
      el.scrollTo({ top: 500, behavior: 'instant' });
    });

    // Wait a moment for any layout shifts
    await page.waitForTimeout(300);

    // Header should still be visible after scrolling
    await expect(header).toBeVisible();

    // Verify header is still at the top of the viewport
    const headerBox = await header.boundingBox();
    expect(headerBox).not.toBeNull();
    if (headerBox) {
      expect(headerBox.y).toBeLessThanOrEqual(10); // Should be at or near top
    }
  });

  test('all header controls are clickable on iPhone SE', async ({ page }) => {
    // Set viewport to iPhone SE (375x667)
    await page.setViewportSize({ width: 375, height: 667 });

    await createConversationViaUI(page, 'Mobile controls test', 'Aristotle');

    // Wait for chat area
    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Test pause/resume button
    const pauseResumeButton = page.getByTestId('pause-resume-button');
    await expect(pauseResumeButton).toBeVisible();
    await expect(pauseResumeButton).toBeEnabled();

    // Click to pause
    await pauseResumeButton.click();
    await expect(pauseResumeButton).toContainText('Resume');

    // Click to resume
    await pauseResumeButton.click();
    await expect(pauseResumeButton).toContainText('Pause');

    // Test export button
    const exportButton = page.getByTestId('export-button');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();

    // Click export button to open menu
    await exportButton.click();
    await expect(page.getByTestId('export-menu')).toBeVisible();

    // Verify export options are clickable
    const htmlOption = page.getByTestId('export-html-option');
    const markdownOption = page.getByTestId('export-markdown-option');
    await expect(htmlOption).toBeVisible();
    await expect(htmlOption).toBeEnabled();
    await expect(markdownOption).toBeVisible();
    await expect(markdownOption).toBeEnabled();

    // Close menu by clicking outside
    await page.getByTestId('chat-area').click({ position: { x: 10, y: 200 } });
    await expect(page.getByTestId('export-menu')).not.toBeVisible();

    // Test speed control (if present)
    const speedControl = page.getByTestId('speed-control');
    if (await speedControl.isVisible()) {
      const speedSlider = page.getByTestId('speed-slider');
      await expect(speedSlider).toBeEnabled();

      // Try changing speed
      await speedSlider.evaluate((el: HTMLInputElement) => {
        el.value = '2.0';
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }
  });

  test('header works correctly on iPhone 12 Pro', async ({ page }) => {
    // Set viewport to iPhone 12 Pro (390x844)
    await page.setViewportSize({ width: 390, height: 844 });

    await createConversationViaUI(page, 'iPhone 12 Pro test', 'Confucius');

    // Wait for chat area
    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    // Get header element
    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Verify header doesn't overlap with content
    const headerBox = await header.boundingBox();
    expect(headerBox).not.toBeNull();

    // Check that topic and thinkers are visible
    await expect(
      page.locator('h2', { hasText: 'iPhone 12 Pro test' })
    ).toBeVisible();
    await expect(page.locator('text=with Confucius')).toBeVisible();

    // Verify controls are accessible
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(page.getByTestId('export-button')).toBeVisible();

    // Send a message to verify input is accessible below header
    const messageTextarea = page.getByTestId('message-textarea');
    await expect(messageTextarea).toBeVisible();
    await messageTextarea.fill('Testing input accessibility');

    const sendButton = page.getByTestId('send-button');
    await expect(sendButton).toBeVisible();
    await sendButton.click();

    await expect(page.locator('text=Testing input accessibility')).toBeVisible({
      timeout: 5000,
    });
  });

  test('header works correctly on iPhone 14 Pro Max', async ({ page }) => {
    // Set viewport to iPhone 14 Pro Max (430x932)
    await page.setViewportSize({ width: 430, height: 932 });

    await createConversationViaUI(page, 'iPhone 14 Pro Max test', 'Plato');

    // Wait for chat area
    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    // Get header element
    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Verify sticky positioning is maintained
    const headerStyles = await header.evaluate((el) => {
      const styles = window.getComputedStyle(el);
      return {
        position: styles.position,
        top: styles.top,
      };
    });
    expect(headerStyles.position).toBe('sticky');
    expect(headerStyles.top).toBe('0px');

    // Verify all controls are within viewport
    const pauseButton = page.getByTestId('pause-resume-button');
    const exportButton = page.getByTestId('export-button');

    const pauseBox = await pauseButton.boundingBox();
    const exportBox = await exportButton.boundingBox();

    expect(pauseBox).not.toBeNull();
    expect(exportBox).not.toBeNull();

    if (pauseBox && exportBox) {
      // All controls should be within the 430px viewport width
      expect(pauseBox.x + pauseBox.width).toBeLessThanOrEqual(430);
      expect(exportBox.x + exportBox.width).toBeLessThanOrEqual(430);
    }
  });

  test('header wraps controls appropriately on narrow viewport', async ({
    page,
  }) => {
    // Set viewport to very narrow (320x568 - iPhone SE 1st gen)
    await page.setViewportSize({ width: 320, height: 568 });

    await createConversationViaUI(page, 'Narrow viewport test', 'Nietzsche');

    // Wait for chat area
    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Verify header is visible and not overflowing
    const header = page.getByTestId('chat-area').locator('div').first();
    await expect(header).toBeVisible();

    const headerBox = await header.boundingBox();
    expect(headerBox).not.toBeNull();

    if (headerBox) {
      // Header should not extend beyond viewport width
      expect(headerBox.width).toBeLessThanOrEqual(320);
    }

    // Verify critical controls are still accessible
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(page.getByTestId('export-button')).toBeVisible();

    // Verify controls are clickable even on narrow viewport
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.click();
    await expect(pauseButton).toContainText('Resume');
  });

  test('header remains functional after orientation change', async ({
    page,
  }) => {
    // Start in portrait
    await page.setViewportSize({ width: 390, height: 844 });

    await createConversationViaUI(page, 'Orientation test', 'Einstein');

    // Verify header in portrait
    const header = page.getByTestId('chat-area').locator('div').first();
    await expect(header).toBeVisible();
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();

    // Change to landscape
    await page.setViewportSize({ width: 844, height: 390 });

    // Wait for layout to adjust
    await page.waitForTimeout(300);

    // Header should still be visible and functional
    await expect(header).toBeVisible();
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();

    // Test clicking a control after orientation change
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.click();
    await expect(pauseButton).toContainText('Resume');
  });

  test('header controls do not overlap conversation content', async ({
    page,
  }) => {
    // Test on medium-sized mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await createConversationViaUI(page, 'No overlap test', 'Descartes');

    // Send a message
    const messageTextarea = page.getByTestId('message-textarea');
    await messageTextarea.fill(
      'This message should be visible below the header'
    );
    await page.getByTestId('send-button').click();

    // Wait for message to appear
    const userMessage = page.locator(
      'text=This message should be visible below the header'
    );
    await expect(userMessage).toBeVisible({ timeout: 5000 });

    // Get positions of header and first message
    const header = page.getByTestId('chat-area').locator('div').first();
    const headerBox = await header.boundingBox();
    const messageBox = await userMessage.boundingBox();

    expect(headerBox).not.toBeNull();
    expect(messageBox).not.toBeNull();

    if (headerBox && messageBox) {
      // Message should be below the header (not overlapping)
      expect(messageBox.y).toBeGreaterThanOrEqual(
        headerBox.y + headerBox.height
      );
    }
  });

  test('all buttons meet minimum 44x44px touch target size', async ({
    page,
  }) => {
    // Test on iPhone SE (smallest common viewport)
    await page.setViewportSize({ width: 375, height: 667 });

    await createConversationViaUI(page, 'Touch target test', 'Marcus Aurelius');

    // Wait for chat area
    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Test pause/resume button meets 44x44px minimum
    const pauseButton = page.getByTestId('pause-resume-button');
    await expect(pauseButton).toBeVisible();
    const pauseBox = await pauseButton.boundingBox();
    expect(pauseBox).not.toBeNull();
    if (pauseBox) {
      expect(pauseBox.width).toBeGreaterThanOrEqual(44);
      expect(pauseBox.height).toBeGreaterThanOrEqual(44);
    }

    // Test export button meets 44x44px minimum
    const exportButton = page.getByTestId('export-button');
    await expect(exportButton).toBeVisible();
    const exportBox = await exportButton.boundingBox();
    expect(exportBox).not.toBeNull();
    if (exportBox) {
      expect(exportBox.width).toBeGreaterThanOrEqual(44);
      expect(exportBox.height).toBeGreaterThanOrEqual(44);
    }

    // Test speed slider has adequate touch area (44px height)
    const speedControl = page.getByTestId('speed-control');
    if (await speedControl.isVisible()) {
      const speedSlider = page.getByTestId('speed-slider');
      const sliderBox = await speedSlider.boundingBox();
      expect(sliderBox).not.toBeNull();
      if (sliderBox) {
        // Slider should have 44px height for easy finger interaction
        expect(sliderBox.height).toBeGreaterThanOrEqual(44);
      }
    }
  });

  test('buttons have adequate spacing for touch (8px minimum)', async ({
    page,
  }) => {
    // Test on iPhone SE (smallest common viewport)
    await page.setViewportSize({ width: 375, height: 667 });

    await createConversationViaUI(page, 'Button spacing test', 'Seneca');

    // Wait for chat area
    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Get button positions
    const pauseButton = page.getByTestId('pause-resume-button');
    const exportButton = page.getByTestId('export-button');

    await expect(pauseButton).toBeVisible();
    await expect(exportButton).toBeVisible();

    const pauseBox = await pauseButton.boundingBox();
    const exportBox = await exportButton.boundingBox();

    expect(pauseBox).not.toBeNull();
    expect(exportBox).not.toBeNull();

    if (pauseBox && exportBox) {
      // Calculate horizontal spacing between buttons
      // Assumes buttons are ordered left-to-right (export, then pause)
      const spacing = Math.abs(pauseBox.x - (exportBox.x + exportBox.width));

      // Should have at least 8px spacing (we set gap-3 which is 12px in Tailwind)
      expect(spacing).toBeGreaterThanOrEqual(8);
    }
  });

  test('pace slider is usable with finger on mobile', async ({ page }) => {
    // Test on iPhone SE
    await page.setViewportSize({ width: 375, height: 667 });

    await createConversationViaUI(page, 'Slider usability test', 'Epictetus');

    // Wait for chat area
    await expect(page.getByTestId('chat-area')).toBeVisible();

    const speedControl = page.getByTestId('speed-control');
    if (await speedControl.isVisible()) {
      const speedSlider = page.getByTestId('speed-slider');
      await expect(speedSlider).toBeVisible();

      // Verify slider is interactable
      await expect(speedSlider).toBeEnabled();

      // Get initial value
      const initialValue = await speedSlider.inputValue();

      // Simulate touch interaction by changing value
      await speedSlider.evaluate((el: HTMLInputElement) => {
        el.value = '2.0';
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });

      // Verify value changed
      const newValue = await speedSlider.inputValue();
      expect(newValue).not.toBe(initialValue);

      // Verify slider has adequate touch area
      const sliderBox = await speedSlider.boundingBox();
      expect(sliderBox).not.toBeNull();
      if (sliderBox) {
        expect(sliderBox.height).toBeGreaterThanOrEqual(44);
      }
    }
  });
});
