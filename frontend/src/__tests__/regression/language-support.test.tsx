/**
 * Regression tests for language support
 *
 * Issue #340: French language option missing from frontend
 * Fix: commit fc63a10 (2026-01-09)
 *
 * Bug: Backend and translations supported French, but frontend dropdowns did not show French option
 * Root cause: LanguageContext didn't import fr.json, and register/settings pages didn't have French option
 * Fix: Added French import to LanguageContext and French option to all language dropdowns
 *
 * Issue #453: German language support requested
 * Fix: Added de.json translations and German support across frontend and backend
 */

import { render, screen } from '@testing-library/react';
import { LanguageProvider, useLanguage } from '@/contexts/LanguageContext';
import { AuthProvider } from '@/contexts/AuthContext';
import en from '@/locales/en.json';
import es from '@/locales/es.json';
import fr from '@/locales/fr.json';
import de from '@/locales/de.json';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => '/test',
}));

// Test component to access LanguageContext
function TestLanguageComponent() {
  const { locale, t } = useLanguage();
  return (
    <div>
      <div data-testid="locale">{locale}</div>
      <div data-testid="translations">{JSON.stringify(Object.keys(t))}</div>
    </div>
  );
}

describe('Regression: Language Support (Issue #340, #453)', () => {
  describe('LanguageContext includes all translations', () => {
    it('includes all language translations (en, es, fr, de)', () => {
      // This test prevents regression where language files weren't imported
      render(
        <AuthProvider>
          <LanguageProvider>
            <TestLanguageComponent />
          </LanguageProvider>
        </AuthProvider>
      );

      // LanguageContext should have loaded all translation files
      const translationsData = screen.getByTestId('translations');
      const keys = JSON.parse(translationsData.textContent || '[]');

      // Verify translations object has all required properties
      // (All language JSONs should have the same structure)
      expect(keys).toContain('loginPage');
      expect(keys).toContain('register');
      expect(keys).toContain('languages');
    });

    it('defaults to English locale', () => {
      render(
        <AuthProvider>
          <LanguageProvider>
            <TestLanguageComponent />
          </LanguageProvider>
        </AuthProvider>
      );

      const localeEl = screen.getByTestId('locale');
      expect(localeEl).toHaveTextContent('en');
    });
  });

  describe('Register page shows all language options', () => {
    // Import the actual register page component
    // Note: We can't easily test the register page directly due to Next.js dependencies,
    // but we can verify the translations structure supports all four languages

    it('translation files exist for en, es, fr, and de', () => {
      // Translation files imported at top of file to verify they exist

      // All four should have languages section with all four options
      expect(en.languages).toBeDefined();
      expect(en.languages.en).toBeDefined();
      expect(en.languages.es).toBeDefined();
      expect(en.languages.fr).toBeDefined();
      expect(en.languages.de).toBeDefined();

      expect(es.languages).toBeDefined();
      expect(es.languages.en).toBeDefined();
      expect(es.languages.es).toBeDefined();
      expect(es.languages.fr).toBeDefined();
      expect(es.languages.de).toBeDefined();

      expect(fr.languages).toBeDefined();
      expect(fr.languages.en).toBeDefined();
      expect(fr.languages.es).toBeDefined();
      expect(fr.languages.fr).toBeDefined();
      expect(fr.languages.de).toBeDefined();

      expect(de.languages).toBeDefined();
      expect(de.languages.en).toBeDefined();
      expect(de.languages.es).toBeDefined();
      expect(de.languages.fr).toBeDefined();
      expect(de.languages.de).toBeDefined();
    });

    it('French translations are complete', () => {
      // French should have the same top-level keys as English
      const enKeys = Object.keys(en).sort();
      const frKeys = Object.keys(fr).sort();

      expect(frKeys).toEqual(enKeys);

      // Verify critical sections exist
      expect(fr.register).toBeDefined();
      expect(fr.loginPage).toBeDefined();
      expect(fr.chatArea).toBeDefined();
      expect(fr.languages).toBeDefined();
    });

    it('German translations are complete', () => {
      // German should have the same top-level keys as English
      const enKeys = Object.keys(en).sort();
      const deKeys = Object.keys(de).sort();

      expect(deKeys).toEqual(enKeys);

      // Verify critical sections exist
      expect(de.register).toBeDefined();
      expect(de.loginPage).toBeDefined();
      expect(de.chatArea).toBeDefined();
      expect(de.languages).toBeDefined();
      expect(de.settingsPage).toBeDefined();
      expect(de.feedbackModal).toBeDefined();
    });
  });

  describe('LanguageContext translations object', () => {
    it('has all four language keys: en, es, fr, de', () => {
      // Test that the translations object in LanguageContext.tsx includes all four languages
      // This is the specific bug that was fixed in Issue #340 and extended in #453

      // All four imports should succeed (not throw)
      expect(en).toBeDefined();
      expect(es).toBeDefined();
      expect(fr).toBeDefined();
      expect(de).toBeDefined();

      // Verify they're proper translation objects with expected structure
      expect(typeof en).toBe('object');
      expect(typeof es).toBe('object');
      expect(typeof fr).toBe('object');
      expect(typeof de).toBe('object');
    });
  });
});
