/**
 * @jest-environment jsdom
 * @jest-environment-options {"url": "https://localhost/login"}
 *
 * Pins the jsdom URL to /login so we can exercise the branch in fetchWithAuth
 * where a 401 is received while the user is already on the login page and the
 * automatic redirect is therefore skipped (only clearAuth should run).
 */
import { createMockFetchResponse, setupAuthToken } from '@/test-utils';

let api: typeof import('@/lib/api');

beforeEach(async () => {
  jest.clearAllMocks();
  localStorage.clear();
  (global.fetch as jest.Mock).mockReset();
  (localStorage.getItem as jest.Mock).mockReturnValue(null);
  jest.resetModules();
  api = await import('@/lib/api');
});

describe('fetchWithAuth 401 while already on /login', () => {
  it('clears auth but does not navigate away from /login', async () => {
    setupAuthToken();
    // Sanity check: the pinned URL really is /login.
    expect(window.location.pathname).toBe('/login');
    const hrefBefore = window.location.href;

    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ detail: 'Bad credentials' }, false, 401)
    );

    await expect(api.getConversations()).rejects.toThrow('Bad credentials');

    expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    // No navigation: still on the login page.
    expect(window.location.href).toBe(hrefBefore);
    expect(window.location.pathname).toBe('/login');
  });
});
