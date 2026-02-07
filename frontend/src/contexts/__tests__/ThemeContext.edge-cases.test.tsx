/**
 * Edge case tests for ThemeContext
 *
 * Focus: Testing error conditions, invalid inputs, and boundary cases for theme management.
 * Saturday QA focus: Edge case analysis - test error paths and boundary conditions.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { ThemeProvider, useTheme } from '../ThemeContext';

describe('ThemeContext Edge Cases', () => {
  let mockMatchMedia: jest.Mock;
  let originalMatchMedia: typeof window.matchMedia;
  let localStorageSpy: jest.SpyInstance;

  beforeEach(() => {
    // Mock matchMedia
    mockMatchMedia = jest.fn().mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));
    originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: mockMatchMedia,
    });

    // Spy on localStorage
    localStorageSpy = jest.spyOn(Storage.prototype, 'getItem');
    jest.spyOn(Storage.prototype, 'setItem');
    jest.spyOn(Storage.prototype, 'removeItem');

    // Clear localStorage
    localStorage.clear();
  });

  afterEach(() => {
    // Restore original matchMedia
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: originalMatchMedia,
    });
    localStorageSpy.mockRestore();
    jest.restoreAllMocks();
  });

  describe('Invalid localStorage values', () => {
    it('should fallback to system theme when localStorage contains invalid value', () => {
      // Set invalid theme value in localStorage
      localStorage.setItem('theme-preference', 'invalid-theme-value');

      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Should fallback to 'system'
      expect(result.current.theme).toBe('system');
    });

    it('should handle empty string in localStorage', () => {
      localStorage.setItem('theme-preference', '');

      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Should fallback to 'system'
      expect(result.current.theme).toBe('system');
    });

    it('should handle malformed JSON in localStorage', () => {
      localStorage.setItem('theme-preference', '{"theme": "dark"}');

      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Should fallback to 'system' (not valid theme mode string)
      expect(result.current.theme).toBe('system');
    });

    it('should handle null value in localStorage', () => {
      // @ts-expect-error - Testing invalid input
      localStorageSpy.mockReturnValue(null);

      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      expect(result.current.theme).toBe('system');
    });

    it('should handle localStorage getItem throwing error', () => {
      localStorageSpy.mockImplementation(() => {
        throw new Error('localStorage access denied');
      });

      // Should not crash and fallback to system
      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      expect(result.current.theme).toBe('system');
    });
  });

  describe('System theme changes', () => {
    it('should update resolved theme when system preference changes', async () => {
      // Start with system theme preference
      let mediaQueryCallback: ((e: MediaQueryListEvent) => void) | null = null;

      mockMatchMedia.mockImplementation((query) => {
        const mql = {
          matches: false, // Start with light
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn((_, callback) => {
            mediaQueryCallback = callback;
          }),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        };
        return mql;
      });

      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Initially should be light (system default)
      expect(result.current.theme).toBe('system');
      expect(result.current.resolvedTheme).toBe('light');

      // Simulate system theme change to dark
      act(() => {
        mockMatchMedia.mockImplementation((query) => ({
          matches: true, // Now dark
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        }));

        // Trigger the callback
        if (mediaQueryCallback) {
          mediaQueryCallback({
            matches: true,
            media: '(prefers-color-scheme: dark)',
          } as MediaQueryListEvent);
        }
      });

      await waitFor(() => {
        expect(result.current.resolvedTheme).toBe('dark');
      });
    });

    it('should not affect resolved theme when user has explicit preference', () => {
      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Set explicit dark theme
      act(() => {
        result.current.setTheme('dark');
      });

      expect(result.current.resolvedTheme).toBe('dark');

      // System theme change should not affect it
      mockMatchMedia.mockImplementation((query) => ({
        matches: false, // System prefers light
        media: query,
        onchange: null,
        addListener: jest.fn(),
        removeListener: jest.fn(),
        addEventListener: jest.fn(),
        removeEventListener: jest.fn(),
        dispatchEvent: jest.fn(),
      }));

      // Should still be dark (user preference overrides system)
      expect(result.current.resolvedTheme).toBe('dark');
    });
  });

  describe('Rapid theme changes', () => {
    it('should handle rapid consecutive theme changes', () => {
      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Rapidly change themes
      act(() => {
        result.current.setTheme('dark');
        result.current.setTheme('light');
        result.current.setTheme('system');
        result.current.setTheme('dark');
      });

      // Should end up with the last theme
      expect(result.current.theme).toBe('dark');
      expect(result.current.resolvedTheme).toBe('dark');
    });

    it('should handle setting same theme multiple times', () => {
      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      act(() => {
        result.current.setTheme('dark');
        result.current.setTheme('dark');
        result.current.setTheme('dark');
      });

      expect(result.current.theme).toBe('dark');
      expect(result.current.resolvedTheme).toBe('dark');
    });
  });

  describe('useTheme hook without provider', () => {
    it('should throw error when used outside ThemeProvider', () => {
      // Suppress console.error for this test
      const consoleError = jest.spyOn(console, 'error').mockImplementation();

      expect(() => {
        renderHook(() => useTheme());
      }).toThrow('useTheme must be used within a ThemeProvider');

      consoleError.mockRestore();
    });
  });

  describe('DOM manipulation edge cases', () => {
    it('should clean up classes when switching between all theme modes', () => {
      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Test class toggling through all states
      act(() => {
        result.current.setTheme('dark');
      });
      expect(document.documentElement.classList.contains('dark')).toBe(true);
      expect(document.documentElement.classList.contains('light')).toBe(false);

      act(() => {
        result.current.setTheme('light');
      });
      expect(document.documentElement.classList.contains('light')).toBe(true);
      expect(document.documentElement.classList.contains('dark')).toBe(false);

      act(() => {
        result.current.setTheme('system');
      });
      // System mode should not add any class
      expect(document.documentElement.classList.contains('light')).toBe(false);
      expect(document.documentElement.classList.contains('dark')).toBe(false);
    });
  });

  describe('localStorage persistence edge cases', () => {
    it('should handle localStorage setItem throwing QuotaExceededError', () => {
      // Create a fresh hook instance
      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Mock setItem to throw after component is mounted
      const originalSetItem = Storage.prototype.setItem;
      const setItemSpy = jest
        .spyOn(Storage.prototype, 'setItem')
        .mockImplementationOnce(function (key, value) {
          // Let the first call through for initialization
          originalSetItem.call(this, key, value);
        })
        .mockImplementationOnce(() => {
          throw new DOMException('QuotaExceededError');
        });

      // Should not crash even if localStorage fails
      expect(() => {
        act(() => {
          result.current.setTheme('dark');
        });
      }).not.toThrow();

      setItemSpy.mockRestore();
    });

    it('should handle localStorage being disabled/blocked', () => {
      // Mock getItem specifically to throw
      const getItemSpy = jest
        .spyOn(Storage.prototype, 'getItem')
        .mockImplementation(() => {
          throw new Error('localStorage is disabled');
        });

      // Should not crash and fallback to defaults
      const { result } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      expect(result.current.theme).toBe('system');

      getItemSpy.mockRestore();
    });
  });

  describe('Memory leak prevention', () => {
    it('should clean up media query listener on unmount', () => {
      // Clear localStorage for clean test
      localStorage.clear();

      const removeEventListenerSpy = jest.fn();
      const addEventListenerSpy = jest.fn();

      mockMatchMedia.mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: jest.fn(),
        removeListener: jest.fn(),
        addEventListener: addEventListenerSpy,
        removeEventListener: removeEventListenerSpy,
        dispatchEvent: jest.fn(),
      }));

      const { unmount } = renderHook(() => useTheme(), {
        wrapper: ThemeProvider,
      });

      // Verify addEventListener was called during mount
      expect(addEventListenerSpy).toHaveBeenCalledWith(
        'change',
        expect.any(Function)
      );

      // Unmount should call removeEventListener
      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'change',
        expect.any(Function)
      );
    });
  });
});
