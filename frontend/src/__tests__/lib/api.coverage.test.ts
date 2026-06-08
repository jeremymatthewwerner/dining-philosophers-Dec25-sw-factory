import { createMockFetchResponse, setupAuthToken } from '@/test-utils';

// Isolate tests with jest.resetModules so the module-level accessToken cache
// does not leak between cases.
let api: typeof import('@/lib/api');

beforeEach(async () => {
  jest.clearAllMocks();
  localStorage.clear();
  (global.fetch as jest.Mock).mockReset();
  (localStorage.getItem as jest.Mock).mockReturnValue(null);
  jest.resetModules();
  api = await import('@/lib/api');
});

describe('api.ts coverage sprint', () => {
  describe('Token & user storage helpers', () => {
    it('setAccessToken(null) removes the token from localStorage', () => {
      api.setAccessToken(null);
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });

    it('setAccessToken(token) writes the token to localStorage', () => {
      api.setAccessToken('abc');
      expect(localStorage.setItem).toHaveBeenCalledWith('access_token', 'abc');
    });

    it('setStoredUser(null) removes the user from localStorage', () => {
      api.setStoredUser(null);
      expect(localStorage.removeItem).toHaveBeenCalledWith('user');
    });

    it('getStoredUser returns the parsed user when JSON is valid', () => {
      const user = { id: 'u1', username: 'alice' };
      (localStorage.getItem as jest.Mock).mockReturnValue(JSON.stringify(user));
      expect(api.getStoredUser()).toEqual(user);
    });

    it('getStoredUser returns null when nothing is stored', () => {
      (localStorage.getItem as jest.Mock).mockReturnValue(null);
      expect(api.getStoredUser()).toBeNull();
    });

    it('getStoredUser returns null when the stored value is not valid JSON', () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('{not-json');
      expect(api.getStoredUser()).toBeNull();
    });

    it('getAccessToken caches the token after the first read', () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('cached-token');
      expect(api.getAccessToken()).toBe('cached-token');
      // Second call should hit the in-memory cache, not localStorage again.
      (localStorage.getItem as jest.Mock).mockClear();
      expect(api.getAccessToken()).toBe('cached-token');
      expect(localStorage.getItem).not.toHaveBeenCalled();
    });
  });

  describe('Profile / language / password mutations', () => {
    beforeEach(() => setupAuthToken());

    it('updateLanguage PATCHes the preference and stores the updated user', async () => {
      const updated = {
        id: 'u1',
        username: 'alice',
        language_preference: 'fr',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(updated)
      );

      const result = await api.updateLanguage('fr');

      expect(result).toEqual(updated);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/language'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ language_preference: 'fr' }),
        })
      );
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(updated)
      );
    });

    it('updateProfile PATCHes the display name and stores the updated user', async () => {
      const updated = { id: 'u1', username: 'alice', display_name: 'Alice B' };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(updated)
      );

      const result = await api.updateProfile('Alice B');

      expect(result).toEqual(updated);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/profile'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ display_name: 'Alice B' }),
        })
      );
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(updated)
      );
    });

    it('changePassword POSTs current and new passwords', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ message: 'Password changed' })
      );

      const result = await api.changePassword('oldpw', 'newpw');

      expect(result).toEqual({ message: 'Password changed' });
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/change-password'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            current_password: 'oldpw',
            new_password: 'newpw',
          }),
        })
      );
    });
  });

  describe('Admin API', () => {
    beforeEach(() => setupAuthToken());

    it('getAdminUsers GETs the admin user list', async () => {
      const users = [{ id: 'u1', username: 'alice', total_spend: 1.5 }];
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(users)
      );

      const result = await api.getAdminUsers();

      expect(result).toEqual(users);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer jwt-token-123',
          }),
        })
      );
    });

    it('deleteUser DELETEs the given user', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ message: 'User deleted' })
      );

      const result = await api.deleteUser('u1');

      expect(result).toEqual({ message: 'User deleted' });
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users/u1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('updateUserSpendLimit PATCHes the spend limit', async () => {
      const resp = {
        user_id: 'u1',
        spend_limit: 25,
        message: 'Updated',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(resp)
      );

      const result = await api.updateUserSpendLimit('u1', 25);

      expect(result).toEqual(resp);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users/u1/spend-limit'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ spend_limit: 25 }),
        })
      );
    });
  });

  describe('submitFeedback', () => {
    const feedback = {
      feedback_type: 'bug' as const,
      message: 'Something broke',
    };

    it('POSTs feedback and returns the created record', async () => {
      const created = { id: 'fb-1', message: 'Thanks!' };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(created)
      );

      const result = await api.submitFeedback(feedback);

      expect(result).toEqual(created);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/feedback'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(feedback),
        })
      );
    });

    it('throws the server-provided detail on a non-ok response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ detail: 'Rate limited' }, false, 429)
      );

      await expect(api.submitFeedback(feedback)).rejects.toThrow(
        'Rate limited'
      );
    });

    it('falls back to the HTTP status when the error body has no detail', async () => {
      // json() resolves to an object without a `detail` field, so the
      // `HTTP <status>` fallback is used.
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({}, false, 503)
      );

      await expect(api.submitFeedback(feedback)).rejects.toThrow('HTTP 503');
    });

    it('maps a "Failed to fetch" network error to a friendly message', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new TypeError('Failed to fetch')
      );

      await expect(api.submitFeedback(feedback)).rejects.toThrow(
        /Unable to connect to the server/
      );
    });

    it('re-throws unexpected errors unchanged', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('boom'));

      await expect(api.submitFeedback(feedback)).rejects.toThrow('boom');
    });
  });

  describe('fetchWithAuth 401 handling', () => {
    // The default jsdom URL is "/", which does NOT include "/login", so a 401
    // exercises the clear-auth + redirect branch. The companion case where the
    // user is already on /login (redirect skipped) lives in
    // api.login-401.coverage.test.ts, which pins the jsdom URL to /login.
    it('clears auth (and attempts a redirect) on a 401 from a protected page', async () => {
      setupAuthToken();
      expect(window.location.pathname.includes('/login')).toBe(false);
      // Assigning window.location.href makes jsdom emit a "Not implemented:
      // navigation" jsdomError; silence it so it doesn't clutter the run.
      const errSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ detail: 'Token expired' }, false, 401)
      );

      await expect(api.getConversations()).rejects.toThrow('Token expired');

      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorage.removeItem).toHaveBeenCalledWith('user');
      errSpy.mockRestore();
    });
  });

  describe('getCurrentUser failure path', () => {
    it('clears auth and returns null when the /me request fails', async () => {
      setupAuthToken();
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ detail: 'nope' }, false, 500)
      );

      const user = await api.getCurrentUser();

      expect(user).toBeNull();
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });
  });

  describe('Timeout and cancellation in fetchWithAuth', () => {
    it('converts an AbortError with no external signal into a timeout error', async () => {
      setupAuthToken();
      const abortErr = new Error('aborted');
      abortErr.name = 'AbortError';
      (global.fetch as jest.Mock).mockRejectedValueOnce(abortErr);

      // suggestThinkers passes an explicit 30000ms timeout to fetchWithAuth.
      await expect(api.suggestThinkers('topic')).rejects.toThrow(
        'Request timeout after 30000ms'
      );
    });

    it('reports a cancellation when the external AbortSignal is aborted', async () => {
      setupAuthToken();
      const controller = new AbortController();
      controller.abort(); // external signal aborted -> cancellation, not timeout

      const abortErr = new Error('aborted');
      abortErr.name = 'AbortError';
      (global.fetch as jest.Mock).mockRejectedValueOnce(abortErr);

      await expect(
        api.suggestThinkers('topic', 3, [], 'en', controller.signal)
      ).rejects.toThrow('Request cancelled');
    });

    it('wires the external AbortSignal through to suggestThinkers', async () => {
      setupAuthToken();
      const controller = new AbortController();
      const addSpy = jest.spyOn(controller.signal, 'addEventListener');
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse([])
      );

      await api.suggestThinkers('topic', 3, [], 'en', controller.signal);

      expect(addSpy).toHaveBeenCalledWith('abort', expect.any(Function));
    });
  });
});
