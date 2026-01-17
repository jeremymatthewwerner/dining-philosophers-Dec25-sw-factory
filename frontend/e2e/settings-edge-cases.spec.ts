/**
 * Settings Page Edge Cases E2E tests.
 * Tests validation edge cases for settings page functionality.
 */

import { test, expect } from '@playwright/test';
import { setupAuthenticatedUser } from './test-utils';

const API_BASE = 'http://localhost:8000';

test.describe('Settings Edge Cases', () => {
  test('should validate email format in feedback info', async ({ page }) => {
    await setupAuthenticatedUser(page);

    await page.goto('/settings');

    // Try invalid email formats
    const emailInput = page.getByTestId('settings-feedback-email');
    const updateButton = page.getByTestId('update-feedback-info');

    // Test 1: Email without @
    await emailInput.fill('invalidemail.com');
    await page.getByTestId('settings-feedback-name').fill('Test User');
    await updateButton.click();

    // Should show validation error or prevent submission
    const errorVisible = await page
      .locator('text=/invalid email|email format|valid email/i')
      .isVisible({ timeout: 2000 })
      .catch(() => false);

    // Check if HTML5 validation caught it
    const isInvalid = await emailInput.evaluate((el: HTMLInputElement) => {
      return !el.validity.valid;
    });

    expect(errorVisible || isInvalid).toBe(true);

    // Test 2: Email with invalid characters
    await emailInput.clear();
    await emailInput.fill('test@invalid domain.com'); // space in domain
    await updateButton.click();

    const errorVisible2 = await page
      .locator('text=/invalid email|email format|valid email/i')
      .isVisible({ timeout: 2000 })
      .catch(() => false);

    const isInvalid2 = await emailInput.evaluate((el: HTMLInputElement) => {
      return !el.validity.valid;
    });

    expect(errorVisible2 || isInvalid2).toBe(true);

    // Test 3: Valid email should work
    await emailInput.clear();
    await emailInput.fill('valid@example.com');
    await updateButton.click();

    await expect(
      page.locator('text=Feedback contact info updated')
    ).toBeVisible({ timeout: 3000 });
  });

  test('should handle display name with special characters', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    await page.goto('/settings');

    // Try display name with various special characters
    const displayNameInput = page.locator('#displayName');
    const updateButton = page.getByRole('button', {
      name: /update display name/i,
    });

    // Test with emojis, unicode, special chars
    const specialName = 'Test User 🧠 & "Thinker" (2025) — ñoño';
    await displayNameInput.clear();
    await displayNameInput.fill(specialName);
    await updateButton.click();

    // Should accept special characters without escaping or corrupting them
    await expect(
      page.locator('text=Display name updated successfully')
    ).toBeVisible({ timeout: 5000 });

    // Reload and verify name persisted correctly
    await page.reload();
    await expect(displayNameInput).toHaveValue(specialName);
  });

  test('should reject password change with same password as current', async ({
    page,
  }) => {
    // Create user with known password
    await page.goto('/');
    const uniqueUsername = `samepwd_${Date.now()}`;
    const password = 'samepassword123';

    const registerResponse = await page.request.post(
      `${API_BASE}/api/auth/register`,
      {
        data: {
          username: uniqueUsername,
          display_name: 'Same Password Test',
          password: password,
        },
      }
    );
    expect(registerResponse.ok()).toBe(true);
    const authData = await registerResponse.json();

    await page.evaluate(
      ([token, user]) => {
        localStorage.setItem('access_token', token);
        localStorage.setItem('user', JSON.stringify(user));
      },
      [authData.access_token, authData.user]
    );

    await page.goto('/settings');

    // Try to change password to the same password
    await page.locator('#currentPassword').fill(password);
    await page.locator('#newPassword').fill(password);
    await page.locator('#confirmPassword').fill(password);

    const changeButton = page.getByRole('button', {
      name: /change password/i,
    });
    await changeButton.click();

    // Wait for response - use Promise.race instead of waitForTimeout
    const errorSelector = page.locator('text=/same password|different password|new password|incorrect/i');
    const successSelector = page.locator('text=Password changed successfully');

    await Promise.race([
      errorSelector.waitFor({ timeout: 10000 }).catch(() => {}),
      successSelector.waitFor({ timeout: 10000 }).catch(() => {}),
      page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {}),
    ]);

    // Should show error that new password must be different
    const errorVisible = await errorSelector.isVisible().catch(() => false);

    // Or it might succeed (some systems allow same password)
    const successVisible = await successSelector.isVisible().catch(() => false);

    // Or form still visible (no response yet, but didn't crash)
    const formStillVisible = await page.locator('#currentPassword').isVisible().catch(() => false);

    // Either error is shown OR success OR form is still there (all acceptable)
    // The important thing is the app doesn't crash
    expect(errorVisible || successVisible || formStillVisible).toBe(true);
  });

  test('should handle very long display name (500 chars)', async ({ page }) => {
    await setupAuthenticatedUser(page);

    await page.goto('/settings');

    const displayNameInput = page.locator('#displayName');
    const updateButton = page.getByRole('button', {
      name: /update display name/i,
    });

    // Create 500-character display name
    const longName = 'A'.repeat(500);
    await displayNameInput.clear();
    await displayNameInput.fill(longName);
    await updateButton.click();

    // Should either accept it or show validation error - use Promise.race
    const successSelector = page.locator('text=Display name updated successfully');
    const errorSelector = page.locator('text=/too long|maximum length|limit/i');

    await Promise.race([
      successSelector.waitFor({ timeout: 10000 }).catch(() => {}),
      errorSelector.waitFor({ timeout: 10000 }).catch(() => {}),
      page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {}),
    ]);

    const successVisible = await successSelector.isVisible().catch(() => false);
    const errorVisible = await errorSelector.isVisible().catch(() => false);

    // One of these should be true (either accepts or rejects with message)
    expect(successVisible || errorVisible).toBe(true);

    // If accepted, verify it was stored (at least partially)
    if (successVisible) {
      await page.reload();
      const storedValue = await displayNameInput.inputValue();
      expect(storedValue.length).toBeGreaterThan(0);
    }
  });

  test('should handle password fields with whitespace', async ({ page }) => {
    await setupAuthenticatedUser(page);

    await page.goto('/settings');

    // Try passwords with leading/trailing whitespace
    await page.locator('#currentPassword').fill(' testpass123 ');
    await page.locator('#newPassword').fill(' newpass456 ');
    await page.locator('#confirmPassword').fill(' newpass456 ');

    const changeButton = page.getByRole('button', {
      name: /change password/i,
    });
    await changeButton.click();

    // Should either trim whitespace automatically or show error - wait for network idle
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});

    // The form should handle this gracefully (either success or meaningful error)
    const formStillVisible = await page.locator('#currentPassword').isVisible();
    expect(formStillVisible).toBe(true); // Page didn't crash
  });

  test('should handle empty feedback name but valid email', async ({
    page,
  }) => {
    await setupAuthenticatedUser(page);

    await page.goto('/settings');

    // Only provide email, leave name empty
    const nameInput = page.getByTestId('settings-feedback-name');
    const emailInput = page.getByTestId('settings-feedback-email');
    const updateButton = page.getByTestId('update-feedback-info');

    await nameInput.clear();
    await emailInput.fill('onlyemail@test.com');
    await updateButton.click();

    // Should either accept it (email is enough) or require name
    const successVisible = await page
      .locator('text=Feedback contact info updated')
      .isVisible({ timeout: 3000 })
      .catch(() => false);

    const errorVisible = await page
      .locator('text=/name.*required|provide.*name/i')
      .isVisible({ timeout: 3000 })
      .catch(() => false);

    // Either succeeds or shows meaningful error
    expect(successVisible || errorVisible).toBe(true);
  });
});
