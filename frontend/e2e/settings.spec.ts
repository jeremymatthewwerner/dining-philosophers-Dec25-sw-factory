/**
 * E2E tests for user settings page.
 * Tests display name updates, password changes, and language preferences.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser, loginUser } from './test-utils';

const API_BASE = 'http://localhost:8000';

test.describe('Settings Page', () => {
  test('should navigate to settings page from sidebar', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // First, open the user menu dropdown
    const userMenuButton = page.getByTestId('user-menu-button');
    await userMenuButton.click();

    // Wait for the dropdown to appear
    const dropdown = page.getByTestId('user-menu-dropdown');
    await expect(dropdown).toBeVisible();

    // Click settings link in the dropdown menu
    const settingsLink = page.getByTestId('user-menu-settings');
    await settingsLink.click();

    // Should be on settings page
    await expect(page).toHaveURL('/settings');
    await expect(page.locator('h1')).toContainText('Settings');
  });

  test('should redirect to login if not authenticated', async ({ page }) => {
    // Go directly to settings without auth
    await page.goto('/settings');

    // Should redirect to login
    await expect(page).toHaveURL('/login');
  });

  test.describe('Display Name Update', () => {
    test('should pre-populate display name from user data', async ({ page }) => {
      // Register with a known display name
      await page.goto('/');

      const uniqueUsername = `prepoptest_${Date.now()}`;
      const expectedDisplayName = 'Pre-Populated Test User';
      const password = 'testpass123';

      // Register via API with specific display name
      const registerResponse = await page.request.post(
        `${API_BASE}/api/auth/register`,
        {
          data: {
            username: uniqueUsername,
            display_name: expectedDisplayName,
            password: password,
          },
        }
      );
      expect(registerResponse.ok()).toBe(true);
      const authData = await registerResponse.json();

      // Store auth in localStorage
      await page.evaluate(
        ([token, user]) => {
          localStorage.setItem('access_token', token);
          localStorage.setItem('user', JSON.stringify(user));
        },
        [authData.access_token, authData.user]
      );

      // Navigate to settings
      await page.goto('/settings');
      await expect(page.locator('h1')).toContainText('Settings');

      // The display name input should be pre-populated with the user's display name
      const displayNameInput = page.locator('#displayName');
      await expect(displayNameInput).toHaveValue(expectedDisplayName);
    });

    test('should update display name successfully', async ({ page }) => {
      await setupAuthenticatedUser(page);

      // Navigate to settings
      await page.goto('/settings');
      await expect(page.locator('h1')).toContainText('Settings');

      // Find and fill the display name input
      const displayNameInput = page.locator('#displayName');
      await displayNameInput.clear();
      await displayNameInput.fill('New Display Name');

      // Submit the form
      const updateButton = page.getByRole('button', {
        name: /update display name/i,
      });
      await updateButton.click();

      // Should show success message
      await expect(
        page.locator('text=Display name updated successfully')
      ).toBeVisible({ timeout: 5000 });
    });

    test('should show error for empty display name', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.goto('/settings');

      const displayNameInput = page.locator('#displayName');
      await displayNameInput.clear();

      const updateButton = page.getByRole('button', {
        name: /update display name/i,
      });
      await updateButton.click();

      // Should show error message
      await expect(
        page.locator('text=Display name is required')
      ).toBeVisible();
    });
  });

  test.describe('Password Change', () => {
    test('should change password successfully', async ({ page }) => {
      // Register with known credentials
      await page.goto('/');
      const uniqueUsername = `pwdtest_${Date.now()}`;
      const originalPassword = 'originalpass123';
      const newPassword = 'newpassword456';

      // Register via API
      const registerResponse = await page.request.post(
        `${API_BASE}/api/auth/register`,
        {
          data: {
            username: uniqueUsername,
            display_name: 'Password Test User',
            password: originalPassword,
          },
        }
      );
      expect(registerResponse.ok()).toBe(true);
      const authData = await registerResponse.json();

      // Store auth in localStorage
      await page.evaluate(
        ([token, user]) => {
          localStorage.setItem('access_token', token);
          localStorage.setItem('user', JSON.stringify(user));
        },
        [authData.access_token, authData.user]
      );

      // Navigate to settings
      await page.goto('/settings');

      // Fill password change form
      await page.locator('#currentPassword').fill(originalPassword);
      await page.locator('#newPassword').fill(newPassword);
      await page.locator('#confirmPassword').fill(newPassword);

      // Submit
      const changeButton = page.getByRole('button', {
        name: /change password/i,
      });
      await changeButton.click();

      // Should show success
      await expect(
        page.locator('text=Password changed successfully')
      ).toBeVisible({ timeout: 5000 });

      // Clear local storage
      await page.evaluate(() => localStorage.clear());

      // Navigate to login and verify new password works
      await page.goto('/login');
      await page.locator('#username').fill(uniqueUsername);
      await page.locator('#password').fill(newPassword);
      await page.getByRole('button', { name: /sign in/i }).click();

      // Should be redirected to home
      await expect(page).toHaveURL('/');
    });

    test('should show error for incorrect current password', async ({
      page,
    }) => {
      await setupAuthenticatedUser(page);

      await page.goto('/settings');

      // Fill with wrong current password
      await page.locator('#currentPassword').fill('wrongpassword');
      await page.locator('#newPassword').fill('newpassword123');
      await page.locator('#confirmPassword').fill('newpassword123');

      const changeButton = page.getByRole('button', {
        name: /change password/i,
      });
      await changeButton.click();

      // Should show error
      await expect(
        page.locator('text=Current password is incorrect')
      ).toBeVisible({ timeout: 5000 });
    });

    test('should show error for mismatched passwords', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.goto('/settings');

      await page.locator('#currentPassword').fill('testpass123');
      await page.locator('#newPassword').fill('newpassword123');
      await page.locator('#confirmPassword').fill('differentpassword');

      const changeButton = page.getByRole('button', {
        name: /change password/i,
      });
      await changeButton.click();

      // Should show mismatch error
      await expect(page.locator('text=Passwords do not match')).toBeVisible();
    });

    test('should show error for password too short', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.goto('/settings');

      await page.locator('#currentPassword').fill('testpass123');
      await page.locator('#newPassword').fill('short');
      await page.locator('#confirmPassword').fill('short');

      const changeButton = page.getByRole('button', {
        name: /change password/i,
      });
      await changeButton.click();

      // Should show length error
      await expect(
        page.locator('text=Password must be at least 6 characters')
      ).toBeVisible();
    });
  });

  test.describe('Language Selection', () => {
    test('should display language selector', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.goto('/settings');

      // Language selector should be visible
      const languageSelect = page.locator('#language');
      await expect(languageSelect).toBeVisible();

      // Should have English and Spanish options
      await expect(languageSelect.locator('option[value="en"]')).toBeAttached();
      await expect(languageSelect.locator('option[value="es"]')).toBeAttached();
    });

    test('should change language to Spanish', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.goto('/settings');

      // Change to Spanish
      const languageSelect = page.locator('#language');
      await languageSelect.selectOption('es');

      // Page content should change to Spanish
      await expect(page.locator('h1')).toContainText('Configuraci');
    });
  });

  test('should navigate back to chat', async ({ page }) => {
    await setupAuthenticatedUser(page);

    await page.goto('/settings');

    // Click back to chat button
    const backButton = page.getByRole('button', { name: /back to chat/i });
    await backButton.click();

    // Should be on home page
    await expect(page).toHaveURL('/');
  });

  test.describe('Feedback Contact Info', () => {
    test('should display feedback info section', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.goto('/settings');

      // Check section heading exists
      await expect(page.locator('text=Feedback Contact Info')).toBeVisible();

      // Check form elements exist
      await expect(page.getByTestId('settings-feedback-name')).toBeVisible();
      await expect(page.getByTestId('settings-feedback-email')).toBeVisible();
      await expect(page.getByTestId('update-feedback-info')).toBeVisible();
      await expect(page.getByTestId('clear-feedback-info')).toBeVisible();
    });

    test('should save and display feedback info', async ({ page }) => {
      await setupAuthenticatedUser(page);

      await page.goto('/settings');

      // Fill in feedback info
      const nameInput = page.getByTestId('settings-feedback-name');
      const emailInput = page.getByTestId('settings-feedback-email');

      await nameInput.fill('Test Feedback User');
      await emailInput.fill('feedback@test.com');

      // Click update button
      await page.getByTestId('update-feedback-info').click();

      // Should show success message
      await expect(
        page.locator('text=Feedback contact info updated')
      ).toBeVisible();

      // Reload page and verify persistence
      await page.reload();

      await expect(nameInput).toHaveValue('Test Feedback User');
      await expect(emailInput).toHaveValue('feedback@test.com');
    });

    test('should clear saved feedback info', async ({ page }) => {
      await setupAuthenticatedUser(page);

      // First set some values
      await page.evaluate(() => {
        localStorage.setItem('feedback_name', 'Clear Test');
        localStorage.setItem('feedback_email', 'clear@test.com');
      });

      await page.goto('/settings');

      // Verify values are loaded
      const nameInput = page.getByTestId('settings-feedback-name');
      const emailInput = page.getByTestId('settings-feedback-email');

      await expect(nameInput).toHaveValue('Clear Test');
      await expect(emailInput).toHaveValue('clear@test.com');

      // Click clear button
      await page.getByTestId('clear-feedback-info').click();

      // Should show cleared message
      await expect(
        page.locator('text=Feedback contact info cleared')
      ).toBeVisible();

      // Fields should be empty
      await expect(nameInput).toHaveValue('');
      await expect(emailInput).toHaveValue('');

      // Verify localStorage is cleared
      const storedName = await page.evaluate(() =>
        localStorage.getItem('feedback_name')
      );
      const storedEmail = await page.evaluate(() =>
        localStorage.getItem('feedback_email')
      );
      expect(storedName).toBeNull();
      expect(storedEmail).toBeNull();
    });

    test('should pre-fill feedback modal with saved info', async ({ page }) => {
      await setupAuthenticatedUser(page);

      // Set feedback info
      await page.evaluate(() => {
        localStorage.setItem('feedback_name', 'Modal Test User');
        localStorage.setItem('feedback_email', 'modal@test.com');
      });

      await page.goto('/');

      // Open sidebar and click feedback button
      // Note: The feedback button may be in the sidebar
      const feedbackButton = page.locator('[data-testid="feedback-button"]');
      if (await feedbackButton.isVisible()) {
        await feedbackButton.click();
      } else {
        // If not visible, might need to open sidebar first
        const sidebarToggle = page.locator('[data-testid="sidebar-toggle"]');
        if (await sidebarToggle.isVisible()) {
          await sidebarToggle.click();
          await page.waitForTimeout(300);
        }
        // Look for feedback link in sidebar
        const feedbackLink = page.locator('text=Feedback').first();
        await feedbackLink.click();
      }

      // Wait for modal
      await expect(page.getByTestId('feedback-modal')).toBeVisible({
        timeout: 5000,
      });

      // Verify fields are pre-filled
      await expect(page.getByTestId('feedback-name')).toHaveValue(
        'Modal Test User'
      );
      await expect(page.getByTestId('feedback-email')).toHaveValue(
        'modal@test.com'
      );
    });
  });
});
