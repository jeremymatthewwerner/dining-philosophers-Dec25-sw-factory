/**
 * Homepage E2E tests.
 * Tests the main page functionality after authentication.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, resetPageState } from './test-utils';

test.describe('Homepage', () => {
  test.beforeEach(async ({ page }) => {
    // Set up authenticated user before each test
    await setupAuthenticatedUser(page);
  });

  test('loads and shows welcome message', async ({ page }) => {
    // Should show the welcome message when no conversation selected
    const welcomeText = page.locator('text=Welcome to Dining Philosophers');
    await expect(welcomeText).toBeVisible();

    // Should show the new chat button in sidebar
    const newChatButton = page.getByTestId('new-chat-button');
    await expect(newChatButton).toBeVisible();
  });

  test('sidebar shows empty state initially', async ({ page }) => {
    // Should show empty conversation list
    const emptyState = page.getByTestId('conversation-list-empty');
    await expect(emptyState).toBeVisible();
  });

  test('shows display name in sidebar', async ({ page }) => {
    // Should show the display name in the sidebar footer
    const sidebar = page.getByTestId('sidebar');
    await expect(sidebar).toBeVisible();

    // The display name should be displayed (starts with "Test User")
    const displayNameElement = sidebar.locator('text=/Test User/');
    await expect(displayNameElement).toBeVisible();
  });

  test('logout redirects to login page', async ({ page }) => {
    // Click the logout button
    const logoutButton = page.getByTestId('logout-button');
    await logoutButton.click();

    // Should redirect to login page
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe('Login Page', () => {
  test('shows login form when not authenticated', async ({ page }) => {
    // Clear any existing auth
    await page.goto('/');
    await resetPageState(page);

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/);

    // Should show login form
    await expect(
      page.locator('h1', { hasText: 'Welcome to Dining Philosophers' })
    ).toBeVisible();
    await expect(page.locator('#username')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
  });

  test('can navigate to register page', async ({ page }) => {
    await page.goto('/login');
    await page.click('text=Create one');
    await expect(page).toHaveURL(/\/register/);
  });
});

test.describe('Register Page', () => {
  test('shows register form', async ({ page }) => {
    await page.goto('/register');

    // Should show register form
    await expect(
      page.locator('h1', { hasText: 'Create an Account' })
    ).toBeVisible();
    await expect(page.locator('#username')).toBeVisible();
    await expect(page.locator('#displayName')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.locator('#confirmPassword')).toBeVisible();
  });

  test('can navigate to login page', async ({ page }) => {
    await page.goto('/register');
    await page.click('text=Sign in');
    await expect(page).toHaveURL(/\/login/);
  });

  test('shows error for mismatched passwords', async ({ page }) => {
    await page.goto('/register');
    await page.fill('#username', 'newuser');
    await page.fill('#displayName', 'New User');
    await page.fill('#password', 'password123');
    await page.fill('#confirmPassword', 'different');
    await page.click('button[type="submit"]');

    await expect(page.locator('text=Passwords do not match')).toBeVisible();
  });
});
