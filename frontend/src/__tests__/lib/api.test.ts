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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const response = await api.login('testuser', 'password123');

      expect(response).toEqual(mockResponse);
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'access_token',
        'jwt-token-456'
      );
    });

    it('logs out and clears auth data', async () => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ message: 'Logged out' }),
      });

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
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUser),
      });

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
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockSession),
      });

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
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: 'Not found' }),
      });

      const session = await api.getSession();

      expect(session).toBeNull();
    });
  });

  describe('Conversation API', () => {
    beforeEach(() => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockBackendResponse),
      });

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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockConversation),
      });

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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockConversation),
      });

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
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await api.deleteConversation('conv-1');

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/conversations/conv-1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Message API', () => {
    beforeEach(() => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
    });

    it('sends a message', async () => {
      const mockMessage = {
        id: 'msg-1',
        content: 'Hello',
        sender_type: 'user',
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockMessage),
      });

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
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
    });

    it('suggests thinkers for a topic', async () => {
      const mockSuggestions = [
        { name: 'Socrates', reason: 'Great philosopher', profile: {} },
      ];
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockSuggestions),
      });

      const suggestions = await api.suggestThinkers('philosophy', 3);

      expect(suggestions).toEqual(mockSuggestions);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/thinkers/suggest'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ topic: 'philosophy', count: 3, exclude: [] }),
        })
      );
    });

    it('validates a thinker name', async () => {
      const mockResponse = {
        valid: true,
        name: 'Socrates',
        profile: { name: 'Socrates', bio: 'Philosopher' },
      };
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const response = await api.validateThinker('Socrates');

      expect(response).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/thinkers/validate'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'Socrates' }),
        })
      );
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      (localStorage.getItem as jest.Mock).mockReturnValue('jwt-token-123');
    });

    it('throws error with detail from response', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: 'Not authorized' }),
      });

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
  });
});
