'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useAuth, useLanguage } from '@/contexts';

export default function RegisterPage() {
  const router = useRouter();
  const { register, isAuthenticated, isLoading } = useAuth();
  const { t, setLocale } = useLanguage();
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [languagePreference, setLanguagePreference] = useState('en');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLanguageChange = (newLanguage: string) => {
    setLanguagePreference(newLanguage);
    setLocale(newLanguage);
  };

  // Redirect if already authenticated
  if (!isLoading && isAuthenticated) {
    router.replace('/');
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError(t.register.passwordsDoNotMatch);
      return;
    }

    if (password.length < 6) {
      setError(t.register.passwordTooShort);
      return;
    }

    setIsSubmitting(true);

    try {
      await register(username, displayName, password, languagePreference);
      router.push('/');
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t.register.registrationFailed
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-900">
        <div className="text-zinc-500 dark:text-zinc-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-900">
      <div className="w-full max-w-md">
        <div className="rounded-xl bg-white p-8 shadow-lg dark:bg-zinc-800">
          <h1 className="mb-6 text-center text-2xl font-bold text-zinc-900 dark:text-zinc-100">
            {t.register.title}
          </h1>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                {error}
              </div>
            )}

            <div>
              <label
                htmlFor="username"
                className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.register.username}
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-4 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                placeholder={t.register.usernamePlaceholder}
                required
                autoFocus
              />
            </div>

            <div>
              <label
                htmlFor="displayName"
                className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.register.displayName}
              </label>
              <input
                id="displayName"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-4 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                placeholder={t.register.displayNamePlaceholder}
                required
              />
            </div>

            <div>
              <label
                htmlFor="languagePreference"
                className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.register.language}
              </label>
              <select
                id="languagePreference"
                value={languagePreference}
                onChange={(e) => handleLanguageChange(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-4 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
              >
                <option value="en">{t.languages.en}</option>
                <option value="es">{t.languages.es}</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="password"
                className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.register.password}
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-4 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                placeholder={t.register.passwordPlaceholder}
                required
              />
            </div>

            <div>
              <label
                htmlFor="confirmPassword"
                className="mb-1 block text-sm font-medium text-zinc-700 dark:text-zinc-300"
              >
                {t.register.confirmPassword}
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-4 py-2 text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:border-zinc-600 dark:bg-zinc-700 dark:text-zinc-100"
                placeholder={t.register.confirmPasswordPlaceholder}
                required
              />
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500/50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSubmitting
                ? t.register.creatingAccount
                : t.register.createAccount}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-zinc-600 dark:text-zinc-400">
            {t.register.alreadyHaveAccount}{' '}
            <Link
              href="/login"
              className="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
            >
              {t.register.signIn}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
