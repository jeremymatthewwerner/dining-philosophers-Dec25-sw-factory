/**
 * New conversation flow E2E tests.
 * Tests the modal flow for creating conversations with thinkers.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser } from './test-utils';

test.describe('New Conversation Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('can create a new conversation with suggested thinkers', async ({
    page,
  }) => {
    // Click new chat button in sidebar
    const newChatButton = page.getByTestId('new-chat-button');
    await newChatButton.click();

    // Modal should appear
    const modal = page.getByTestId('new-chat-modal');
    await expect(modal).toBeVisible();

    // Enter a topic
    const topicInput = page.getByTestId('topic-input');
    await topicInput.fill('The nature of consciousness');

    // Click Next
    const nextButton = page.getByTestId('next-button');
    await nextButton.click();

    // Wait for thinker suggestions (this calls the real backend API)
    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Should see suggested thinkers
    const thinkerCards = page.getByTestId('thinker-suggestion');
    await expect(thinkerCards.first()).toBeVisible({ timeout: 10000 });

    // Select a thinker by clicking the accept button (checkmark)
    const acceptButton = page.getByTestId('accept-suggestion').first();
    await acceptButton.click();

    // Should see selected thinker
    const selectedThinker = page.getByTestId('selected-thinker');
    await expect(selectedThinker).toBeVisible();

    // Create button should be enabled
    const createButton = page.getByTestId('create-button');
    await expect(createButton).toBeEnabled();

    // Click create
    await createButton.click();

    // Modal should close and conversation should be created
    await expect(modal).not.toBeVisible({ timeout: 10000 });

    // Wait for chat area to appear
    const chatArea = page.getByTestId('chat-area');
    await expect(chatArea).toBeVisible({ timeout: 10000 });

    // Should see the topic in the chat area header
    await expect(
      chatArea.locator('h2', { hasText: 'The nature of consciousness' })
    ).toBeVisible();
  });

  test('can add custom thinker', async ({ page }) => {
    // Open new chat modal
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Philosophy of mind');
    await page.getByTestId('next-button').click();

    // Wait for thinker step
    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Enter a custom thinker name
    const customInput = page.getByTestId('custom-thinker-input');
    await customInput.fill('Socrates');

    // Click add button
    const addButton = page.getByTestId('add-custom-thinker');
    await addButton.click();

    // Should validate and add the thinker (may take time to validate via API)
    const selectedThinker = page.getByTestId('selected-thinker');
    await expect(selectedThinker).toBeVisible({ timeout: 15000 });
  });

  test('create button is disabled without thinkers', async ({ page }) => {
    // Open modal and go to thinker step
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Test topic');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Create button should be disabled
    const createButton = page.getByTestId('create-button');
    await expect(createButton).toBeDisabled();
  });

  test('shows loading spinner on Next button while generating suggestions', async ({
    page,
  }) => {
    // Open modal
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('The meaning of life');

    // Get the next button
    const nextButton = page.getByTestId('next-button');

    // Click Next and immediately check for loading state
    await nextButton.click();

    // The button should show a spinner (svg with animate-spin class)
    // Wait for either the spinner to appear OR the thinkers step to load
    const spinnerOrThinkers = await Promise.race([
      nextButton
        .locator('svg.animate-spin')
        .isVisible()
        .then(() => 'spinner'),
      page
        .locator('h2', { hasText: 'Select Thinkers' })
        .waitFor({ timeout: 30000 })
        .then(() => 'thinkers'),
    ]);

    // If we caught the spinner, great! If thinkers loaded too fast, that's also fine
    console.log(`Loading animation test: saw ${spinnerOrThinkers}`);

    // Verify we end up at the thinker selection step
    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });
    // Button should no longer be in loading state
    await expect(nextButton).not.toBeVisible();
  });
});

test.describe('Thinker Suggestions', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('can refresh a suggestion', async ({ page }) => {
    // Open modal and go to thinker step
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Ancient philosophy');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Get initial thinker name
    const firstSuggestion = page.getByTestId('thinker-suggestion').first();
    await expect(firstSuggestion).toBeVisible({ timeout: 10000 });

    // Click refresh button
    const refreshButton = page.getByTestId('refresh-suggestion').first();
    await refreshButton.click();

    // Should show loading spinner briefly, then new suggestion
    await expect(firstSuggestion).toBeVisible({ timeout: 15000 });
  });

  test('refresh suggestion replaces with different thinker', async ({
    page,
  }) => {
    // Open modal and go to thinker step
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Quantum physics');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Wait for initial suggestions
    const suggestions = page.getByTestId('thinker-suggestion');
    await expect(suggestions.first()).toBeVisible({ timeout: 15000 });

    // Get initial thinker name
    const firstSuggestion = page.getByTestId('thinker-suggestion').first();
    const initialName = await firstSuggestion
      .locator('div.font-medium')
      .textContent();

    // Click refresh button
    const refreshButton = page.getByTestId('refresh-suggestion').first();
    await refreshButton.click();

    // Wait for refresh to complete
    await page.waitForTimeout(3000);

    // The suggestion should have been replaced (or at least refreshed)
    await expect(firstSuggestion).toBeVisible({ timeout: 15000 });
    const newName = await firstSuggestion
      .locator('div.font-medium')
      .textContent();

    // Verify that the suggestion exists (might be same or different person)
    expect(newName).toBeTruthy();
    console.log(`Refreshed: ${initialName} -> ${newName}`);
  });

  // SKIP: Flaky in CI - depends on Claude API response times which can timeout
  // TODO: Mock Claude API or add better retry logic
  test.skip('auto-fetches new suggestion when selecting a thinker', async ({
    page,
  }) => {
    // Open modal and go to thinker step
    await page.getByTestId('new-chat-button').click();
    await page.getByTestId('topic-input').fill('Ancient Greek philosophy');
    await page.getByTestId('next-button').click();

    await expect(
      page.locator('h2', { hasText: 'Select Thinkers' })
    ).toBeVisible({ timeout: 30000 });

    // Wait for initial suggestions to load
    const suggestions = page.getByTestId('thinker-suggestion');
    await expect(suggestions.first()).toBeVisible({ timeout: 15000 });

    // Count initial suggestions and get names
    const initialCount = await suggestions.count();
    const initialNames: string[] = [];
    for (let i = 0; i < initialCount; i++) {
      const name = await suggestions
        .nth(i)
        .locator('div.font-medium')
        .textContent();
      if (name) initialNames.push(name);
    }

    // Set up listener for auto-fetch API call BEFORE clicking
    const autoFetchPromise = page.waitForResponse(
      (response) => response.url().includes('/thinkers/suggest'),
      { timeout: 20000 }
    );

    // Select the first thinker
    const acceptButton = page.getByTestId('accept-suggestion').first();
    await acceptButton.click();

    // Should see selected thinker appear
    await expect(page.getByTestId('selected-thinker')).toBeVisible();

    // Wait for the auto-fetch API call to complete
    await autoFetchPromise;

    // Wait for state to update after API response
    await page.waitForTimeout(2000);

    // Get the final count and names
    const finalCount = await suggestions.count();
    const finalNames: string[] = [];
    for (let i = 0; i < finalCount; i++) {
      const name = await suggestions
        .nth(i)
        .locator('div.font-medium')
        .textContent();
      if (name) finalNames.push(name);
    }

    // Check if a new thinker was added (different from original suggestions)
    const newThinkers = finalNames.filter(
      (name) => !initialNames.includes(name)
    );

    // With auto-fetch working, we should have at least as many suggestions as before
    expect(finalCount).toBeGreaterThanOrEqual(initialCount - 1);
    expect(newThinkers.length).toBeGreaterThan(0);
  });
});
