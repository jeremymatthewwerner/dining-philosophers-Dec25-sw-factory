/**
 * Tests for AuthContext.tsx
 *
 * Covers:
 * - AuthProvider renders children
 * - useAuth throws when used outside provider
 * - Initial state: loading, then resolves to user or null
 * - login sets user
 * - register sets user
 * - logout clears user
 * - refreshUser updates user
 * - updateDisplayName updates user
 * - isAuthenticated reflects user state
 */

import React from 'react';
import {
  render,
  renderHook,
  act,
  screen,
  waitFor,
} from '@testing-library/react';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import * as api from '@/lib/api';

// Mock the api module
jest.mock('@/lib/api', () => ({
  getCurrentUser: jest.fn(),
  getStoredUser: jest.fn(),
  setStoredUser: jest.fn(),
  login: jest.fn(),
  register: jest.fn(),
  logout: jest.fn(),
  updateProfile: jest.fn(),
}));

const mockUser = {
  id: 'user-1',
  username: 'testuser',
  display_name: 'Test User',
  language_preference: 'en',
};

function wrapper({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe('AuthContext', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (api.getStoredUser as jest.Mock).mockReturnValue(null);
    (api.getCurrentUser as jest.Mock).mockResolvedValue(null);
  });

  describe('useAuth outside provider', () => {
    it('throws error when used outside AuthProvider', () => {
      const consoleSpy = jest
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      expect(() => {
        renderHook(() => useAuth());
      }).toThrow('useAuth must be used within an AuthProvider');

      consoleSpy.mockRestore();
    });
  });

  describe('initial loading state', () => {
    it('starts with isLoading true', () => {
      // Don't resolve getCurrentUser immediately
      (api.getCurrentUser as jest.Mock).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useAuth(), { wrapper });
      expect(result.current.isLoading).toBe(true);
    });

    it('sets isLoading to false after auth check resolves', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets user when getCurrentUser returns a user', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);
      (api.setStoredUser as jest.Mock).mockImplementation(() => {});

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets user to null when getCurrentUser returns null', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.user).toBeNull();
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('initializes from localStorage if stored user exists', async () => {
      (api.getStoredUser as jest.Mock).mockReturnValue(mockUser);
      (api.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);
      (api.setStoredUser as jest.Mock).mockImplementation(() => {});

      const { result } = renderHook(() => useAuth(), { wrapper });

      // Initially should have stored user
      expect(result.current.user).toEqual(mockUser);
    });
  });

  describe('isAuthenticated', () => {
    it('is false when user is null', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false);
      });
    });

    it('is true when user is set', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);
      (api.setStoredUser as jest.Mock).mockImplementation(() => {});

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });
    });
  });

  describe('login', () => {
    it('calls api.login and sets user', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);
      (api.login as jest.Mock).mockResolvedValue({
        access_token: 'token',
        user: mockUser,
      });

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.login('testuser', 'password123');
      });

      expect(api.login).toHaveBeenCalledWith('testuser', 'password123');
      expect(result.current.user).toEqual(mockUser);
    });

    it('propagates errors from api.login', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);
      (api.login as jest.Mock).mockRejectedValue(
        new Error('Invalid credentials')
      );

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await expect(
        act(async () => {
          await result.current.login('testuser', 'wrongpass');
        })
      ).rejects.toThrow('Invalid credentials');
    });
  });

  describe('register', () => {
    it('calls api.register and sets user', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);
      (api.register as jest.Mock).mockResolvedValue({
        access_token: 'token',
        user: mockUser,
      });

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.register('testuser', 'Test User', 'password123');
      });

      expect(api.register).toHaveBeenCalledWith(
        'testuser',
        'Test User',
        'password123',
        'en'
      );
      expect(result.current.user).toEqual(mockUser);
    });

    it('passes language preference to api.register', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);
      (api.register as jest.Mock).mockResolvedValue({
        access_token: 'token',
        user: mockUser,
      });

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.register(
          'testuser',
          'Test User',
          'password123',
          'es'
        );
      });

      expect(api.register).toHaveBeenCalledWith(
        'testuser',
        'Test User',
        'password123',
        'es'
      );
    });
  });

  describe('logout', () => {
    it('calls api.logout and clears user', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);
      (api.setStoredUser as jest.Mock).mockImplementation(() => {});
      (api.logout as jest.Mock).mockResolvedValue(undefined);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      await act(async () => {
        await result.current.logout();
      });

      expect(api.logout).toHaveBeenCalled();
      expect(result.current.user).toBeNull();
    });
  });

  describe('refreshUser', () => {
    it('calls getCurrentUser and updates user', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValueOnce(null);
      (api.getCurrentUser as jest.Mock).mockResolvedValueOnce({
        ...mockUser,
        display_name: 'Updated Name',
      });
      (api.setStoredUser as jest.Mock).mockImplementation(() => {});

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.refreshUser();
      });

      expect(result.current.user?.display_name).toBe('Updated Name');
    });

    it('does not update user if getCurrentUser returns null', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(null);

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      await act(async () => {
        await result.current.refreshUser();
      });

      expect(result.current.user).toBeNull();
    });
  });

  describe('updateDisplayName', () => {
    it('calls api.updateProfile and updates user', async () => {
      (api.getCurrentUser as jest.Mock).mockResolvedValue(mockUser);
      (api.setStoredUser as jest.Mock).mockImplementation(() => {});
      (api.updateProfile as jest.Mock).mockResolvedValue({
        ...mockUser,
        display_name: 'New Display Name',
      });

      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });

      await act(async () => {
        await result.current.updateDisplayName('New Display Name');
      });

      expect(api.updateProfile).toHaveBeenCalledWith('New Display Name');
      expect(result.current.user?.display_name).toBe('New Display Name');
    });
  });

  describe('AuthProvider renders children', () => {
    it('renders children correctly', async () => {
      render(
        <AuthProvider>
          <div data-testid="auth-child">Auth Child</div>
        </AuthProvider>
      );
      expect(screen.getByTestId('auth-child')).toBeInTheDocument();
    });
  });
});
