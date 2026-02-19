/**
 * Shared test utilities for E2E tests.
 */

import type { Page } from '@playwright/test';

const API_BASE = 'http://localhost:8000';

export interface ConversationSetup {
  id: string;
  topic: string;
}

interface AuthResponse {
  access_token: string;
  user: {
    id: string;
    username: string;
  };
}

/**
 * Registers a new user and stores the auth token in localStorage.
 * Uses a unique username per test to avoid conflicts.
 */
export async function registerUser(
  page: Page,
  username?: string
): Promise<AuthResponse> {
  // Generate unique username if not provided
  const uniqueUsername =
    username ||
    `testuser_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const displayName = `Test User ${Date.now()}`;
  const password = 'testpass123';

  const response = await page.request.post(`${API_BASE}/api/auth/register`, {
    data: { username: uniqueUsername, display_name: displayName, password },
  });

  if (!response.ok()) {
    const error = await response.json();
    throw new Error(`Failed to register: ${error.detail || response.status()}`);
  }

  const data: AuthResponse = await response.json();

  // Store auth data in localStorage
  await page.evaluate(
    ([token, user]) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('user', JSON.stringify(user));
    },
    [data.access_token, data.user] as [string, { id: string; username: string }]
  );

  return data;
}

/**
 * Logs in an existing user and stores the auth token in localStorage.
 */
export async function loginUser(
  page: Page,
  username: string,
  password: string
): Promise<AuthResponse> {
  const response = await page.request.post(`${API_BASE}/api/auth/login`, {
    data: { username, password },
  });

  if (!response.ok()) {
    const error = await response.json();
    throw new Error(`Failed to login: ${error.detail || response.status()}`);
  }

  const data: AuthResponse = await response.json();

  // Store auth data in localStorage
  await page.evaluate(
    ([token, user]) => {
      localStorage.setItem('access_token', token);
      localStorage.setItem('user', JSON.stringify(user));
    },
    [data.access_token, data.user] as [string, { id: string; username: string }]
  );

  return data;
}

/**
 * Sets up an authenticated user and navigates to the home page.
 * This should be called at the start of tests that require authentication.
 */
export async function setupAuthenticatedUser(
  page: Page
): Promise<AuthResponse> {
  // First navigate to the page to have a context for localStorage
  await page.goto('/');

  // Register a new user
  const auth = await registerUser(page);

  // Reload to pick up the new auth state
  await page.reload();
  // Wait for the main UI to be ready (element-driven wait is faster than networkidle)
  // new-chat-button is visible once auth succeeds and the app has loaded
  await page.getByTestId('new-chat-button').waitFor({ state: 'visible', timeout: 15000 });

  return auth;
}

/**
 * Gets the stored access token from localStorage.
 */
export async function getStoredToken(page: Page): Promise<string | null> {
  return page.evaluate(() => localStorage.getItem('access_token'));
}

/**
 * Creates a conversation directly via API for faster test setup.
 * Use this when you don't need to test the modal flow itself.
 *
 * IMPORTANT: After calling this, use navigateToConversation() to actually
 * open the conversation in the chat view. The app doesn't have URL-based
 * routing for conversations - you need to click the conversation in the sidebar.
 */
export async function createConversationViaAPI(
  page: Page,
  topic: string,
  thinkerNames: string[] = ['Aristotle']
): Promise<ConversationSetup> {
  const token = await getStoredToken(page);
  if (!token) {
    throw new Error('No auth token found. Call setupAuthenticatedUser first.');
  }

  // Create conversation via API with auth
  const createResponse = await page.request.post(
    `${API_BASE}/api/conversations`,
    {
      data: {
        topic,
        thinkers: thinkerNames.map((name) => ({
          name,
          bio: `A notable thinker.`,
          positions: 'Various positions',
          style: 'Analytical',
        })),
      },
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!createResponse.ok()) {
    const error = await createResponse.json();
    throw new Error(
      `Failed to create conversation: ${error.detail || createResponse.status()}`
    );
  }

  const conversation = await createResponse.json();
  return { id: conversation.id, topic };
}

/**
 * Navigates to a conversation by clicking on it in the sidebar.
 * This is the correct way to open a conversation - the app doesn't have
 * URL-based routing for individual conversations.
 *
 * Use after createConversationViaAPI() to enter the chat view.
 */
export async function navigateToConversation(
  page: Page,
  topic: string
): Promise<void> {
  // Reload the page to pick up the newly created conversation in the sidebar
  // (The API call doesn't update the React state automatically)
  await page.goto('/');
  // No networkidle wait here - the element-specific waitFor below handles readiness

  // Find and click the conversation in the sidebar
  // The topic may be truncated in the sidebar, so use partial matching
  const conversationItem = page
    .getByTestId('conversation-item')
    .filter({ hasText: topic });

  await conversationItem.waitFor({ state: 'visible', timeout: 10000 });
  await conversationItem.click();

  // Wait for chat area to be visible (indicates conversation is loaded)
  await page.getByTestId('chat-area').waitFor({ state: 'visible', timeout: 10000 });
}

/**
 * Creates a conversation via API and then navigates to it.
 * This is the recommended approach for tests that need to be in a conversation
 * but don't need to test the modal creation flow.
 */
export async function createAndNavigateToConversation(
  page: Page,
  topic: string,
  thinkerNames: string[] = ['Aristotle']
): Promise<ConversationSetup> {
  const conv = await createConversationViaAPI(page, topic, thinkerNames);
  await navigateToConversation(page, topic);
  return conv;
}

/**
 * Helper to create a conversation using the UI flow.
 * Use this when you need to test a specific UI interaction.
 */
export async function createConversationViaUI(
  page: Page,
  topic: string,
  thinker: string
): Promise<void> {
  const newChatButton = page.getByTestId('new-chat-button');
  await newChatButton.click({ force: true });
  await page.getByTestId('topic-input').fill(topic);
  await page.getByTestId('next-button').click();

  // Wait for thinker step
  await page
    .locator('h2', { hasText: 'Select Thinkers' })
    .waitFor({ timeout: 30000 });

  // Add custom thinker
  const customInput = page.getByTestId('custom-thinker-input');
  await customInput.scrollIntoViewIfNeeded();
  await customInput.fill(thinker);
  const addButton = page.getByTestId('add-custom-thinker');
  await addButton.scrollIntoViewIfNeeded();
  await addButton.click();
  await page.getByTestId('selected-thinker').waitFor({ timeout: 15000 });

  // Create conversation
  const createButton = page.getByTestId('create-button');
  await createButton.scrollIntoViewIfNeeded();
  await createButton.click();
  await page.getByTestId('chat-area').waitFor({ timeout: 10000 });
}

/**
 * Clear localStorage and reload for fresh state.
 * After clearing auth, the app redirects to /login.
 */
export async function resetPageState(page: Page): Promise<void> {
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  // Wait for the login redirect (URL-based wait is more targeted than networkidle)
  await page.waitForURL(/\/login/, { timeout: 10000 });
}
