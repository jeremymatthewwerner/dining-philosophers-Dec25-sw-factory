/**
 * Edge case tests for the API client library (api.ts).
 *
 * Focus areas (Saturday QA - Apr 18, 2026):
 * - Request timeout handling (AbortError → timeout error)
 * - External abort signal handling (component unmount cancellation)
 * - 401 Unauthorized → clearAuth + redirect logic
 * - updateLanguage and updateProfile endpoints
 * - submitFeedback network error paths
 * - Admin API calls (getAdminUsers, deleteUser, updateUserSpendLimit)
 * - getCurrentUser error path (clears auth on failure)
 */

import { createMockFetchResponse, setupAuthToken } from '@/test-utils';

// Isolate each test with fresh module state
let api: typeof import('@/lib/api');

beforeEach(async () => {
  jest.clearAllMocks();
  localStorage.clear();
  (global.fetch as jest.Mock).mockReset();
  (localStorage.getItem as jest.Mock).mockReturnValue(null);
  jest.resetModules();
  api = await import('@/lib/api');
});

// ---------------------------------------------------------------------------
// Timeout and abort signal error paths
// ---------------------------------------------------------------------------

describe('fetchWithAuth: timeout and abort handling', () => {
  it('throws timeout error when request times out (AbortError, no external signal)', async () => {
    setupAuthToken();
    // Simulate AbortError without external signal
    const abortError = new Error('The operation was aborted.');
    abortError.name = 'AbortError';
    (global.fetch as jest.Mock).mockRejectedValueOnce(abortError);

    await expect(api.getConversations()).rejects.toThrow(/timeout/i);
  });

  it('throws cancellation error when aborted by external signal', async () => {
    setupAuthToken();
    const controller = new AbortController();
    const abortError = new Error('The operation was aborted.');
    abortError.name = 'AbortError';
    (global.fetch as jest.Mock).mockImplementationOnce(() => {
      controller.abort(); // abort before returning
      return Promise.reject(abortError);
    });

    await expect(
      api.suggestThinkers('philosophy', 3, [], 'en', controller.signal)
    ).rejects.toThrow(/cancelled|timeout/i);
  });

  it('propagates non-abort errors unchanged', async () => {
    setupAuthToken();
    const networkError = new Error('Network connection failed unexpectedly');
    (global.fetch as jest.Mock).mockRejectedValueOnce(networkError);

    await expect(api.getConversations()).rejects.toThrow(
      'Network connection failed unexpectedly'
    );
  });
});

// ---------------------------------------------------------------------------
// 401 Unauthorized handling
// ---------------------------------------------------------------------------

describe('fetchWithAuth: 401 Unauthorized handling', () => {
  it('clears auth token on 401 response', async () => {
    setupAuthToken();
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ detail: 'Unauthorized' }, false, 401)
    );

    await expect(api.getConversations()).rejects.toThrow('Unauthorized');

    // Token should be cleared
    expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    expect(localStorage.removeItem).toHaveBeenCalledWith('user');
  });

  it('throws error with detail message from 401 response', async () => {
    setupAuthToken();
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ detail: 'Token expired' }, false, 401)
    );

    await expect(api.getConversations()).rejects.toThrow('Token expired');
  });
});

// ---------------------------------------------------------------------------
// getCurrentUser error path
// ---------------------------------------------------------------------------

describe('getCurrentUser: error handling', () => {
  it('clears auth and returns null when fetch fails', async () => {
    setupAuthToken();
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ detail: 'Forbidden' }, false, 403)
    );

    const user = await api.getCurrentUser();

    expect(user).toBeNull();
    // clearAuth should have been called
    expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
  });

  it('returns null immediately when no token stored', async () => {
    (localStorage.getItem as jest.Mock).mockReturnValue(null);

    const user = await api.getCurrentUser();

    expect(user).toBeNull();
    expect(global.fetch).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// updateLanguage endpoint
// ---------------------------------------------------------------------------

describe('updateLanguage', () => {
  it('updates language preference and stores user', async () => {
    setupAuthToken();
    const mockUser = {
      id: 'user-123',
      username: 'testuser',
      display_name: 'Test User',
      is_admin: false,
      total_spend: 0,
      spend_limit: 5,
      language_preference: 'es',
      created_at: '2024-01-15T10:00:00Z',
    };
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse(mockUser)
    );

    const result = await api.updateLanguage('es');

    expect(result).toEqual(mockUser);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/language'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ language_preference: 'es' }),
      })
    );
    // User should be stored in localStorage
    expect(localStorage.setItem).toHaveBeenCalledWith(
      'user',
      JSON.stringify(mockUser)
    );
  });

  it('throws on failed language update', async () => {
    setupAuthToken();
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ detail: 'Invalid language' }, false, 422)
    );

    await expect(api.updateLanguage('xx')).rejects.toThrow('Invalid language');
  });
});

// ---------------------------------------------------------------------------
// updateProfile endpoint
// ---------------------------------------------------------------------------

describe('updateProfile', () => {
  it('updates display name and stores updated user', async () => {
    setupAuthToken();
    const mockUser = {
      id: 'user-123',
      username: 'testuser',
      display_name: 'New Display Name',
      is_admin: false,
      total_spend: 0,
      spend_limit: 5,
      language_preference: 'en',
      created_at: '2024-01-15T10:00:00Z',
    };
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse(mockUser)
    );

    const result = await api.updateProfile('New Display Name');

    expect(result).toEqual(mockUser);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/profile'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ display_name: 'New Display Name' }),
      })
    );
    expect(localStorage.setItem).toHaveBeenCalledWith(
      'user',
      JSON.stringify(mockUser)
    );
  });

  it('throws on failed profile update', async () => {
    setupAuthToken();
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ detail: 'Display name too long' }, false, 422)
    );

    await expect(api.updateProfile('A'.repeat(101))).rejects.toThrow(
      'Display name too long'
    );
  });
});

// ---------------------------------------------------------------------------
// Admin API calls
// ---------------------------------------------------------------------------

describe('Admin API', () => {
  beforeEach(() => {
    setupAuthToken();
  });

  it('getAdminUsers fetches all users', async () => {
    const mockUsers = [
      {
        id: 'user-1',
        username: 'admin',
        display_name: 'Admin',
        is_admin: true,
        total_spend: 1.5,
        spend_limit: 10,
        language_preference: 'en',
        conversation_count: 5,
        created_at: '2024-01-01T00:00:00Z',
      },
    ];
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse(mockUsers)
    );

    const users = await api.getAdminUsers();

    expect(users).toEqual(mockUsers);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/users'),
      expect.any(Object)
    );
  });

  it('deleteUser deletes a specific user', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ message: 'User deleted' })
    );

    const result = await api.deleteUser('user-456');

    expect(result).toEqual({ message: 'User deleted' });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/users/user-456'),
      expect.objectContaining({ method: 'DELETE' })
    );
  });

  it('updateUserSpendLimit updates spend limit for a user', async () => {
    const mockResponse = {
      user_id: 'user-789',
      spend_limit: 25.0,
      message: 'Spend limit updated',
    };
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse(mockResponse)
    );

    const result = await api.updateUserSpendLimit('user-789', 25.0);

    expect(result).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/admin/users/user-789/spend-limit'),
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ spend_limit: 25.0 }),
      })
    );
  });

  it('throws on admin endpoint error', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ detail: 'Admin access required' }, false, 403)
    );

    await expect(api.getAdminUsers()).rejects.toThrow('Admin access required');
  });
});

// ---------------------------------------------------------------------------
// submitFeedback: network error paths
// ---------------------------------------------------------------------------

describe('submitFeedback: error handling', () => {
  it('converts network "Failed to fetch" to user-friendly message', async () => {
    const networkError = new TypeError('Failed to fetch');
    (global.fetch as jest.Mock).mockRejectedValueOnce(networkError);

    await expect(
      api.submitFeedback({
        feedback_type: 'bug',
        message: 'Test feedback',
      })
    ).rejects.toThrow(/unable to connect|internet connection/i);
  });

  it('throws API error detail from non-ok response', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse({ detail: 'Feedback too long' }, false, 422)
    );

    await expect(
      api.submitFeedback({
        feedback_type: 'bug',
        message: 'Too long feedback',
      })
    ).rejects.toThrow('Feedback too long');
  });

  it('throws generic HTTP error when detail missing from error response', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error('Parse error')),
    });

    await expect(
      api.submitFeedback({
        feedback_type: 'other',
        message: 'Test feedback',
      })
    ).rejects.toThrow('Unknown error');
  });

  it('succeeds and returns response on valid submission', async () => {
    const mockResponse = {
      id: 'feedback-123',
      message: 'Thank you for your feedback!',
    };
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await api.submitFeedback({
      feedback_type: 'feature',
      message: 'Great idea for new feature',
    });

    expect(result).toEqual(mockResponse);
  });

  it('passes optional fields to the submission', async () => {
    const mockResponse = { id: 'fb-456', message: 'Thank you!' };
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve(mockResponse),
    });

    await api.submitFeedback({
      feedback_type: 'bug',
      message: 'Bug with details',
      email: 'user@example.com',
      name: 'Test User',
      username: 'testuser',
    });

    const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
    const body = JSON.parse(fetchCall[1].body);
    expect(body.email).toBe('user@example.com');
    expect(body.name).toBe('Test User');
    expect(body.username).toBe('testuser');
  });
});

// ---------------------------------------------------------------------------
// getStoredUser: boundary conditions
// ---------------------------------------------------------------------------

describe('getStoredUser', () => {
  it('returns null when no user stored', () => {
    (localStorage.getItem as jest.Mock).mockReturnValue(null);
    const user = api.getStoredUser();
    expect(user).toBeNull();
  });

  it('returns null when stored JSON is invalid', () => {
    (localStorage.getItem as jest.Mock).mockReturnValue('not-valid-json{{{');
    const user = api.getStoredUser();
    expect(user).toBeNull();
  });

  it('returns parsed user when valid JSON stored', () => {
    const storedUser = {
      id: 'user-1',
      username: 'test',
      is_admin: false,
      total_spend: 0,
    };
    (localStorage.getItem as jest.Mock).mockReturnValue(
      JSON.stringify(storedUser)
    );
    const user = api.getStoredUser();
    expect(user).toEqual(storedUser);
  });
});

// ---------------------------------------------------------------------------
// changePassword endpoint
// ---------------------------------------------------------------------------

describe('changePassword', () => {
  it('sends current and new password to the endpoint', async () => {
    setupAuthToken();
    const mockResponse = { message: 'Password changed successfully' };
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse(mockResponse)
    );

    const result = await api.changePassword('oldpass', 'newpass123');

    expect(result).toEqual(mockResponse);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/auth/change-password'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          current_password: 'oldpass',
          new_password: 'newpass123',
        }),
      })
    );
  });

  it('throws on wrong current password', async () => {
    setupAuthToken();
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse(
        { detail: 'Incorrect current password' },
        false,
        400
      )
    );

    await expect(api.changePassword('wrongpass', 'newpass123')).rejects.toThrow(
      'Incorrect current password'
    );
  });
});

// ---------------------------------------------------------------------------
// suggestThinkers with exclude and language options
// ---------------------------------------------------------------------------

describe('suggestThinkers: edge cases', () => {
  beforeEach(() => {
    setupAuthToken();
  });

  it('sends exclude list and language correctly', async () => {
    const mockSuggestions = [
      { name: 'Aristotle', reason: 'Great', profile: {} },
    ];
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse(mockSuggestions)
    );

    await api.suggestThinkers('philosophy', 2, ['Socrates', 'Plato'], 'de');

    const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
    const body = JSON.parse(fetchCall[1].body);
    expect(body.exclude).toEqual(['Socrates', 'Plato']);
    expect(body.language).toBe('de');
    expect(body.count).toBe(2);
  });

  it('uses default values when not specified', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createMockFetchResponse([])
    );

    await api.suggestThinkers('science');

    const fetchCall = (global.fetch as jest.Mock).mock.calls[0];
    const body = JSON.parse(fetchCall[1].body);
    expect(body.count).toBe(3);
    expect(body.exclude).toEqual([]);
    expect(body.language).toBe('en');
  });
});
