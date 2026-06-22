/**
 * Tests for the Home page component (src/app/page.tsx).
 *
 * The Home page is the main application shell. It wires together the Sidebar,
 * ChatArea, ResizeDivider and NewChatModal, owns all conversation CRUD state,
 * and bridges the WebSocket hook to the message list. These tests mock the
 * child components and the hooks/api modules so the page's own logic (callbacks,
 * effects, conditional rendering) can be exercised directly.
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import Home from '@/app/page';
import { useAuth, useLanguage } from '@/contexts';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api';
import type {
  ChatAreaProps,
  NewChatModalProps,
  ResizeDividerProps,
  SidebarProps,
} from '@/components';
import type {
  Conversation,
  ConversationSummary,
  Message,
  ThinkerProfile,
} from '@/types';

// Capture the props passed to each mocked child component so tests can invoke
// their callbacks directly. Keys are filled in lazily on first render.
type Captured = {
  sidebar: SidebarProps;
  chatArea: ChatAreaProps;
  resizeDivider: ResizeDividerProps;
  newChatModal: NewChatModalProps;
};
let captured: Captured = {} as Captured;

jest.mock('@/components', () => ({
  Sidebar: (props: SidebarProps) => {
    captured.sidebar = props;
    return <div data-testid="sidebar" />;
  },
  ChatArea: (props: ChatAreaProps) => {
    captured.chatArea = props;
    return <div data-testid="chat-area" />;
  },
  ResizeDivider: (props: ResizeDividerProps) => {
    captured.resizeDivider = props;
    return <div data-testid="resize-divider" />;
  },
  NewChatModal: (props: NewChatModalProps) => {
    captured.newChatModal = props;
    return <div data-testid="new-chat-modal" />;
  },
}));

// Capture the config passed to useWebSocket so onMessage/onError can be fired.
const mockWsConfig: {
  current: {
    conversationId: string | null;
    onMessage: (message: Message) => void;
    onError: (message: string) => void;
  };
} = { current: { conversationId: null, onMessage: () => {}, onError: () => {} } };
const mockWs = {
  isConnected: true,
  isPaused: false,
  speedMultiplier: 1,
  typingThinkers: new Set<string>(),
  thinkingContent: {},
  sendUserMessage: jest.fn(),
  sendTypingStart: jest.fn(),
  sendTypingStop: jest.fn(),
  sendPause: jest.fn(),
  sendResume: jest.fn(),
  sendSetSpeed: jest.fn(),
};

jest.mock('@/hooks', () => ({
  useWebSocket: (config: (typeof mockWsConfig)['current']) => {
    mockWsConfig.current = config;
    return mockWs;
  },
}));

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

jest.mock('@/contexts', () => ({
  useAuth: jest.fn(),
  useLanguage: jest.fn(),
}));

jest.mock('@/lib/api');

const mockedApi = api as jest.Mocked<typeof api>;

// ---- Test data factories -------------------------------------------------

const makeUser = (overrides = {}) => ({
  id: 'u1',
  username: 'socrates',
  display_name: 'Socrates',
  is_admin: false,
  total_spend: 1.5,
  spend_limit: 10,
  language_preference: 'en',
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

const makeSummary = (
  overrides: Partial<ConversationSummary> = {}
): ConversationSummary => ({
  id: 'c1',
  topic: 'Ethics',
  thinker_names: ['Kant'],
  thinkers: [{ name: 'Kant', image_url: null }],
  message_count: 2,
  total_cost: 0.5,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

const makeConversation = (
  overrides: Partial<Conversation> = {}
): Conversation => ({
  id: 'c1',
  session_id: 's1',
  topic: 'Ethics',
  thinkers: [
    {
      id: 't1',
      name: 'Kant',
      bio: 'bio',
      positions: 'pos',
      style: 'style',
      color: '#fff',
      image_url: null,
    },
  ],
  messages: [],
  total_cost: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

const makeMessage = (overrides: Partial<Message> = {}): Message => ({
  id: 'm1',
  conversation_id: 'c1',
  sender_type: 'thinker',
  sender_name: 'Kant',
  content: 'Hello',
  cost: 0.1,
  created_at: '2024-01-01T00:00:01Z',
  ...overrides,
});

// ---- Shared mocks --------------------------------------------------------

const mockRouter = { push: jest.fn(), replace: jest.fn() };
const mockLogout = jest.fn();

const setAuth = (overrides = {}) => {
  (useAuth as jest.Mock).mockReturnValue({
    user: makeUser(),
    isAuthenticated: true,
    isLoading: false,
    logout: mockLogout,
    ...overrides,
  });
};

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  captured = {} as Captured;
  (useRouter as jest.Mock).mockReturnValue(mockRouter);
  (useLanguage as jest.Mock).mockReturnValue({ locale: 'en' });
  setAuth();
  mockedApi.getConversations.mockResolvedValue([]);
});

// ---- Tests ---------------------------------------------------------------

describe('Home page - rendering states', () => {
  it('shows a loading indicator while auth is loading', () => {
    setAuth({ isLoading: true });
    render(<Home />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.queryByTestId('sidebar')).not.toBeInTheDocument();
  });

  it('renders null once auth is lost after the initial load settles', async () => {
    // First render authenticated so the internal isLoading flag flips to false
    // (it only does so after getConversations resolves while authenticated).
    const { rerender, container } = render(<Home />);
    await waitFor(() =>
      expect(screen.getByTestId('sidebar')).toBeInTheDocument()
    );

    // Now auth is lost: with loading settled and unauthenticated, the page
    // returns null (the redirect effect handles navigation).
    setAuth({ isAuthenticated: false });
    rerender(<Home />);

    await waitFor(() =>
      expect(screen.queryByTestId('sidebar')).not.toBeInTheDocument()
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('redirects to /login when not authenticated', async () => {
    setAuth({ isAuthenticated: false });
    render(<Home />);
    await waitFor(() => {
      expect(mockRouter.replace).toHaveBeenCalledWith('/login');
    });
  });

  it('renders the full shell when authenticated and loaded', async () => {
    render(<Home />);
    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    });
    expect(screen.getByTestId('chat-area')).toBeInTheDocument();
    expect(screen.getByTestId('resize-divider')).toBeInTheDocument();
    expect(screen.getByTestId('new-chat-modal')).toBeInTheDocument();
  });
});

describe('Home page - conversation loading', () => {
  it('loads conversations on mount and passes them to the Sidebar', async () => {
    const summary = makeSummary();
    mockedApi.getConversations.mockResolvedValue([summary]);
    render(<Home />);
    await waitFor(() => {
      expect(captured.sidebar.conversations).toEqual([summary]);
    });
  });

  it('logs and recovers when loading conversations fails', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockedApi.getConversations.mockRejectedValue(new Error('boom'));
    render(<Home />);
    await waitFor(() => {
      // Still renders the shell despite the failure (finally sets loading false).
      expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    });
    expect(spy).toHaveBeenCalledWith(
      'Failed to load conversations:',
      expect.any(Error)
    );
    spy.mockRestore();
  });
});

describe('Home page - conversation selection', () => {
  it('loads and displays the selected conversation', async () => {
    const conv = makeConversation({ messages: [makeMessage()] });
    mockedApi.getConversation.mockResolvedValue(conv);
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());

    await act(async () => {
      await captured.sidebar.onSelectConversation('c1');
    });

    expect(mockedApi.getConversation).toHaveBeenCalledWith('c1');
    expect(captured.chatArea.conversation).toEqual(conv);
    expect(captured.chatArea.messages).toEqual(conv.messages);
  });

  it('closes the sidebar on mobile widths after selecting', async () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 500,
    });
    mockedApi.getConversation.mockResolvedValue(makeConversation());
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());

    await act(async () => {
      await captured.sidebar.onSelectConversation('c1');
    });
    await waitFor(() => expect(captured.sidebar.isOpen).toBe(false));

    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 1280,
    });
  });

  it('logs an error when selecting a conversation fails', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockedApi.getConversation.mockRejectedValue(new Error('nope'));
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());

    await act(async () => {
      await captured.sidebar.onSelectConversation('c1');
    });

    expect(spy).toHaveBeenCalledWith(
      'Failed to load conversation:',
      expect.any(Error)
    );
    spy.mockRestore();
  });
});

describe('Home page - conversation deletion', () => {
  it('removes a deleted conversation from the list', async () => {
    mockedApi.getConversations.mockResolvedValue([
      makeSummary({ id: 'c1' }),
      makeSummary({ id: 'c2' }),
    ]);
    mockedApi.deleteConversation.mockResolvedValue(undefined as never);
    render(<Home />);
    await waitFor(() => expect(captured.sidebar.conversations).toHaveLength(2));

    await act(async () => {
      await captured.sidebar.onDeleteConversation!('c1');
    });

    expect(mockedApi.deleteConversation).toHaveBeenCalledWith('c1');
    await waitFor(() =>
      expect(captured.sidebar.conversations.map((c) => c.id)).toEqual(['c2'])
    );
  });

  it('clears the current conversation when it is the one deleted', async () => {
    mockedApi.getConversations.mockResolvedValue([makeSummary({ id: 'c1' })]);
    mockedApi.getConversation.mockResolvedValue(makeConversation({ id: 'c1' }));
    mockedApi.deleteConversation.mockResolvedValue(undefined as never);
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());

    await act(async () => {
      await captured.sidebar.onSelectConversation('c1');
    });
    await waitFor(() => expect(captured.chatArea.conversation).toBeTruthy());

    await act(async () => {
      await captured.sidebar.onDeleteConversation!('c1');
    });

    await waitFor(() => expect(captured.chatArea.conversation).toBeNull());
    expect(captured.chatArea.messages).toEqual([]);
  });

  it('logs an error when deletion fails', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockedApi.getConversations.mockResolvedValue([makeSummary({ id: 'c1' })]);
    mockedApi.deleteConversation.mockRejectedValue(new Error('fail'));
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());

    await act(async () => {
      await captured.sidebar.onDeleteConversation!('c1');
    });

    expect(spy).toHaveBeenCalledWith(
      'Failed to delete conversation:',
      expect.any(Error)
    );
    spy.mockRestore();
  });
});

describe('Home page - sending messages', () => {
  const selectConv = async () => {
    mockedApi.getConversation.mockResolvedValue(makeConversation({ id: 'c1' }));
    await act(async () => {
      await captured.sidebar.onSelectConversation('c1');
    });
    await waitFor(() => expect(captured.chatArea.conversation).toBeTruthy());
  };

  it('does nothing when there is no current conversation', async () => {
    render(<Home />);
    await waitFor(() => expect(captured.chatArea).toBeDefined());

    await act(async () => {
      await captured.chatArea.onSendMessage('hi');
    });

    expect(mockedApi.sendMessage).not.toHaveBeenCalled();
  });

  it('sends a message and notifies via WebSocket', async () => {
    const sent = makeMessage({ id: 'm9', sender_type: 'user', content: 'hi' });
    mockedApi.sendMessage.mockResolvedValue(sent);
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());
    await selectConv();

    await act(async () => {
      await captured.chatArea.onSendMessage('hi');
    });

    expect(mockedApi.sendMessage).toHaveBeenCalledWith('c1', 'hi');
    expect(mockWs.sendUserMessage).toHaveBeenCalledWith('hi');
    await waitFor(() =>
      expect(captured.chatArea.messages).toContainEqual(sent)
    );
  });

  it('surfaces a non-401 send error to the user', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockedApi.sendMessage.mockRejectedValue(new Error('server exploded'));
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());
    await selectConv();

    await act(async () => {
      await captured.chatArea.onSendMessage('hi');
    });

    await waitFor(() =>
      expect(captured.chatArea.errorMessage).toBe(
        'Failed to send message: server exploded'
      )
    );
    spy.mockRestore();
  });

  it('does not show an error banner for a 401 send error', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockedApi.sendMessage.mockRejectedValue(new Error('401 Unauthorized'));
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());
    await selectConv();

    await act(async () => {
      await captured.chatArea.onSendMessage('hi');
    });

    // 401 is swallowed (handled by redirect elsewhere) - no banner text set.
    expect(captured.chatArea.errorMessage).toBe('');
    spy.mockRestore();
  });
});

describe('Home page - creating conversations', () => {
  it('prepends the new conversation and makes it current', async () => {
    const created = makeConversation({ id: 'cNew', topic: 'New Topic' });
    mockedApi.createConversation.mockResolvedValue(created);
    render(<Home />);
    await waitFor(() => expect(captured.newChatModal).toBeDefined());

    await act(async () => {
      await captured.newChatModal.onCreate('New Topic', [
        { name: 'Kant', bio: 'b', positions: 'p', style: 's' },
      ]);
    });

    expect(mockedApi.createConversation).toHaveBeenCalledWith({
      topic: 'New Topic',
      thinkers: [{ name: 'Kant', bio: 'b', positions: 'p', style: 's' }],
    });
    await waitFor(() => {
      expect(captured.sidebar.conversations[0].id).toBe('cNew');
      expect(captured.chatArea.conversation!.id).toBe('cNew');
    });
    expect(captured.chatArea.messages).toEqual([]);
  });

  it('closes the sidebar on mobile widths after creating', async () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 500,
    });
    mockedApi.createConversation.mockResolvedValue(
      makeConversation({ id: 'cNew' })
    );
    render(<Home />);
    await waitFor(() => expect(captured.newChatModal).toBeDefined());

    await act(async () => {
      await captured.newChatModal.onCreate('T', [
        { name: 'Kant', bio: 'b', positions: 'p', style: 's' },
      ]);
    });

    await waitFor(() => expect(captured.sidebar.isOpen).toBe(false));

    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: 1280,
    });
  });
});

describe('Home page - thinker suggestion & validation', () => {
  it('delegates suggestThinkers to the api with the current locale', async () => {
    (useLanguage as jest.Mock).mockReturnValue({ locale: 'fr' });
    const suggestions = [
      {
        name: 'Hume',
        reason: 'r',
        profile: { name: 'Hume', bio: '', positions: '', style: '' },
      },
    ];
    mockedApi.suggestThinkers.mockResolvedValue(suggestions as never);
    render(<Home />);
    await waitFor(() => expect(captured.newChatModal).toBeDefined());

    let result: unknown;
    await act(async () => {
      result = await captured.newChatModal.onSuggestThinkers('topic', 3, ['x']);
    });

    expect(mockedApi.suggestThinkers).toHaveBeenCalledWith(
      'topic',
      3,
      ['x'],
      'fr'
    );
    expect(result).toEqual(suggestions);
  });

  it('returns the profile when a custom thinker validates', async () => {
    const profile: ThinkerProfile = {
      name: 'Hume',
      bio: 'b',
      positions: 'p',
      style: 's',
    };
    mockedApi.validateThinker.mockResolvedValue({
      valid: true,
      profile,
    } as never);
    render(<Home />);
    await waitFor(() => expect(captured.newChatModal).toBeDefined());

    let result: unknown;
    await act(async () => {
      result = await captured.newChatModal.onValidateThinker('Hume');
    });

    expect(result).toEqual(profile);
  });

  it('returns null when a custom thinker is invalid', async () => {
    mockedApi.validateThinker.mockResolvedValue({
      valid: false,
      profile: null,
    } as never);
    render(<Home />);
    await waitFor(() => expect(captured.newChatModal).toBeDefined());

    let result: unknown;
    await act(async () => {
      result = await captured.newChatModal.onValidateThinker('NotReal');
    });

    expect(result).toBeNull();
  });
});

describe('Home page - logout', () => {
  it('logs out and navigates to /login', async () => {
    mockLogout.mockResolvedValue(undefined);
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());

    await act(async () => {
      await captured.sidebar.onLogout!();
    });

    expect(mockLogout).toHaveBeenCalled();
    expect(mockRouter.push).toHaveBeenCalledWith('/login');
  });
});

describe('Home page - WebSocket message handling', () => {
  it('appends incoming messages and accumulates session cost', async () => {
    render(<Home />);
    await waitFor(() => expect(captured.chatArea).toBeDefined());

    act(() => {
      mockWsConfig.current.onMessage(makeMessage({ cost: 0.25 }));
    });

    await waitFor(() => expect(captured.chatArea.messages).toHaveLength(1));
    expect(captured.sidebar.sessionCost).toBe(0.25);
    // userTotalSpend = base total_spend (1.5) + session cost (0.25)
    expect(captured.chatArea.userTotalSpend).toBeCloseTo(1.75);
  });

  it('updates the matching sidebar summary for thinker messages', async () => {
    mockedApi.getConversations.mockResolvedValue([
      makeSummary({ id: 'c1', message_count: 2, total_cost: 0.5 }),
    ]);
    render(<Home />);
    await waitFor(() => expect(captured.sidebar.conversations).toHaveLength(1));

    act(() => {
      mockWsConfig.current.onMessage(
        makeMessage({ conversation_id: 'c1', cost: 0.3 })
      );
    });

    await waitFor(() => {
      const conv = captured.sidebar.conversations[0];
      expect(conv.message_count).toBe(3);
      expect(conv.total_cost).toBeCloseTo(0.8);
    });
  });

  it('leaves non-matching conversation summaries untouched', async () => {
    mockedApi.getConversations.mockResolvedValue([
      makeSummary({ id: 'c1', message_count: 2, total_cost: 0.5 }),
    ]);
    render(<Home />);
    await waitFor(() => expect(captured.sidebar.conversations).toHaveLength(1));

    act(() => {
      // Thinker message for a different conversation than the one in the list.
      mockWsConfig.current.onMessage(
        makeMessage({ conversation_id: 'cOther', cost: 0.9 })
      );
    });

    await waitFor(() => expect(captured.chatArea.messages).toHaveLength(1));
    const conv = captured.sidebar.conversations[0];
    expect(conv.message_count).toBe(2);
    expect(conv.total_cost).toBeCloseTo(0.5);
  });

  it('does not bump message_count for user messages', async () => {
    mockedApi.getConversations.mockResolvedValue([
      makeSummary({ id: 'c1', message_count: 2 }),
    ]);
    render(<Home />);
    await waitFor(() => expect(captured.sidebar.conversations).toHaveLength(1));

    act(() => {
      mockWsConfig.current.onMessage(
        makeMessage({ conversation_id: 'c1', sender_type: 'user', cost: null })
      );
    });

    await waitFor(() => expect(captured.chatArea.messages).toHaveLength(1));
    // User messages are free and should not change the summary counters.
    expect(captured.sidebar.conversations[0].message_count).toBe(2);
  });
});

describe('Home page - WebSocket error handling', () => {
  it('flags the spend limit when a spend-limit error arrives', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    render(<Home />);
    await waitFor(() => expect(captured.chatArea).toBeDefined());

    act(() => {
      mockWsConfig.current.onError('Spend limit exceeded for this user');
    });

    await waitFor(() =>
      expect(captured.chatArea.spendLimitExceeded).toBe(true)
    );
    expect(captured.chatArea.errorMessage).toBe(
      'Spend limit exceeded for this user'
    );
    spy.mockRestore();
  });

  it('sets a generic error message without the spend-limit flag', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    render(<Home />);
    await waitFor(() => expect(captured.chatArea).toBeDefined());

    act(() => {
      mockWsConfig.current.onError('Connection dropped');
    });

    await waitFor(() =>
      expect(captured.chatArea.errorMessage).toBe('Connection dropped')
    );
    expect(captured.chatArea.spendLimitExceeded).toBe(false);
    spy.mockRestore();
  });

  it('clears the error message via the ChatArea dismiss callback', async () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    render(<Home />);
    await waitFor(() => expect(captured.chatArea).toBeDefined());

    act(() => {
      mockWsConfig.current.onError('Connection dropped');
    });
    await waitFor(() =>
      expect(captured.chatArea.errorMessage).toBe('Connection dropped')
    );

    act(() => {
      captured.chatArea.onDismissError!();
    });
    await waitFor(() => expect(captured.chatArea.errorMessage).toBe(''));
    spy.mockRestore();
  });
});

describe('Home page - sidebar width persistence & toggling', () => {
  it('restores a valid saved sidebar width from localStorage', async () => {
    (window.localStorage.getItem as jest.Mock).mockReturnValue('350');
    render(<Home />);
    await waitFor(() => expect(captured.sidebar.width).toBe(350));
  });

  it('ignores an out-of-range saved width', async () => {
    (window.localStorage.getItem as jest.Mock).mockReturnValue('9999');
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());
    // Falls back to the default width (288) when stored value is out of bounds.
    expect(captured.sidebar.width).toBe(288);
  });

  it('persists a new width when the divider is dragged', async () => {
    render(<Home />);
    await waitFor(() => expect(captured.resizeDivider).toBeDefined());

    act(() => {
      captured.resizeDivider.onResize(420);
    });

    await waitFor(() => expect(captured.sidebar.width).toBe(420));
    expect(window.localStorage.setItem).toHaveBeenCalledWith(
      'dining-philosophers-sidebar-width',
      '420'
    );
  });

  it('toggles the sidebar open state', async () => {
    render(<Home />);
    await waitFor(() => expect(captured.sidebar).toBeDefined());
    expect(captured.sidebar.isOpen).toBe(true);

    act(() => {
      captured.sidebar.onToggle();
    });

    await waitFor(() => expect(captured.sidebar.isOpen).toBe(false));
  });

  it('opens the new-chat modal from the sidebar', async () => {
    render(<Home />);
    await waitFor(() => expect(captured.newChatModal).toBeDefined());
    expect(captured.newChatModal.isOpen).toBe(false);

    act(() => {
      captured.sidebar.onNewChat();
    });

    await waitFor(() => expect(captured.newChatModal.isOpen).toBe(true));
  });
});
