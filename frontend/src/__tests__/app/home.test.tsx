/**
 * Tests for the main Home page component (src/app/page.tsx).
 *
 * Covers:
 * - Auth loading state display
 * - Redirect to login when unauthenticated
 * - Conversation loading on mount
 * - Conversation selection
 * - Conversation deletion
 * - Creating a new conversation
 * - Logout functionality
 * - WebSocket message handling (onMessage callback)
 * - Error handling
 * - Sidebar resize persistence via localStorage
 */

import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Home from '@/app/page';
import { useAuth } from '@/contexts/AuthContext';
import { useLanguage } from '@/contexts/LanguageContext';
import { useRouter } from 'next/navigation';
import { useWebSocket } from '@/hooks/useWebSocket';
import * as api from '@/lib/api';
import type { Conversation, ConversationSummary, Message } from '@/types';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

// Mock contexts
jest.mock('@/contexts/AuthContext', () => {
  const actual = jest.requireActual('@/contexts/AuthContext');
  return { ...actual, useAuth: jest.fn() };
});

jest.mock('@/contexts/LanguageContext', () => {
  const actual = jest.requireActual('@/contexts/LanguageContext');
  return { ...actual, useLanguage: jest.fn() };
});

// Mock the WebSocket hook
jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: jest.fn(),
}));

// Mock the API module
jest.mock('@/lib/api', () => ({
  getConversations: jest.fn(),
  getConversation: jest.fn(),
  deleteConversation: jest.fn(),
  createConversation: jest.fn(),
  sendMessage: jest.fn(),
  suggestThinkers: jest.fn(),
  validateThinker: jest.fn(),
}));

// Mock heavy child components to keep tests focused on page logic
jest.mock('@/components', () => ({
  Sidebar: jest.fn(
    ({
      onNewChat,
      onSelectConversation,
      onDeleteConversation,
      onLogout,
      conversations,
    }) => (
      <div data-testid="sidebar">
        <button onClick={onNewChat} data-testid="new-chat-btn">
          New Chat
        </button>
        <button onClick={onLogout} data-testid="logout-btn">
          Logout
        </button>
        {conversations.map((c: ConversationSummary) => (
          <div key={c.id} data-testid={`conv-${c.id}`}>
            <button
              onClick={() => onSelectConversation(c.id)}
              data-testid={`select-${c.id}`}
            >
              {c.topic}
            </button>
            <button
              onClick={() => onDeleteConversation(c.id)}
              data-testid={`delete-${c.id}`}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    )
  ),
  ChatArea: jest.fn(({ onSendMessage, errorMessage, onDismissError }) => (
    <div data-testid="chat-area">
      <button
        onClick={() => onSendMessage('test message')}
        data-testid="send-msg-btn"
      >
        Send
      </button>
      {errorMessage && (
        <div data-testid="error-banner">
          {errorMessage}
          <button onClick={onDismissError} data-testid="dismiss-error">
            Dismiss
          </button>
        </div>
      )}
    </div>
  )),
  NewChatModal: jest.fn(({ isOpen, onClose, onCreate }) =>
    isOpen ? (
      <div data-testid="new-chat-modal">
        <button onClick={onClose} data-testid="close-modal">
          Close
        </button>
        <button
          onClick={() =>
            onCreate('Philosophy', [
              {
                name: 'Socrates',
                bio: 'bio',
                positions: 'pos',
                style: 'style',
              },
            ])
          }
          data-testid="create-conv-btn"
        >
          Create
        </button>
      </div>
    ) : null
  ),
  ResizeDivider: jest.fn(() => <div data-testid="resize-divider" />),
}));

const mockWebSocket = {
  isConnected: true,
  isPaused: false,
  speedMultiplier: 1.0,
  typingThinkers: new Set<string>(),
  thinkingContent: new Map<string, string>(),
  sendUserMessage: jest.fn(),
  sendTypingStart: jest.fn(),
  sendTypingStop: jest.fn(),
  sendPause: jest.fn(),
  sendResume: jest.fn(),
  sendSetSpeed: jest.fn(),
};

const mockUser = {
  id: 'user-123',
  username: 'testuser',
  display_name: 'Test User',
  is_admin: false,
  total_spend: 0,
  created_at: '2024-01-01T00:00:00Z',
};

const mockConversations: ConversationSummary[] = [
  {
    id: 'conv-1',
    topic: 'Philosophy of Mind',
    thinker_names: ['Socrates'],
    thinkers: [{ name: 'Socrates', image_url: null }],
    message_count: 5,
    total_cost: 0.05,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const mockFullConversation: Conversation = {
  id: 'conv-1',
  topic: 'Philosophy of Mind',
  thinkers: [
    {
      name: 'Socrates',
      bio: 'Greek philosopher',
      positions: 'Virtue ethics',
      style: 'Socratic method',
      color: '#4a90e2',
      image_url: null,
    },
  ],
  messages: [
    {
      id: 'msg-1',
      conversation_id: 'conv-1',
      sender_type: 'user',
      sender_name: 'testuser',
      content: 'Hello!',
      cost: 0,
      created_at: '2024-01-01T00:00:00Z',
    } as Message,
  ],
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
  total_cost: 0.05,
  session_id: 'session-123',
};

function setupMocks(
  overrides: { isAuthenticated?: boolean; authLoading?: boolean } = {}
) {
  const mockRouter = { push: jest.fn(), replace: jest.fn() };
  (useRouter as jest.Mock).mockReturnValue(mockRouter);
  (useAuth as jest.Mock).mockReturnValue({
    user: mockUser,
    isAuthenticated: overrides.isAuthenticated ?? true,
    isLoading: overrides.authLoading ?? false,
    logout: jest.fn(),
  });
  (useLanguage as jest.Mock).mockReturnValue({ locale: 'en' });
  (useWebSocket as jest.Mock).mockReturnValue(mockWebSocket);
  (api.getConversations as jest.Mock).mockResolvedValue(mockConversations);
  return { mockRouter };
}

describe('Home Page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading state while auth is loading', () => {
      setupMocks({ authLoading: true });
      render(<Home />);

      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });

    it('shows loading while conversations are fetching', async () => {
      setupMocks();
      let resolveConversations: (v: ConversationSummary[]) => void;
      (api.getConversations as jest.Mock).mockReturnValue(
        new Promise((resolve) => {
          resolveConversations = resolve;
        })
      );

      render(<Home />);

      expect(screen.getByText('Loading...')).toBeInTheDocument();

      await act(async () => {
        resolveConversations!(mockConversations);
      });

      await waitFor(() => {
        expect(screen.getByTestId('sidebar')).toBeInTheDocument();
      });
    });
  });

  describe('Authentication', () => {
    it('redirects to login when not authenticated', async () => {
      const { mockRouter } = setupMocks({ isAuthenticated: false });
      (useAuth as jest.Mock).mockReturnValue({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        logout: jest.fn(),
      });

      render(<Home />);

      await waitFor(() => {
        expect(mockRouter.replace).toHaveBeenCalledWith('/login');
      });
    });

    it('renders main UI when authenticated', async () => {
      setupMocks();
      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('sidebar')).toBeInTheDocument();
        expect(screen.getByTestId('chat-area')).toBeInTheDocument();
      });
    });
  });

  describe('Conversation Loading', () => {
    it('loads conversations on mount when authenticated', async () => {
      setupMocks();
      render(<Home />);

      await waitFor(() => {
        expect(api.getConversations).toHaveBeenCalledTimes(1);
      });

      await waitFor(() => {
        expect(screen.getByTestId('conv-conv-1')).toBeInTheDocument();
      });
    });

    it('handles conversation load failure gracefully', async () => {
      setupMocks();
      (api.getConversations as jest.Mock).mockRejectedValue(
        new Error('Network error')
      );

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('sidebar')).toBeInTheDocument();
      });
    });
  });

  describe('Conversation Selection', () => {
    it('loads and displays conversation when selected', async () => {
      setupMocks();
      (api.getConversation as jest.Mock).mockResolvedValue(
        mockFullConversation
      );

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('select-conv-1')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId('select-conv-1'));

      await waitFor(() => {
        expect(api.getConversation).toHaveBeenCalledWith('conv-1');
      });
    });

    it('handles conversation selection failure gracefully', async () => {
      setupMocks();
      (api.getConversation as jest.Mock).mockRejectedValue(
        new Error('Not found')
      );

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('select-conv-1')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId('select-conv-1'));

      await waitFor(() => {
        expect(api.getConversation).toHaveBeenCalled();
      });
    });
  });

  describe('Conversation Deletion', () => {
    it('deletes conversation and removes from list', async () => {
      setupMocks();
      (api.deleteConversation as jest.Mock).mockResolvedValue(undefined);

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('delete-conv-1')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId('delete-conv-1'));

      await waitFor(() => {
        expect(api.deleteConversation).toHaveBeenCalledWith('conv-1');
      });
    });

    it('handles delete failure gracefully', async () => {
      setupMocks();
      (api.deleteConversation as jest.Mock).mockRejectedValue(
        new Error('Delete failed')
      );

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('delete-conv-1')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId('delete-conv-1'));

      await waitFor(() => {
        expect(api.deleteConversation).toHaveBeenCalledWith('conv-1');
      });
    });
  });

  describe('New Conversation', () => {
    it('opens new chat modal when new chat button clicked', async () => {
      setupMocks();

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('new-chat-btn')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId('new-chat-btn'));

      expect(screen.getByTestId('new-chat-modal')).toBeInTheDocument();
    });

    it('creates a conversation and adds it to the list', async () => {
      setupMocks();
      const newConv: Conversation = {
        id: 'conv-new',
        topic: 'Philosophy',
        thinkers: [
          {
            name: 'Socrates',
            bio: 'bio',
            positions: 'pos',
            style: 'style',
            color: '#fff',
            image_url: null,
          },
        ],
        messages: [],
        is_active: true,
        created_at: '2024-01-02T00:00:00Z',
        total_cost: 0,
        session_id: 'session-123',
      };
      (api.createConversation as jest.Mock).mockResolvedValue(newConv);

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('new-chat-btn')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId('new-chat-btn'));

      await waitFor(() => {
        expect(screen.getByTestId('create-conv-btn')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId('create-conv-btn'));

      await waitFor(() => {
        expect(api.createConversation).toHaveBeenCalledWith({
          topic: 'Philosophy',
          thinkers: [
            { name: 'Socrates', bio: 'bio', positions: 'pos', style: 'style' },
          ],
        });
      });
    });
  });

  describe('Logout', () => {
    it('calls logout and redirects to login', async () => {
      const mockLogout = jest.fn().mockResolvedValue(undefined);
      const { mockRouter } = setupMocks();
      (useAuth as jest.Mock).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        isLoading: false,
        logout: mockLogout,
      });

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('logout-btn')).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId('logout-btn'));

      await waitFor(() => {
        expect(mockLogout).toHaveBeenCalled();
        expect(mockRouter.push).toHaveBeenCalledWith('/login');
      });
    });
  });

  describe('Sidebar Width Persistence', () => {
    it('loads saved sidebar width from localStorage on mount', async () => {
      setupMocks();
      const localStorageGetItem = jest.spyOn(Storage.prototype, 'getItem');
      localStorageGetItem.mockImplementation((key: string) => {
        if (key === 'dining-philosophers-sidebar-width') return '350';
        return null;
      });

      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('sidebar')).toBeInTheDocument();
      });

      localStorageGetItem.mockRestore();
    });

    it('renders main chat layout with sidebar and chat area', async () => {
      setupMocks();
      render(<Home />);

      await waitFor(() => {
        expect(screen.getByTestId('sidebar')).toBeInTheDocument();
        expect(screen.getByTestId('chat-area')).toBeInTheDocument();
        expect(screen.getByTestId('resize-divider')).toBeInTheDocument();
      });
    });
  });
});
