'use client';

import { createContext, useContext, useState } from 'react';
import en from '@/locales/en.json';
import es from '@/locales/es.json';
import { useAuth } from './AuthContext';
import * as api from '@/lib/api';

type Translations = typeof en;

const translations: Record<string, Translations> = {
  en,
  es,
};

/**
 * Helper function to interpolate variables into translation strings
 * Example: interpolate("Hello {name}", { name: "World" }) => "Hello World"
 */
function interpolate(
  template: string,
  variables: Record<string, string | number>
): string {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    return String(variables[key] ?? `{${key}}`);
  });
}

interface LanguageContextType {
  locale: string;
  t: Translations;
  setLocale: (locale: string) => Promise<void>;
  interpolate: typeof interpolate;
}

const LanguageContext = createContext<LanguageContextType | undefined>(
  undefined
);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const { user, refreshUser } = useAuth();
  const [overrideLocale, setOverrideLocale] = useState<string | null>(null);

  // Use override locale if set, otherwise use user's preference, otherwise default to 'en'
  const locale = overrideLocale || user?.language_preference || 'en';

  const setLocale = async (newLocale: string) => {
    if (translations[newLocale]) {
      setOverrideLocale(newLocale);

      // If user is authenticated, persist to database
      if (user) {
        try {
          await api.updateLanguage(newLocale);
          // Refresh user to get updated language_preference
          await refreshUser();
        } catch (error) {
          console.error('Failed to update language preference:', error);
          // Keep the UI updated even if API call fails
        }
      }
    }
  };

  const t = translations[locale] || translations.en;

  return (
    <LanguageContext.Provider value={{ locale, t, setLocale, interpolate }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (context === undefined) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
