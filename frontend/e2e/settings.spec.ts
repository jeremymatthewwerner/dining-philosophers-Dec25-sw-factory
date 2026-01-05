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

    // Click settings link in sidebar
    const settingsLink = page.getByTestId('settings-link');
    await settingsLink.waitFor({ state: 'visible' });
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
});
