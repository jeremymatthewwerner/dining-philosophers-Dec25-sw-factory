import { createMockFetchResponse, setupAuthToken } from '@/test-utils';

// Isolate tests with jest.resetModules
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

describe('API Client', () => {
  describe('Auth API', () => {
    it('registers a user and stores token', async () => {
      const mockResponse = {
        access_token: 'jwt-token-123',
        user: {
          id: 'user-123',
          username: 'testuser',
          display_name: 'Test User',
          is_admin: false,
          total_spend: 0,
          created_at: '2024-01-15T10:00:00Z',
        },
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockResponse)
      );

      const response = await api.register(
        'testuser',
        'Test User',
        'password123'
      );

      expect(response).toEqual(mockResponse);
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'access_token',
        'jwt-token-123'
      );
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(mockResponse.user)
      );
    });

    it('logs in a user and stores token', async () => {
      const mockResponse = {
        access_token: 'jwt-token-456',
        user: {
          id: 'user-123',
          username: 'testuser',
          is_admin: false,
          total_spend: 0.5,
          created_at: '2024-01-15T10:00:00Z',
        },
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockResponse)
      );

      const response = await api.login('testuser', 'password123');

      expect(response).toEqual(mockResponse);
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'access_token',
        'jwt-token-456'
      );
    });

    it('logs out and clears auth data', async () => {
      setupAuthToken();
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ message: 'Logged out' })
      );

      await api.logout();

      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
      expect(localStorage.removeItem).toHaveBeenCalledWith('user');
    });

    it('gets current user with valid token', async () => {
      const mockUser = {
        id: 'user-123',
        username: 'testuser',
        is_admin: false,
        total_spend: 0,
        created_at: '2024-01-15T10:00:00Z',
      };
      setupAuthToken();
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockUser)
      );

      const user = await api.getCurrentUser();

      expect(user).toEqual(mockUser);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/me'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer jwt-token-123',
          }),
        })
      );
    });

    it('returns null when no token exists', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue(null);

      const user = await api.getCurrentUser();

      expect(user).toBeNull();
      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('Session API', () => {
    it('gets session with valid token', async () => {
      const mockSession = {
        id: 'session-123',
        created_at: '2024-01-15T10:00:00Z',
      };
      setupAuthToken();
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockSession)
      );

      const session = await api.getSession();

      expect(session).toEqual(mockSession);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/sessions/me'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer jwt-token-123',
          }),
        })
      );
    });

    it('returns null when no token exists', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue(null);

      const session = await api.getSession();

      expect(session).toBeNull();
      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('returns null when session fetch fails', async () => {
      setupAuthToken();
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ detail: 'Not found' }, false)
      );

      const session = await api.getSession();

      expect(session).toBeNull();
    });
  });

  describe('Conversation API', () => {
    beforeEach(() => {
      setupAuthToken();
    });

    it('gets all conversations', async () => {
      // Backend returns conversations with thinkers array and counts
      const mockBackendResponse = [
        {
          id: 'conv-1',
          session_id: 'session-123',
          topic: 'Philosophy',
          title: null,
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
          thinkers: [
            {
              name: 'Socrates',
              bio: 'bio',
              positions: 'pos',
              style: 'style',
              color: '#fff',
              image_url: 'https://example.com/socrates.jpg',
            },
          ],
          message_count: 5,
          total_cost: 0.123,
        },
      ];
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockBackendResponse)
      );

      const conversations = await api.getConversations();

      // Frontend transforms to ConversationSummary format
      expect(conversations).toEqual([
        {
          id: 'conv-1',
          topic: 'Philosophy',
          thinker_names: ['Socrates'],
          thinkers: [
            { name: 'Socrates', image_url: 'https://example.com/socrates.jpg' },
          ],
          message_count: 5,
          total_cost: 0.123,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ]);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/conversations'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer jwt-token-123',
          }),
        })
      );
    });

    it('gets a specific conversation', async () => {
      const mockConversation = {
        id: 'conv-1',
        topic: 'Philosophy',
        thinkers: [],
        messages: [],
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockConversation)
      );

      const conversation = await api.getConversation('conv-1');

      expect(conversation).toEqual(mockConversation);
    });

    it('creates a conversation', async () => {
      const mockConversation = {
        id: 'new-conv',
        topic: 'Science',
        thinkers: [{ name: 'Einstein' }],
        messages: [],
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockConversation)
      );

      const conversation = await api.createConversation({
        topic: 'Science',
        thinkers: [
          {
            name: 'Albert Einstein',
            bio: 'Theoretical physicist',
            positions: 'Relativity theory',
            style: 'Thoughtful and curious',
          },
        ],
      });

      expect(conversation).toEqual(mockConversation);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/conversations'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            topic: 'Science',
            thinkers: [
              {
                name: 'Albert Einstein',
                bio: 'Theoretical physicist',
                positions: 'Relativity theory',
                style: 'Thoughtful and curious',
              },
            ],
          }),
        })
      );
    });

    it('deletes a conversation', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ success: true })
      );

      await api.deleteConversation('conv-1');

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/conversations/conv-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Message API', () => {
    beforeEach(() => {
      setupAuthToken();
    });

    it('sends a message', async () => {
      const mockMessage = {
        id: 'msg-1',
        content: 'Hello',
        sender_type: 'user',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockMessage)
      );

      const message = await api.sendMessage('conv-1', 'Hello');

      expect(message).toEqual(mockMessage);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/conversations/conv-1/messages'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ content: 'Hello' }),
        })
      );
    });
  });

  describe('Thinker API', () => {
    beforeEach(() => {
      setupAuthToken();
    });

    it('suggests thinkers for a topic', async () => {
      const mockSuggestions = [
        { name: 'Socrates', reason: 'Great philosopher', profile: {} },
      ];
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockSuggestions)
      );

      const suggestions = await api.suggestThinkers('philosophy', 3);

      expect(suggestions).toEqual(mockSuggestions);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/thinkers/suggest'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            topic: 'philosophy',
            count: 3,
            exclude: [],
            language: 'en',
          }),
        })
      );
    });

    it('validates a thinker name', async () => {
      const mockValidation = {
        valid: true,
        name: 'Socrates',
        profile: { name: 'Socrates', bio: 'Philosopher' },
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockValidation)
      );

      const response = await api.validateThinker('Socrates');

      expect(response).toEqual(mockValidation);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/thinkers/validate'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'Socrates', language: 'en' }),
        })
      );
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      setupAuthToken();
    });

    it('throws error with detail from response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ detail: 'Not authorized' }, false)
      );

      await expect(api.getConversations()).rejects.toThrow('Not authorized');
    });

    it('throws error with status code when no detail', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Parse error')),
      });

      await expect(api.getConversations()).rejects.toThrow('Unknown error');
    });

    it('clears auth on 401 response', async () => {
      setupAuthToken();

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      });

      await expect(api.getConversations()).rejects.toThrow();
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });

    it('handles 401 response without crashing when window is available', async () => {
      setupAuthToken();

      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Session expired' }),
      });

      await expect(api.getConversations()).rejects.toThrow('Session expired');
    });

    it('throws timeout error when request takes too long', async () => {
      setupAuthToken();

      (global.fetch as jest.Mock).mockImplementationOnce(
        (_url: string, options: RequestInit) => {
          return new Promise((_resolve, reject) => {
            if (options.signal) {
              options.signal.addEventListener('abort', () => {
                const err = new Error('The operation was aborted');
                err.name = 'AbortError';
                reject(err);
              });
            }
          });
        }
      );

      await expect(api.getConversation('conv-1')).rejects.toThrow(/timeout/i);
    }, 35000);

    it('throws cancellation error when external signal aborts request', async () => {
      setupAuthToken();
      const controller = new AbortController();

      (global.fetch as jest.Mock).mockImplementationOnce(
        (_url: string, options: RequestInit) => {
          return new Promise((_resolve, reject) => {
            if (options.signal) {
              options.signal.addEventListener('abort', () => {
                const err = new Error('The operation was aborted');
                err.name = 'AbortError';
                reject(err);
              });
            }
          });
        }
      );

      const promise = api.suggestThinkers(
        'philosophy',
        3,
        [],
        'en',
        controller.signal
      );
      controller.abort();

      await expect(promise).rejects.toThrow(/cancelled|timeout/i);
    });
  });

  describe('Token Management', () => {
    it('setAccessToken removes token from localStorage when called with null', () => {
      api.setAccessToken(null);

      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });

    it('getStoredUser returns parsed user from localStorage', () => {
      const mockUser = {
        id: 'user-123',
        username: 'testuser',
        display_name: 'Test User',
        is_admin: false,
        total_spend: 0,
        created_at: '2024-01-15T10:00:00Z',
      };
      (localStorage.getItem as jest.Mock).mockReturnValue(
        JSON.stringify(mockUser)
      );

      const user = api.getStoredUser();

      expect(user).toEqual(mockUser);
    });

    it('getStoredUser returns null when localStorage has invalid JSON', () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('invalid json {{{');

      const user = api.getStoredUser();

      expect(user).toBeNull();
    });

    it('getStoredUser returns null when no user in localStorage', () => {
      (localStorage.getItem as jest.Mock).mockReturnValue(null);

      const user = api.getStoredUser();

      expect(user).toBeNull();
    });

    it('setStoredUser removes user from localStorage when called with null', () => {
      api.setStoredUser(null);

      expect(localStorage.removeItem).toHaveBeenCalledWith('user');
    });
  });

  describe('Auth API - Profile Updates', () => {
    beforeEach(() => {
      setupAuthToken();
    });

    it('updates language preference and stores updated user', async () => {
      const mockUser = {
        id: 'user-123',
        username: 'testuser',
        display_name: 'Test User',
        is_admin: false,
        total_spend: 0,
        created_at: '2024-01-15T10:00:00Z',
        language_preference: 'es',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockUser)
      );

      const user = await api.updateLanguage('es');

      expect(user).toEqual(mockUser);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/language'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ language_preference: 'es' }),
        })
      );
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'user',
        JSON.stringify(mockUser)
      );
    });

    it('updates display name and stores updated user', async () => {
      const mockUser = {
        id: 'user-123',
        username: 'testuser',
        display_name: 'New Display Name',
        is_admin: false,
        total_spend: 0,
        created_at: '2024-01-15T10:00:00Z',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockUser)
      );

      const user = await api.updateProfile('New Display Name');

      expect(user).toEqual(mockUser);
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

    it('changes password successfully', async () => {
      const mockResponse = { message: 'Password changed successfully' };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockResponse)
      );

      const result = await api.changePassword('oldpassword', 'newpassword');

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/change-password'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            current_password: 'oldpassword',
            new_password: 'newpassword',
          }),
        })
      );
    });

    it('clears auth when getCurrentUser fetch fails', async () => {
      setupAuthToken();
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse({ detail: 'Server error' }, false)
      );

      const user = await api.getCurrentUser();

      expect(user).toBeNull();
      expect(localStorage.removeItem).toHaveBeenCalledWith('access_token');
    });
  });

  describe('Admin API', () => {
    beforeEach(() => {
      setupAuthToken();
    });

    it('gets all admin users', async () => {
      const mockUsers = [
        {
          id: 'user-1',
          username: 'alice',
          display_name: 'Alice',
          is_admin: false,
          total_spend: 1.5,
          created_at: '2024-01-01T00:00:00Z',
          conversation_count: 3,
          message_count: 12,
        },
      ];
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockUsers)
      );

      const users = await api.getAdminUsers();

      expect(users).toEqual(mockUsers);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer jwt-token-123',
          }),
        })
      );
    });

    it('deletes a user by id', async () => {
      const mockResponse = { message: 'User deleted successfully' };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockResponse)
      );

      const result = await api.deleteUser('user-to-delete');

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users/user-to-delete'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('updates user spend limit', async () => {
      const mockResponse = {
        user_id: 'user-123',
        spend_limit: 25.0,
        message: 'Spend limit updated',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockResponse)
      );

      const result = await api.updateUserSpendLimit('user-123', 25.0);

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/admin/users/user-123/spend-limit'),
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ spend_limit: 25.0 }),
        })
      );
    });
  });

  describe('Feedback API', () => {
    it('submits feedback successfully', async () => {
      const mockResponse = { id: 'feedback-123', message: 'Feedback received' };
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createMockFetchResponse(mockResponse)
      );

      const result = await api.submitFeedback({
        feedback_type: 'bug',
        message: 'Something is broken',
        email: 'user@example.com',
      });

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/feedback'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({
            feedback_type: 'bug',
            message: 'Something is broken',
            email: 'user@example.com',
          }),
        })
      );
    });

    it('throws error with detail when feedback submission fails', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: 'Validation error' }),
      });

      await expect(
        api.submitFeedback({ feedback_type: 'bug', message: '' })
      ).rejects.toThrow('Validation error');
    });

    it('throws user-friendly message on network failure', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new TypeError('Failed to fetch')
      );

      await expect(
        api.submitFeedback({ feedback_type: 'feature', message: 'New idea' })
      ).rejects.toThrow(/unable to connect/i);
    });

    it('rethrows non-network errors from submitFeedback', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Some other error')
      );

      await expect(
        api.submitFeedback({ feedback_type: 'other', message: 'Test' })
      ).rejects.toThrow('Some other error');
    });
  });
});
