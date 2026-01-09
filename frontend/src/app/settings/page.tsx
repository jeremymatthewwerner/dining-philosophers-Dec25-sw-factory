'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { useTheme, ThemeMode } from '@/contexts';
import * as api from '@/lib/api';

export default function SettingsPage() {
  const router = useRouter();
  const { user, isLoading: authLoading, updateDisplayName } = useAuth();
  const { t, locale, setLocale } = useLanguage();
  const { theme, setTheme } = useTheme();

  // Display name form state
  const [displayName, setDisplayName] = useState('');
  const [displayNameError, setDisplayNameError] = useState<string | null>(null);
  const [displayNameSuccess, setDisplayNameSuccess] = useState<string | null>(
    null
  );
  const [isUpdatingDisplayName, setIsUpdatingDisplayName] = useState(false);

  // Password form state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Initialize display name from user when user data becomes available
  useEffect(() => {
    if (user) {
      setDisplayName(user.display_name || '');
    }
  }, [user]);

  // Redirect if not authenticated
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  async function handleUpdateDisplayName(e: React.FormEvent) {
    e.preventDefault();
    setDisplayNameError(null);
    setDisplayNameSuccess(null);

    if (!displayName.trim()) {
      setDisplayNameError(t.settingsPage.displayNameRequired);
      return;
    }

    if (displayName.length > 100) {
      setDisplayNameError(t.settingsPage.displayNameTooLong);
      return;
    }

    try {
      setIsUpdatingDisplayName(true);
      await updateDisplayName(displayName.trim());
      setDisplayNameSuccess(t.settingsPage.displayNameUpdated);
    } catch (err) {
      setDisplayNameError(
        err instanceof Error ? err.message : t.settingsPage.displayNameFailed
      );
    } finally {
      setIsUpdatingDisplayName(false);
    }
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!currentPassword) {
      setPasswordError(t.settingsPage.currentPasswordRequired);
      return;
    }

    if (!newPassword) {
      setPasswordError(t.settingsPage.newPasswordRequired);
      return;
    }

    if (newPassword.length < 6) {
      setPasswordError(t.settingsPage.passwordTooShort);
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError(t.settingsPage.passwordsDoNotMatch);
      return;
    }

    try {
      setIsChangingPassword(true);
      await api.changePassword(currentPassword, newPassword);
      setPasswordSuccess(t.settingsPage.passwordChanged);
      // Clear form on success
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setPasswordError(
        err instanceof Error ? err.message : t.settingsPage.passwordChangeFailed
      );
    } finally {
      setIsChangingPassword(false);
    }
  }

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-900">
        <div className="text-zinc-500 dark:text-zinc-400">
          {t.common.loading}
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-900">
      <div className="mx-auto max-w-2xl px-4 py-8">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
              {t.settingsPage.title}
            </h1>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              {t.settingsPage.description}
            </p>
          </div>
          <button
            onClick={() => router.push('/')}
            className="rounded-lg bg-zinc-200 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600"
          >
            {t.settingsPage.backToChat}
          </button>
        </div>

        {/* Profile Section */}
        <div className="mb-6 rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
          <h2 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {t.settingsPage.profileSection}
          </h2>

          <form onSubmit={handleUpdateDisplayName} className="space-y-4">
            <div>
              <label
                htmlFor="displayName"
                className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.settingsPage.displayName}
              </label>
              <input
                type="text"
                id="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                placeholder={t.settingsPage.displayNamePlaceholder}
                maxLength={100}
              />
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                {t.settingsPage.displayNameHelp}
              </p>
            </div>

            {displayNameError && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                {displayNameError}
              </div>
            )}

            {displayNameSuccess && (
              <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
                {displayNameSuccess}
              </div>
            )}

            <button
              type="submit"
              disabled={isUpdatingDisplayName}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {isUpdatingDisplayName
                ? t.settingsPage.updating
                : t.settingsPage.updateDisplayName}
            </button>
          </form>
        </div>

        {/* Language Section */}
        <div className="mb-6 rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
          <h2 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {t.settingsPage.languageSection}
          </h2>

          <div>
            <label
              htmlFor="language"
              className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              {t.settingsPage.preferredLanguage}
            </label>
            <select
              id="language"
              value={locale}
              onChange={(e) => setLocale(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
            >
              <option value="en">{t.languages.en}</option>
              <option value="es">{t.languages.es}</option>
            </select>
          </div>
        </div>

        {/* Theme Section */}
        <div className="mb-6 rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
          <h2 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {t.settingsPage.themeSection}
          </h2>

          <div>
            <label
              htmlFor="theme"
              className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
            >
              {t.settingsPage.themePreference}
            </label>
            <select
              id="theme"
              value={theme}
              onChange={(e) => setTheme(e.target.value as ThemeMode)}
              className="mt-1 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
            >
              <option value="system">{t.settingsPage.themeSystem}</option>
              <option value="light">{t.settingsPage.themeLight}</option>
              <option value="dark">{t.settingsPage.themeDark}</option>
            </select>
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
              {t.settingsPage.themeHelp}
            </p>
          </div>
        </div>

        {/* Password Section */}
        <div className="rounded-lg bg-white p-6 shadow dark:bg-zinc-800">
          <h2 className="mb-4 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {t.settingsPage.passwordSection}
          </h2>

          <form onSubmit={handleChangePassword} className="space-y-4">
            <div>
              <label
                htmlFor="currentPassword"
                className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.settingsPage.currentPassword}
              </label>
              <input
                type="password"
                id="currentPassword"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                placeholder={t.settingsPage.currentPasswordPlaceholder}
              />
            </div>

            <div>
              <label
                htmlFor="newPassword"
                className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.settingsPage.newPassword}
              </label>
              <input
                type="password"
                id="newPassword"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                placeholder={t.settingsPage.newPasswordPlaceholder}
              />
            </div>

            <div>
              <label
                htmlFor="confirmPassword"
                className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.settingsPage.confirmPassword}
              </label>
              <input
                type="password"
                id="confirmPassword"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                placeholder={t.settingsPage.confirmPasswordPlaceholder}
              />
            </div>

            {passwordError && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-400">
                {passwordError}
              </div>
            )}

            {passwordSuccess && (
              <div className="rounded-lg bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
                {passwordSuccess}
              </div>
            )}

            <button
              type="submit"
              disabled={isChangingPassword}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {isChangingPassword
                ? t.settingsPage.changingPassword
                : t.settingsPage.changePassword}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
