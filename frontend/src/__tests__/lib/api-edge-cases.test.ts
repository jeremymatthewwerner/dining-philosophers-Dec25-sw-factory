/**
 * Edge case tests for api.ts - covers error paths, boundary conditions,
 * and authentication edge cases not covered in the main api.test.ts.
 *
 * Tests cover:
 * - 401 redirect behavior (clears auth, redirects to /login)
 * - Request timeout error message
 * - External signal (AbortSignal) cancellation vs timeout distinction
 * - setAccessToken with null clears localStorage
 * - getStoredUser with invalid JSON returns null
 * - getCurrentUser clears auth on error
 * - updateLanguage stores updated user
 * - updateProfile stores updated user
 * - changePassword API call format
 * - submitFeedback function (unauthenticated POST)
 * - submitFeedback network failure with user-friendly message
 * - Admin API: updateUserSpendLimit call format
 * - Admin API: getAdminUsers
 * - Admin API: deleteUser
 */

let api: typeof import('@/lib/api');

beforeEach(async () => {
  jest.clearAllMocks();
  localStorage.clear();
  (global.fetch as jest.Mock).mockReset();
  (localStorage.getItem as jest.Mock).mockReturnValue(null);
  // Reset module to clear internal accessToken state
  jest.resetModules();
  api = await import('@/lib/api');
});

describe('API Client Edge Cases', () => {
  describe('Token Management', () => {
    it('setAccessToken with null removes token from localStorage', async () => {
      // First set a token
      api.setAccessToken('my-token');
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'access_token',
        'my-token'
      );

      // Now clear it
      api.setAccessToken(null);
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });

    it('getStoredUser returns null when localStorage has invalid JSON', async () => {
      (localStorage.getItem as jest.Mock).mockImplementation((key: string) => {
        if (key === 'user') return 'invalid-json{{{';
        return null;
      });

      const user = api.getStoredUser();
      expect(user).toBeNull();
    });

    it('getStoredUser returns null when no user in localStorage', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue(null);

      const user = api.getStoredUser();
      expect(user).toBeNull();
    });

    it('clearAuth removes both token and user from localStorage', () => {
      api.clearAuth();
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorage.removeItem).toHaveBeenCalledWith('user');
    });
  });

  describe('401 Unauthorized Handling', () => {
    it('clears auth when 401 response is received', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('expired-token');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Token expired' }),
      });

      // Mock window.location
      const originalLocation = window.location;
      // @ts-expect-error - deleting read-only property for test
      delete window.location;
      window.location = { href: '', pathname: '/conversations' } as Location;

      await expect(api.getConversations()).rejects.toThrow('Token expired');

      // Auth should be cleared
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');

      // Restore
      window.location = originalLocation;
    });

    it('does not redirect if already on login page when 401 occurs', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('expired-token');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Not authenticated' }),
      });

      const originalLocation = window.location;
      // @ts-expect-error - deleting read-only property for test
      delete window.location;
      const mockLocation = { href: '/login', pathname: '/login' } as Location;
      window.location = mockLocation;

      await expect(api.getConversations()).rejects.toThrow('Not authenticated');

      // Should not redirect if already on login page
      expect(mockLocation.href).toBe('/login');

      window.location = originalLocation;
    });
  });

  describe('Request Timeout and Cancellation', () => {
    beforeEach(() => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
    });

    it('throws timeout error when request takes too long', async () => {
      jest.useFakeTimers();
      try {
        // Make fetch respond as if aborted (simulates timeout abort)
        (global.fetch as jest.Mock).mockImplementation(() => {
          // Simulate an abort error that would occur after timeout
          const error = new DOMException(
            'The operation was aborted.',
            'AbortError'
          );
          return Promise.reject(error);
        });

        await expect(api.getConversations()).rejects.toThrow(
          /timeout|aborted/i
        );
      } finally {
        jest.useRealTimers();
      }
    });

    it('throws "Request cancelled" when aborted via external signal', async () => {
      const controller = new AbortController();
      // Pre-abort the signal so externalSignal.aborted is true
      controller.abort();

      // Simulate fetch throwing AbortError (which happens when signal is aborted)
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new DOMException('The operation was aborted.', 'AbortError')
      );

      // When externalSignal.aborted is true, fetchWithAuth throws 'Request cancelled'
      // (not the generic timeout message)
      await expect(
        api.suggestThinkers('philosophy', 3, [], 'en', controller.signal)
      ).rejects.toThrow('Request cancelled');
    });
  });

  describe('Auth API - Additional Coverage', () => {
    it('getCurrentUser clears auth and returns null on API error', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Invalid token' }),
      });

      const user = await api.getCurrentUser();

      expect(user).toBeNull();
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });

    it('updateLanguage stores updated user in localStorage', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      const updatedUser = {
        id: 'user-123',
        username: 'testuser',
        display_name: 'Test User',
        is_admin: false,
        total_spend: 0,
        spend_limit: 5.0,
        language_preference: 'fr',
        created_at: '2024-01-15T10:00:00Z',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(updatedUser),
      });

      const result = await api.updateLanguage('fr');

      expect(result).toEqual(updatedUser);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/language'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ language_preference: 'fr' }),
        })
      );
      // User should be stored in localStorage
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(updatedUser)
      );
    });

    it('updateProfile stores updated user in localStorage', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      const updatedUser = {
        id: 'user-123',
        username: 'testuser',
        display_name: 'New Display Name',
        is_admin: false,
        total_spend: 0,
        spend_limit: 5.0,
        language_preference: 'en',
        created_at: '2024-01-15T10:00:00Z',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(updatedUser),
      });

      const result = await api.updateProfile('New Display Name');

      expect(result).toEqual(updatedUser);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/profile'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ display_name: 'New Display Name' }),
        })
      );
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(updatedUser)
      );
    });

    it('changePassword sends correct request format', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ message: 'Password changed successfully' }),
      });

      const result = await api.changePassword('currentpass123', 'newpass456');

      expect(result.message).toBe('Password changed successfully');
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/change-password'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            current_password: 'currentpass123',
            new_password: 'newpass456',
          }),
        })
      );
    });

    it('logout still clears auth even when API call fails', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ detail: 'Server error' }),
      });

      // logout() has try { await fetchWithAuth() } finally { clearAuth() }
      // So even on failure, clearAuth() is called in the finally block.
      // But the error from fetchWithAuth still propagates out.
      await expect(api.logout()).rejects.toThrow('Server error');

      // Auth should still be cleared via the finally block
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorage.removeItem).toHaveBeenCalledWith('user');
    });
  });

  describe('Admin API', () => {
    beforeEach(() => {
      (localStorage.getItem as jest.Mock).mockReturnValue('admin-jwt-token');
    });

    it('getAdminUsers fetches from admin users endpoint', async () => {
      const mockUsers = [
        {
          id: 'user-1',
          username: 'user1',
          display_name: 'User One',
          is_admin: false,
          total_spend: 0.5,
          spend_limit: 5.0,
          language_preference: 'en',
          conversation_count: 3,
          created_at: '2024-01-01T00:00:00Z',
        },
      ];
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUsers),
      });

      const users = await api.getAdminUsers();

      expect(users).toEqual(mockUsers);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer admin-jwt-token',
          }),
        })
      );
    });

    it('deleteUser sends DELETE request to admin endpoint', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ message: 'User deleted' }),
      });

      const result = await api.deleteUser('user-to-delete');

      expect(result).toEqual({ message: 'User deleted' });
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users/user-to-delete'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('updateUserSpendLimit sends PATCH with correct body', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            user_id: 'user-123',
            spend_limit: 10.0,
            message: 'Spend limit updated',
          }),
      });

      const result = await api.updateUserSpendLimit('user-123', 10.0);

      expect(result.spend_limit).toBe(10.0);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users/user-123/spend-limit'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ spend_limit: 10.0 }),
        })
      );
    });
  });

  describe('submitFeedback - Unauthenticated API', () => {
    it('submits feedback successfully without authentication', async () => {
      const mockResponse = { id: 'feedback-123', message: 'Thank you!' };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await api.submitFeedback({
        feedback_type: 'bug',
        message: 'Found a bug in the app',
        email: 'user@example.com',
        name: 'Test User',
      });

      expect(result).toEqual(mockResponse);
      // Should NOT include Authorization header (no auth for feedback)
      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const options = fetchCall[1];
      expect(options.headers?.Authorization).toBeUndefined();
    });

    it('throws network error with user-friendly message on fetch failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new TypeError('Failed to fetch')
      );

      await expect(
        api.submitFeedback({
          feedback_type: 'bug',
          message: 'Feedback that fails to send',
        })
      ).rejects.toThrow(/Unable to connect|internet connection/i);
    });

    it('throws API error when server returns non-ok response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 429,
        json: () =>
          Promise.resolve({ detail: 'Too many feedback submissions' }),
      });

      await expect(
        api.submitFeedback({
          feedback_type: 'other',
          message: 'Rate limited feedback submission',
        })
      ).rejects.toThrow('Too many feedback submissions');
    });

    it('throws generic error when server returns error without parseable body', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Parse error')),
      });

      await expect(
        api.submitFeedback({
          feedback_type: 'bug',
          message: 'Feedback with unparseable error response',
        })
      ).rejects.toThrow('Unknown error');
    });

    it('submits feedback with all optional fields', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 'fb-123', message: 'Received' }),
      });

      await api.submitFeedback({
        feedback_type: 'feature',
        message: 'Please add dark mode',
        email: 'user@example.com',
        name: 'John Doe',
        username: 'johndoe',
        user_agent: 'Mozilla/5.0',
        screenshot_data: 'base64data...',
        screenshot_filename: 'screenshot.png',
      });

      const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
      const body = JSON.parse(fetchCall[1].body);
      expect(body.feedback_type).toBe('feature');
      expect(body.username).toBe('johndoe');
      expect(body.screenshot_filename).toBe('screenshot.png');
    });
  });

  describe('Error Handling - Additional', () => {
    beforeEach(() => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
    });

    it('throws generic error for non-abort non-detail error', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Generic network error')
      );

      await expect(api.getConversations()).rejects.toThrow(
        'Generic network error'
      );
    });
  });
});
