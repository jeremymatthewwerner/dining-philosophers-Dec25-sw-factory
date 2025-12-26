'use client';

import { createContext, useContext, useState } from 'react';
import en from '@/locales/en.json';
import es from '@/locales/es.json';
import { useAuth } from './AuthContext';

type Translations = typeof en;

const translations: Record<string, Translations> = {
  en,
  es,
};

interface LanguageContextType {
  locale: string;
  t: Translations;
  setLocale: (locale: string) => void;
}

const LanguageContext = createContext<LanguageContextType | undefined>(
  undefined
);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [overrideLocale, setOverrideLocale] = useState<string | null>(null);

  // Use override locale if set, otherwise use user's preference, otherwise default to 'en'
  const locale = overrideLocale || user?.language_preference || 'en';

  const setLocale = (newLocale: string) => {
    if (translations[newLocale]) {
      setOverrideLocale(newLocale);
    }
  };

  const t = translations[locale] || translations.en;

  return (
    <LanguageContext.Provider value={{ locale, t, setLocale }}>
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
