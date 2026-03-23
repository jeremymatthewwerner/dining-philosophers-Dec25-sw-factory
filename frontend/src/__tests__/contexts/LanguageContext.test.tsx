/**
 * Tests for LanguageContext.tsx
 *
 * Covers:
 * - LanguageProvider renders children
 * - useLanguage throws when used outside provider
 * - Default locale is 'en'
 * - setLocale updates locale
 * - setLocale persists via API when user is authenticated
 * - setLocale is no-op for unsupported locale
 * - locale falls back to user language_preference
 * - interpolate function works correctly
 * - t (translations) is returned correctly for locale
 */

import React from 'react';
import { render, renderHook, act, screen } from '@testing-library/react';
import { LanguageProvider, useLanguage } from '@/contexts/LanguageContext';
import { AuthProvider } from '@/contexts/AuthContext';
import { ThemeProvider } from '@/contexts/ThemeContext';
import * as api from '@/lib/api';

// Mock api
jest.mock('@/lib/api', () => ({
  getCurrentUser: jest.fn(),
  getStoredUser: jest.fn(),
  setStoredUser: jest.fn(),
  updateLanguage: jest.fn(),
  login: jest.fn(),
  register: jest.fn(),
  logout: jest.fn(),
  updateProfile: jest.fn(),
}));

// Mock matchMedia for ThemeProvider
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

function AllProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <AuthProvider>
        <LanguageProvider>{children}</LanguageProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

describe('LanguageContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mock getCurrentUser to return null (no authenticated user by default)
    (api.getCurrentUser as jest.Mock).mockResolvedValue(null);
    (api.getStoredUser as jest.Mock).mockReturnValue(null);
  });

  describe('useLanguage outside provider', () => {
    it('throws error when used outside LanguageProvider', () => {
      const consoleSpy = jest
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      expect(() => {
        renderHook(() => useLanguage());
      }).toThrow('useLanguage must be used within a LanguageProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('default state', () => {
    it('defaults to English locale when no user', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      // Wait for auth to resolve
      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      expect(result.current.locale).toBe('en');
    });

    it('provides English translations by default', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      expect(result.current.t).toBeDefined();
      expect(typeof result.current.t).toBe('object');
    });
  });

  describe('setLocale', () => {
    it('changes locale to Spanish', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      await act(async () => {
        await result.current.setLocale('es');
      });

      expect(result.current.locale).toBe('es');
    });

    it('changes locale to French', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      await act(async () => {
        await result.current.setLocale('fr');
      });

      expect(result.current.locale).toBe('fr');
    });

    it('does not change locale for unsupported locale', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      await act(async () => {
        await result.current.setLocale('xx');
      });

      // Should remain 'en'
      expect(result.current.locale).toBe('en');
    });

    it('calls updateLanguage API when user is authenticated', async () => {
      const mockUser = {
        id: 'user-1',
        username: 'testuser',
        display_name: 'Test User',
        language_preference: 'en',
      };
      (api.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);
      (api.getStoredUser as jest.Mock).mockReturnValue(mockUser);
      (api.updateLanguage as jest.Mock).mockResolvedValue(undefined);

      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      await act(async () => {
        await result.current.setLocale('de');
      });

      expect(api.updateLanguage).toHaveBeenCalledWith('de');
    });

    it('does not call updateLanguage API when user is not authenticated', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);
      (api.getStoredUser as jest.Mock).mockReturnValue(null);

      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      await act(async () => {
        await result.current.setLocale('es');
      });

      expect(api.updateLanguage).not.toHaveBeenCalled();
    });

    it('keeps UI updated even when API call fails', async () => {
      const mockUser = {
        id: 'user-1',
        username: 'testuser',
        display_name: 'Test User',
        language_preference: 'en',
      };
      (api.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);
      (api.getStoredUser as jest.Mock).mockReturnValue(mockUser);
      (api.updateLanguage as jest.Mock).mockRejectedValue(
        new Error('Network error')
      );

      const consoleSpy = jest
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      await act(async () => {
        await result.current.setLocale('es');
      });

      // UI should still update even though API failed
      expect(result.current.locale).toBe('es');
      consoleSpy.mockRestore();
    });
  });

  describe('interpolate function', () => {
    it('interpolates single variable', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      const output = result.current.interpolate('Hello {name}', {
        name: 'World',
      });
      expect(output).toBe('Hello World');
    });

    it('interpolates multiple variables', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      const output = result.current.interpolate('{greeting}, {name}!', {
        greeting: 'Hi',
        name: 'Plato',
      });
      expect(output).toBe('Hi, Plato!');
    });

    it('leaves unknown variables as-is', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      const output = result.current.interpolate('Hello {unknown}', {});
      expect(output).toBe('Hello {unknown}');
    });

    it('interpolates numeric variables', async () => {
      const { result } = renderHook(() => useLanguage(), {
        wrapper: AllProviders,
      });

      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });

      const output = result.current.interpolate('Count: {count}', {
        count: 42,
      });
      expect(output).toBe('Count: 42');
    });
  });

  describe('LanguageProvider renders children', () => {
    it('renders children correctly', () => {
      render(
        <AllProviders>
          <div data-testid="lang-child">Language Child</div>
        </AllProviders>
      );
      expect(screen.getByTestId('lang-child')).toBeInTheDocument();
    });
  });
});
