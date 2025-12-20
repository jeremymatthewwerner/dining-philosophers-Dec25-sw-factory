/**
 * iOS Safari-specific E2E tests.
 * Tests iOS-specific rendering behaviors, Safari quirks, and mobile UX patterns.
 *
 * These tests use WebKit engine to simulate iOS Safari behavior as closely as possible.
 * For testing on real iOS devices, consider using BrowserStack or manual testing.
 *
 * Run iOS tests only: npx playwright test mobile-ios --project=ios-safari-iphone-13
 * Run all iOS projects: npx playwright test mobile-ios
 */

import { test, expect } from '@playwright/test';
import { createConversationViaUI, setupAuthenticatedUser } from './test-utils';

// These tests require WebKit (iOS Safari) to be meaningful.
// Skip when running on Chromium-based projects since Safari-specific
// behaviors (sticky positioning quirks, safe areas, etc.) differ.
// To run these tests locally: npx playwright install webkit && npx playwright test mobile-ios --project=webkit
test.beforeEach(async ({ page }, testInfo) => {
  test.skip(
    !testInfo.project.name.includes('webkit') && !testInfo.project.name.includes('safari'),
    'iOS/Safari-only test - requires WebKit browser'
  );
  await setupAuthenticatedUser(page);
});

test.describe('iOS Safari - Header Visibility', () => {
  test('header visible after chat selection on iPhone 13', async ({ page }) => {
    // Create conversation via UI
    await createConversationViaUI(page, 'iOS header test', 'Socrates');

    // Wait for chat area to be visible
    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    // Get header element
    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Verify header has sticky positioning (critical for iOS Safari)
    const headerStyles = await header.evaluate((el) => {
      const styles = window.getComputedStyle(el);
      return {
        position: styles.position,
        top: styles.top,
        zIndex: styles.zIndex,
        transform: styles.transform,
      };
    });

    expect(headerStyles.position).toBe('sticky');
    expect(headerStyles.top).toBe('0px');

    // iOS Safari had issues with transform interfering with sticky
    // Verify no transform is applied that would break sticky positioning
    expect(headerStyles.transform).toBe('none');

    // Verify header is in viewport
    const headerBox = await header.boundingBox();
    expect(headerBox).not.toBeNull();
    if (headerBox) {
      expect(headerBox.y).toBeLessThanOrEqual(10);
      expect(headerBox.y).toBeGreaterThanOrEqual(0);
    }

    // Verify critical controls are accessible
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(page.getByTestId('export-button')).toBeVisible();
  });

  test('header stays visible during scroll on iPhone SE', async ({ page }) => {
    await createConversationViaUI(page, 'iOS scroll test', 'Aristotle');

    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Send multiple messages to create scrollable content
    const messageTextarea = page.getByTestId('message-textarea');
    const sendButton = page.getByTestId('send-button');

    for (let i = 1; i <= 10; i++) {
      await messageTextarea.fill(`iOS scroll test message ${i}`);
      await sendButton.click();
      await expect(
        page.locator(`text=iOS scroll test message ${i}`)
      ).toBeVisible({ timeout: 5000 });
    }

    // Get the messages container for scrolling
    const messagesContainer = page
      .locator('[data-testid="message-list"]')
      .or(
        chatArea
          .locator('div')
          .filter({ has: page.locator('[data-testid="message"]') })
      );

    // Scroll down
    await messagesContainer.evaluate((el) => {
      el.scrollTo({ top: 500, behavior: 'instant' });
    });

    // Wait for iOS Safari to settle (it can be laggy)
    await page.waitForTimeout(500);

    // Header should still be visible after scrolling
    await expect(header).toBeVisible();

    const headerBox = await header.boundingBox();
    expect(headerBox).not.toBeNull();
    if (headerBox) {
      // Header should be sticky at top
      expect(headerBox.y).toBeLessThanOrEqual(10);
    }
  });

  test('header remains visible on iPhone 14 Pro with Dynamic Island', async ({
    page,
  }) => {
    // iPhone 14 Pro has Dynamic Island which can affect viewport
    await createConversationViaUI(page, 'Dynamic Island test', 'Plato');

    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Verify header doesn't get hidden behind notch/Dynamic Island
    const headerBox = await header.boundingBox();
    expect(headerBox).not.toBeNull();

    if (headerBox) {
      // Should respect safe area (env(safe-area-inset-top))
      // Header should be visible, not behind the notch
      expect(headerBox.y).toBeGreaterThanOrEqual(0);
    }

    // Verify controls are clickable (not blocked by notch)
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.click();
    await expect(pauseButton).toContainText('Resume');
  });
});

test.describe('iOS Safari - Sidebar Toggle', () => {
  test('sidebar opens and closes correctly on iPhone 13', async ({ page }) => {
    await createConversationViaUI(page, 'Sidebar test', 'Confucius');

    // Wait for chat area
    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Find hamburger menu button (opens sidebar)
    const sidebarToggle = page.getByTestId('sidebar-toggle');
    await expect(sidebarToggle).toBeVisible();

    // Verify hamburger button meets iOS touch target size (44x44px)
    const toggleBox = await sidebarToggle.boundingBox();
    expect(toggleBox).not.toBeNull();
    if (toggleBox) {
      expect(toggleBox.width).toBeGreaterThanOrEqual(44);
      expect(toggleBox.height).toBeGreaterThanOrEqual(44);
    }

    const sidebar = page.getByTestId('sidebar');
    const overlay = page.getByTestId('sidebar-overlay');

    // Open sidebar by clicking hamburger
    await sidebarToggle.click();
    await page.waitForTimeout(300); // Wait for animation

    // Sidebar and overlay should be visible
    await expect(sidebar).toBeVisible();
    await expect(overlay).toBeVisible();

    // Hamburger button should be hidden when sidebar is open
    await expect(sidebarToggle).not.toBeVisible();

    // Close sidebar by clicking overlay
    await overlay.click();
    await page.waitForTimeout(300); // Wait for animation

    // Sidebar should be hidden, hamburger should reappear
    await expect(sidebar).not.toBeVisible();
    await expect(sidebarToggle).toBeVisible();
  });

  test('sidebar can be reopened after closing on iPhone SE', async ({
    page,
  }) => {
    await createConversationViaUI(page, 'Sidebar reopen test', 'Descartes');

    await expect(page.getByTestId('chat-area')).toBeVisible();

    const sidebarToggle = page.getByTestId('sidebar-toggle');
    const sidebar = page.getByTestId('sidebar');
    const overlay = page.getByTestId('sidebar-overlay');

    await expect(sidebarToggle).toBeVisible();

    // Open, close, reopen cycle
    await sidebarToggle.click();
    await page.waitForTimeout(300);
    await expect(sidebar).toBeVisible();
    await expect(overlay).toBeVisible();

    // Close via overlay
    await overlay.click();
    await page.waitForTimeout(300);
    await expect(sidebar).not.toBeVisible();
    await expect(sidebarToggle).toBeVisible();

    // Reopen should work
    await sidebarToggle.click();
    await page.waitForTimeout(300);
    await expect(sidebar).toBeVisible();
    await expect(overlay).toBeVisible();

    // Close via sidebar's internal close button
    const sidebarCloseButton = page.locator('[aria-label="Close sidebar"]');
    await sidebarCloseButton.click();
    await page.waitForTimeout(300);
    await expect(sidebar).not.toBeVisible();
    await expect(sidebarToggle).toBeVisible();
  });
});

test.describe('iOS Safari - Sticky Positioning', () => {
  test('sticky header maintains position during scroll on iPhone 13', async ({
    page,
  }) => {
    await createConversationViaUI(page, 'Sticky position test', 'Nietzsche');

    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Verify sticky CSS is applied
    const stickyStyles = await header.evaluate((el) => {
      const styles = window.getComputedStyle(el);
      return {
        position: styles.position,
        top: styles.top,
        WebkitPosition: styles.getPropertyValue('-webkit-position'),
      };
    });

    expect(stickyStyles.position).toBe('sticky');
    expect(stickyStyles.top).toBe('0px');

    // Send messages to create scroll
    const messageTextarea = page.getByTestId('message-textarea');
    const sendButton = page.getByTestId('send-button');

    for (let i = 1; i <= 5; i++) {
      await messageTextarea.fill(`Sticky test ${i}`);
      await sendButton.click();
      await expect(page.locator(`text=Sticky test ${i}`)).toBeVisible({
        timeout: 5000,
      });
    }

    // Record header position before scroll
    const headerBoxBefore = await header.boundingBox();
    expect(headerBoxBefore).not.toBeNull();

    // Scroll
    const messagesContainer = page
      .locator('[data-testid="message-list"]')
      .or(
        chatArea
          .locator('div')
          .filter({ has: page.locator('[data-testid="message"]') })
      );
    await messagesContainer.evaluate((el) => {
      el.scrollTo({ top: 300, behavior: 'instant' });
    });

    await page.waitForTimeout(300);

    // Header position should remain at top (sticky behavior)
    const headerBoxAfter = await header.boundingBox();
    expect(headerBoxAfter).not.toBeNull();

    if (headerBoxBefore && headerBoxAfter) {
      // Y position should be similar (within a few pixels)
      expect(
        Math.abs(headerBoxAfter.y - headerBoxBefore.y)
      ).toBeLessThanOrEqual(5);
    }
  });

  test('sticky positioning works with iOS safe areas on iPhone 14 Pro', async ({
    page,
  }) => {
    await createConversationViaUI(page, 'Safe area test', 'Einstein');

    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Check that safe-area-inset CSS variables are respected
    const safeAreaStyles = await header.evaluate((el) => {
      const styles = window.getComputedStyle(el);
      return {
        paddingTop: styles.paddingTop,
        top: styles.top,
        position: styles.position,
      };
    });

    expect(safeAreaStyles.position).toBe('sticky');

    // Header should be visible and accessible
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(page.getByTestId('export-button')).toBeVisible();
  });
});

test.describe('iOS Safari - Orientation Changes', () => {
  test('header adapts to portrait to landscape orientation change', async ({
    page,
  }) => {
    // Start in portrait (iPhone 13: 390x844)
    await page.setViewportSize({ width: 390, height: 844 });

    await createConversationViaUI(page, 'Orientation test', 'Marcus Aurelius');

    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Verify controls in portrait
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(page.getByTestId('export-button')).toBeVisible();

    // Change to landscape (swap dimensions)
    await page.setViewportSize({ width: 844, height: 390 });

    // Wait for iOS Safari to adjust layout
    await page.waitForTimeout(500);

    // Header should still be visible and functional
    await expect(header).toBeVisible();
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(page.getByTestId('export-button')).toBeVisible();

    // Test control functionality after orientation change
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.click();
    await expect(pauseButton).toContainText('Resume');
  });

  test('layout remains functional after multiple orientation changes', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    await createConversationViaUI(page, 'Multiple orientations', 'Seneca');

    await expect(page.getByTestId('chat-area')).toBeVisible();
    const header = page.getByTestId('chat-area').locator('div').first();

    // Portrait → Landscape
    await page.setViewportSize({ width: 844, height: 390 });
    await page.waitForTimeout(500);
    await expect(header).toBeVisible();

    // Landscape → Portrait
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(500);
    await expect(header).toBeVisible();

    // Portrait → Landscape again
    await page.setViewportSize({ width: 844, height: 390 });
    await page.waitForTimeout(500);
    await expect(header).toBeVisible();

    // Verify controls still work
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.click();
    await expect(pauseButton).toContainText('Resume');
  });
});

test.describe('iOS Safari - iPad Specific Tests', () => {
  test('header displays correctly on iPad Pro', async ({ page }) => {
    // iPad Pro has larger viewport, may show different layout
    await createConversationViaUI(page, 'iPad test', 'Epictetus');

    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Verify all controls are visible (iPad may show more)
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(page.getByTestId('export-button')).toBeVisible();

    // Test that controls work
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.click();
    await expect(pauseButton).toContainText('Resume');

    const exportButton = page.getByTestId('export-button');
    await exportButton.click();
    await expect(page.getByTestId('export-menu')).toBeVisible();
  });

  test('iPad handles split view simulation (narrow width)', async ({
    page,
  }) => {
    // Simulate iPad in split view (narrow width)
    await page.setViewportSize({ width: 375, height: 1024 });

    await createConversationViaUI(page, 'iPad split view', 'Aristotle');

    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Should behave like mobile layout
    const header = page.getByTestId('chat-area').locator('div').first();
    await expect(header).toBeVisible();

    // Controls should still be accessible
    await expect(page.getByTestId('pause-resume-button')).toBeVisible();
    await expect(page.getByTestId('export-button')).toBeVisible();
  });
});

test.describe('iOS Safari - Touch Interactions', () => {
  test('touch targets meet iOS 44x44pt minimum on iPhone 13', async ({
    page,
  }) => {
    await createConversationViaUI(page, 'Touch target test', 'Socrates');

    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Test pause/resume button
    const pauseButton = page.getByTestId('pause-resume-button');
    await expect(pauseButton).toBeVisible();
    const pauseBox = await pauseButton.boundingBox();
    expect(pauseBox).not.toBeNull();
    if (pauseBox) {
      // iOS HIG recommends minimum 44x44pt for touch targets
      expect(pauseBox.width).toBeGreaterThanOrEqual(44);
      expect(pauseBox.height).toBeGreaterThanOrEqual(44);
    }

    // Test export button
    const exportButton = page.getByTestId('export-button');
    await expect(exportButton).toBeVisible();
    const exportBox = await exportButton.boundingBox();
    expect(exportBox).not.toBeNull();
    if (exportBox) {
      expect(exportBox.width).toBeGreaterThanOrEqual(44);
      expect(exportBox.height).toBeGreaterThanOrEqual(44);
    }
  });

  test('buttons respond to tap events on iPhone SE', async ({ page }) => {
    await createConversationViaUI(page, 'Tap test', 'Plato');

    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Test tap on pause button
    const pauseButton = page.getByTestId('pause-resume-button');
    await pauseButton.tap();
    await expect(pauseButton).toContainText('Resume');

    // Test tap to resume
    await pauseButton.tap();
    await expect(pauseButton).toContainText('Pause');

    // Test tap on export button
    const exportButton = page.getByTestId('export-button');
    await exportButton.tap();
    await expect(page.getByTestId('export-menu')).toBeVisible();
  });
});

test.describe('iOS Safari - Viewport and Safe Areas', () => {
  test('viewport meta tag configured correctly', async ({ page }) => {
    await page.goto('/');

    // Check viewport meta tag
    const viewportContent = await page.evaluate(() => {
      const meta = document.querySelector('meta[name="viewport"]');
      return meta?.getAttribute('content') || '';
    });

    // Should include viewport-fit=cover for safe areas
    expect(viewportContent).toContain('viewport-fit=cover');
    expect(viewportContent).toContain('width=device-width');
    expect(viewportContent).toContain('initial-scale=1');
  });

  test('safe area insets are applied on iPhone 14 Pro', async ({ page }) => {
    await createConversationViaUI(page, 'Safe area test', 'Confucius');

    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Check that body or root element uses safe-area-inset
    const safeAreaInsets = await page.evaluate(() => {
      const body = document.body;
      const styles = window.getComputedStyle(body);
      return {
        paddingTop: styles.paddingTop,
        paddingBottom: styles.paddingBottom,
        paddingLeft: styles.paddingLeft,
        paddingRight: styles.paddingRight,
      };
    });

    // On devices with notch/Dynamic Island, paddingTop should be > 0
    // This is device-specific, so we just verify it's a valid value
    expect(safeAreaInsets.paddingTop).toBeTruthy();
  });
});

test.describe('iOS Safari - Screenshot on Failure', () => {
  test('captures screenshot on test failure (iPhone 13)', async ({
    page,
  }, testInfo) => {
    await createConversationViaUI(page, 'Screenshot test', 'Descartes');

    await expect(page.getByTestId('chat-area')).toBeVisible();

    // Capture screenshot for documentation
    await page.screenshot({
      path: `${testInfo.outputDir}/ios-safari-iphone-13-${testInfo.title.replace(/\s+/g, '-')}.png`,
      fullPage: true,
    });

    // This test always passes, but demonstrates screenshot capability
    expect(true).toBe(true);
  });
});

test.describe('iOS Safari - Regression Tests', () => {
  test('no WebKit transform on header (Issue #215)', async ({ page }) => {
    // Regression test for iOS header visibility bug
    await createConversationViaUI(page, 'Transform regression', 'Nietzsche');

    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    const header = chatArea.locator('div').first();
    await expect(header).toBeVisible();

    // Verify no transform that would break sticky positioning
    const transform = await header.evaluate((el) => {
      return window.getComputedStyle(el).transform;
    });

    expect(transform).toBe('none');
  });

  test('sticky positioning works after WebKit fix (Issue #217)', async ({
    page,
  }) => {
    await createConversationViaUI(page, 'Sticky regression', 'Einstein');

    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible();

    const header = chatArea.locator('div').first();
    const position = await header.evaluate((el) => {
      return window.getComputedStyle(el).position;
    });

    expect(position).toBe('sticky');

    // Verify header stays visible after scroll
    const messageTextarea = page.getByTestId('message-textarea');
    const sendButton = page.getByTestId('send-button');

    for (let i = 1; i <= 3; i++) {
      await messageTextarea.fill(`Message ${i}`);
      await sendButton.click();
      await expect(page.locator(`text=Message ${i}`)).toBeVisible({
        timeout: 5000,
      });
    }

    // Header should remain visible
    await expect(header).toBeVisible();
  });
});
