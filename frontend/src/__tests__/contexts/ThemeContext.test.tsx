/**
 * Tests for ThemeContext.tsx
 *
 * Covers:
 * - ThemeProvider renders children
 * - useTheme throws when used outside provider
 * - Default theme is 'system'
 * - setTheme updates theme state
 * - setTheme persists to localStorage
 * - setTheme applies class to document root
 * - resolvedTheme returns system theme when theme is 'system'
 * - resolvedTheme returns the set theme for 'light' and 'dark'
 * - System theme change listener
 * - getSavedTheme reads from localStorage
 * - applyThemeToDOM removes existing classes
 */

import React from 'react';
import { render, renderHook, act, screen } from '@testing-library/react';
import { ThemeProvider, useTheme } from '@/contexts/ThemeContext';

// Helper to wrap with ThemeProvider
function wrapper({ children }: { children: React.ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

describe('ThemeContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // localStorage is a jest.fn() mock - default returns undefined
    (localStorage.getItem as jest.Mock).mockReturnValue(null);
    // Reset document root classes
    document.documentElement.classList.remove('light', 'dark');
  });

  afterEach(() => {
    document.documentElement.classList.remove('light', 'dark');
  });

  describe('useTheme outside provider', () => {
    it('throws an error when used outside ThemeProvider', () => {
      // Suppress error output
      const consoleSpy = jest
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      expect(() => {
        renderHook(() => useTheme());
      }).toThrow('useTheme must be used within a ThemeProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('default state', () => {
    it('provides default theme of system', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });
      expect(result.current.theme).toBe('system');
    });

    it('provides resolvedTheme based on system preference', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });
      // Default matchMedia returns false for dark, so system = light
      expect(result.current.resolvedTheme).toBe('light');
    });
  });

  describe('setTheme', () => {
    it('updates theme to light', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('light');
      });

      expect(result.current.theme).toBe('light');
    });

    it('updates theme to dark', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('dark');
      });

      expect(result.current.theme).toBe('dark');
    });

    it('persists theme to localStorage', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('dark');
      });

      expect(localStorage.setItem).toHaveBeenCalledWith(
        'theme-preference',
        'dark'
      );
    });

    it('applies dark class to document root when dark theme is set', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('dark');
      });

      expect(document.documentElement.classList.contains('dark')).toBe(true);
      expect(document.documentElement.classList.contains('light')).toBe(false);
    });

    it('applies light class to document root when light theme is set', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('light');
      });

      expect(document.documentElement.classList.contains('light')).toBe(true);
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });

    it('removes theme classes from root when system theme is set', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      // First set dark
      act(() => {
        result.current.setTheme('dark');
      });
      expect(document.documentElement.classList.contains('dark')).toBe(true);

      // Then set system
      act(() => {
        result.current.setTheme('system');
      });

      expect(document.documentElement.classList.contains('dark')).toBe(false);
      expect(document.documentElement.classList.contains('light')).toBe(false);
    });
  });

  describe('resolvedTheme', () => {
    it('returns light when theme is light', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('light');
      });

      expect(result.current.resolvedTheme).toBe('light');
    });

    it('returns dark when theme is dark', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('dark');
      });

      expect(result.current.resolvedTheme).toBe('dark');
    });

    it('returns dark when theme is system and system prefers dark', () => {
      // Override matchMedia to return dark preference
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation((query: string) => ({
          matches: query === '(prefers-color-scheme: dark)' ? true : false,
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        })),
      });

      const { result } = renderHook(() => useTheme(), { wrapper });
      // theme = 'system', system prefers dark
      expect(result.current.resolvedTheme).toBe('dark');
    });
  });

  describe('localStorage persistence', () => {
    it('reads saved theme from localStorage on mount', () => {
      // Mock localStorage to return 'dark' - ThemeProvider reads it on init
      (localStorage.getItem as jest.Mock).mockReturnValue('dark');

      // Use renderHook with a custom wrapper that creates a fresh ThemeProvider
      const { result } = renderHook(() => useTheme(), { wrapper });
      // The theme should be 'dark' since localStorage returns 'dark'
      expect(result.current.theme).toBe('dark');
    });

    it('saves theme preference to localStorage when setTheme is called', () => {
      const { result } = renderHook(() => useTheme(), { wrapper });

      act(() => {
        result.current.setTheme('light');
      });

      expect(localStorage.setItem).toHaveBeenCalledWith(
        'theme-preference',
        'light'
      );
    });

    it('ignores invalid localStorage value and defaults to system', () => {
      // Return an invalid value from localStorage
      (localStorage.getItem as jest.Mock).mockReturnValue('invalid-theme');

      const { result } = renderHook(() => useTheme(), { wrapper });
      // getSavedTheme filters out invalid values, returns 'system'
      expect(result.current.theme).toBe('system');
    });
  });

  describe('ThemeProvider renders children', () => {
    it('renders children correctly', () => {
      render(
        <ThemeProvider>
          <div data-testid="child">Test Child</div>
        </ThemeProvider>
      );
      expect(screen.getByTestId('child')).toBeInTheDocument();
    });
  });
});
