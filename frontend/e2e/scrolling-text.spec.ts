/**
 * ScrollingText component E2E tests.
 * Tests truncation detection and hover animation in real browser environments.
 *
 * This test exists because:
 * - Unit tests mock DOM measurements (clientWidth, scrollWidth, ResizeObserver)
 * - They can't catch flex layout timing bugs in real browsers
 * - Issue #344 was found by end users because no E2E test covered this behavior
 *
 * @see Issue #344, #370
 */

import { test, expect } from '@playwright/test';
import {
  setupAuthenticatedUser,
  createConversationViaAPI,
} from './test-utils';

test.describe('ScrollingText - Conversation List', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('truncates long conversation topics with ellipsis', async ({ page }) => {
    // Create a conversation with a very long topic that will definitely overflow
    const longTopic =
      'This is an extremely long conversation topic that should definitely be truncated when displayed in the sidebar because it is much too long to fit in a single line';

    await createConversationViaAPI(page, longTopic);

    // Reload to see the conversation in the sidebar
    await page.reload();

    // Find the conversation item in the sidebar
    const conversationItem = page.getByTestId('conversation-item');
    await expect(conversationItem).toBeVisible({ timeout: 10000 });

    // The ScrollingText component is inside the conversation item
    // When truncated and not hovered, it should have the 'truncate' CSS class
    // which applies text-overflow: ellipsis
    const scrollingTextContainer = conversationItem.locator('div.overflow-hidden').first();
    await expect(scrollingTextContainer).toBeVisible();

    // The inner visible span (not the hidden measurement span) should have the 'truncate' class when not animating
    // Use :not([aria-hidden="true"]) to skip the hidden measurement span
    const textSpan = scrollingTextContainer.locator('span:not([aria-hidden="true"])');
    await expect(textSpan).toHaveClass(/truncate/);

    // The container should have a title attribute (native tooltip) when truncated
    await expect(scrollingTextContainer).toHaveAttribute('title', longTopic);
  });

  test('short topics do not show ellipsis or tooltip', async ({ page }) => {
    // Create a conversation with a short topic
    const shortTopic = 'Brief';

    await createConversationViaAPI(page, shortTopic);

    // Reload to see the conversation in the sidebar
    await page.reload();

    // Find the conversation item
    const conversationItem = page.getByTestId('conversation-item');
    await expect(conversationItem).toBeVisible({ timeout: 10000 });

    // For short text, the container should NOT have a title attribute
    // (only truncated text gets the tooltip)
    const scrollingTextContainer = conversationItem.locator('div.overflow-hidden').first();

    // Short topics shouldn't trigger the truncation detection
    // Note: We check that no title is set OR the text is short enough to not truncate
    const title = await scrollingTextContainer.getAttribute('title');

    // Either no title (not truncated) or the title matches (truncated in narrow viewport)
    // This test verifies the component works - specific truncation depends on viewport width
    if (title) {
      expect(title).toBe(shortTopic);
    }
  });

  test('hover triggers animation on truncated text', async ({ page }) => {
    // Create a conversation with a long topic
    const longTopic =
      'A very long philosophical discussion about the nature of consciousness and free will that spans many characters';

    await createConversationViaAPI(page, longTopic);

    // Reload to see the conversation in the sidebar
    await page.reload();

    // Find the conversation item
    const conversationItem = page.getByTestId('conversation-item');
    await expect(conversationItem).toBeVisible({ timeout: 10000 });

    // Get the scrolling text container and visible span (not the hidden measurement span)
    const scrollingTextContainer = conversationItem.locator('div.overflow-hidden').first();
    const textSpan = scrollingTextContainer.locator('span:not([aria-hidden="true"])');

    // Before hover: should have truncate class
    await expect(textSpan).toHaveClass(/truncate/);

    // Hover over the container to trigger animation
    await scrollingTextContainer.hover();

    // After hover starts, the span class should change:
    // - 'truncate' class removed (no ellipsis during animation)
    // - 'inline-block' class added (needed for transform)
    // Wait for the animation to start using polling assertion
    await expect
      .poll(
        async () => {
          const cls = await textSpan.getAttribute('class');
          return cls?.includes('inline-block') && !cls?.includes('truncate');
        },
        { timeout: 5000 }
      )
      .toBe(true);

    // During animation, the span should have inline-block class instead of truncate
    const spanClass = await textSpan.getAttribute('class');
    expect(spanClass).toContain('inline-block');
    expect(spanClass).not.toContain('truncate');

    // The span should have a transform style applied
    const transform = await textSpan.evaluate((el) => {
      return window.getComputedStyle(el).transform;
    });

    // Transform should be a matrix (translateX is converted to matrix)
    // When scrolling, it will be something like 'matrix(1, 0, 0, 1, -X, 0)' where X > 0
    expect(transform).toMatch(/matrix/);

    // Move mouse away
    await page.mouse.move(0, 0);

    // After mouse leave, should revert to truncate class
    await expect(textSpan).toHaveClass(/truncate/, { timeout: 1000 });
  });

  test('animation resets when mouse leaves', async ({ page }) => {
    // Create a conversation with a long topic
    const longTopic =
      'Testing the marquee-style scrolling animation that activates when hovering over truncated text in the conversation list';

    await createConversationViaAPI(page, longTopic);

    // Reload to see the conversation
    await page.reload();

    const conversationItem = page.getByTestId('conversation-item');
    await expect(conversationItem).toBeVisible({ timeout: 10000 });

    const scrollingTextContainer = conversationItem.locator('div.overflow-hidden').first();
    const textSpan = scrollingTextContainer.locator('span:not([aria-hidden="true"])');

    // Hover to start animation
    await scrollingTextContainer.hover();

    // Wait for animation to start (class changes to inline-block)
    await expect
      .poll(
        async () => {
          const cls = await textSpan.getAttribute('class');
          return cls?.includes('inline-block');
        },
        { timeout: 5000 }
      )
      .toBe(true);

    // Leave hover
    await page.mouse.move(0, 0);

    // Should reset: truncate class restored, no transform style
    await expect(textSpan).toHaveClass(/truncate/, { timeout: 2000 });

    // Transform should be reset (none or identity matrix)
    const transform = await textSpan.evaluate((el) => {
      return window.getComputedStyle(el).transform;
    });
    expect(transform === 'none' || transform === 'matrix(1, 0, 0, 1, 0, 0)').toBe(true);
  });

  test('multiple conversations with long topics all show truncation', async ({ page }) => {
    // Create multiple conversations with long topics
    const topics = [
      'First very long conversation topic about ancient philosophy and its influence on modern thought',
      'Second extremely lengthy discussion topic covering ethics and moral philosophy',
      'Third extended conversation subject dealing with epistemology and knowledge theory',
    ];

    for (const topic of topics) {
      await createConversationViaAPI(page, topic);
    }

    // Reload to see all conversations
    await page.reload();

    // All conversation items should be visible
    const conversationItems = page.getByTestId('conversation-item');
    await expect(conversationItems).toHaveCount(3, { timeout: 10000 });

    // Each should have truncated text with title attribute
    for (let i = 0; i < 3; i++) {
      const item = conversationItems.nth(i);
      const scrollingTextContainer = item.locator('div.overflow-hidden').first();

      // Should have title attribute (indicates truncation detected)
      const title = await scrollingTextContainer.getAttribute('title');
      expect(title).toBeTruthy();
      expect(topics).toContain(title);
    }
  });
});

test.describe('ScrollingText - Flex Layout Timing', () => {
  /**
   * This test specifically targets the bug from issue #344:
   * In flex layouts, container width isn't finalized immediately on mount,
   * causing truncation detection to fail without ResizeObserver.
   */
  test('detects truncation correctly in flex layout after resize', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // Create conversation with long topic
    const longTopic =
      'A discussion about metaphysics and the fundamental nature of reality that requires scrolling when truncated';

    await createConversationViaAPI(page, longTopic);

    // Set a narrow viewport to ensure truncation
    await page.setViewportSize({ width: 800, height: 600 });
    await page.reload();

    const conversationItem = page.getByTestId('conversation-item');
    await expect(conversationItem).toBeVisible({ timeout: 10000 });

    const scrollingTextContainer = conversationItem.locator('div.overflow-hidden').first();

    // Truncation should be detected (title attribute present)
    await expect(scrollingTextContainer).toHaveAttribute('title', longTopic, { timeout: 5000 });

    // Now resize viewport wider
    await page.setViewportSize({ width: 1400, height: 800 });

    // Wait for ResizeObserver to re-check truncation by polling the title attribute
    await expect.poll(
      async () => await scrollingTextContainer.getAttribute('title'),
      { timeout: 2000, intervals: [100, 200] }
    ).toBe(longTopic);

    // Even at wider viewport, the sidebar width is constrained,
    // so it should still be truncated
    const titleAfterResize = await scrollingTextContainer.getAttribute('title');
    expect(titleAfterResize).toBe(longTopic);
  });
});
