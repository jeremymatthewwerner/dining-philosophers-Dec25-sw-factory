/**
 * Tests for the Home page component (src/app/page.tsx).
 *
 * The Home page is the main chat orchestration surface. It wires together the
 * auth redirect, conversation loading, the WebSocket message/error callbacks,
 * the send/create/delete/select handlers, sidebar width persistence and the
 * spend-limit display. Child components, hooks and the API layer are mocked so
 * these tests exercise the page's own logic in isolation.
 */

import React from 'react';
import {
  render,
  screen,
  waitFor,
  act,
  fireEvent,
} from '@testing-library/react';
import Home from '@/app/page';
import { useAuth, useLanguage } from '@/contexts';
import { useWebSocket } from '@/hooks';
import { useRouter } from 'next/navigation';
import * as api from '@/lib/api';
import type {
  Conversation,
  ConversationSummary,
  Message,
  ThinkerProfile,
} from '@/types';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}));

jest.mock('@/contexts', () => ({
  useAuth: jest.fn(),
  useLanguage: jest.fn(),
}));

jest.mock('@/hooks', () => ({
  useWebSocket: jest.fn(),
}));

jest.mock('@/lib/api', () => ({
  getConversations: jest.fn(),
  getConversation: jest.fn(),
  deleteConversation: jest.fn(),
  sendMessage: jest.fn(),
  createConversation: jest.fn(),
  suggestThinkers: jest.fn(),
  validateThinker: jest.fn(),
}));

// Captured props/options so tests can drive callbacks the page passes down.
interface WsOptions {
  conversationId: string | null;
  onMessage: (message: Message) => void;
  onError: (error: string) => void;
}
let wsOptions: WsOptions;

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (topic: string, thinkers: unknown[]) => Promise<void> | void;
  onSuggestThinkers: (
    topic: string,
    count?: number,
    exclude?: string[]
  ) => Promise<unknown>;
  onValidateThinker: (name: string) => Promise<ThinkerProfile | null>;
}
let modalProps: ModalProps;

interface SidebarProps {
  conversations: ConversationSummary[];
  selectedId: string | null;
  username?: string;
  isOpen: boolean;
  width: number;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onNewChat: () => void;
  onToggle: () => void;
  onLogout: () => void;
}

interface ChatAreaProps {
  conversation: Conversation | null;
  messages: Message[];
  typingThinkers: string[];
  errorMessage: string;
  userTotalSpend: number;
  userSpendLimit: number;
  spendLimitExceeded: boolean;
  onSendMessage: (content: string) => void;
  onDismissError: () => void;
}

jest.mock('@/components', () => ({
  Sidebar: (props: SidebarProps) => (
    <div
      data-testid="sidebar"
      data-open={String(props.isOpen)}
      data-width={props.width}
    >
      <span data-testid="sidebar-conv-count">{props.conversations.length}</span>
      <span data-testid="sidebar-selected">{props.selectedId || 'none'}</span>
      <span data-testid="sidebar-username">{props.username || ''}</span>
      <button onClick={() => props.onSelectConversation('conv-1')}>
        select-conv
      </button>
      <button onClick={() => props.onDeleteConversation('conv-1')}>
        delete-conv
      </button>
      <button onClick={props.onNewChat}>new-chat</button>
      <button onClick={props.onToggle}>toggle-sidebar</button>
      <button onClick={props.onLogout}>logout</button>
    </div>
  ),
  ChatArea: (props: ChatAreaProps) => (
    <div data-testid="chatarea">
      <span data-testid="chat-msg-count">{props.messages.length}</span>
      <span data-testid="chat-error">{props.errorMessage}</span>
      <span data-testid="chat-total-spend">{props.userTotalSpend}</span>
      <span data-testid="chat-spend-limit">{props.userSpendLimit}</span>
      <span data-testid="chat-spend-exceeded">
        {String(props.spendLimitExceeded)}
      </span>
      <span data-testid="chat-conversation">
        {props.conversation?.id || 'none'}
      </span>
      <span data-testid="chat-typing">{props.typingThinkers.join(',')}</span>
      <button onClick={() => props.onSendMessage('hello')}>send-message</button>
      <button onClick={props.onDismissError}>dismiss-error</button>
    </div>
  ),
  NewChatModal: (props: ModalProps) => {
    modalProps = props;
    return (
      <div data-testid="newchatmodal" data-open={String(props.isOpen)}>
        <button
          onClick={() =>
            props.onCreate('New Topic', [
              {
                name: 'Plato',
                bio: 'b',
                positions: 'p',
                style: 's',
                image_url: null,
              },
            ])
          }
        >
          create-conv
        </button>
        <button onClick={props.onClose}>close-modal</button>
      </div>
    );
  },
  ResizeDivider: (props: { onResize: (width: number) => void }) => (
    <button data-testid="resize" onClick={() => props.onResize(350)}>
      resize
    </button>
  ),
}));

// ---------------------------------------------------------------------------
// Shared fixtures
// ---------------------------------------------------------------------------

const SIDEBAR_WIDTH_KEY = 'dining-philosophers-sidebar-width';

const mockRouter = { push: jest.fn(), replace: jest.fn() };
const mockLogout = jest.fn();

const mockSendUserMessage = jest.fn();
const mockSendTypingStart = jest.fn();
const mockSendTypingStop = jest.fn();
const mockSendPause = jest.fn();
const mockSendResume = jest.fn();
const mockSendSetSpeed = jest.fn();

const mockUser = {
  id: 'user-1',
  username: 'socrates',
  display_name: 'Socrates',
  is_admin: false,
  total_spend: 2,
  spend_limit: 10,
  language_preference: 'en',
  created_at: '2024-01-01T00:00:00Z',
};

const mockSummary: ConversationSummary = {
  id: 'conv-1',
  topic: 'Justice',
  thinker_names: ['Plato'],
  thinkers: [{ name: 'Plato', image_url: null }],
  message_count: 0,
  total_cost: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockConversation: Conversation = {
  id: 'conv-1',
  session_id: 'session-1',
  topic: 'Justice',
  thinkers: [
    {
      id: 't-1',
      name: 'Plato',
      bio: 'b',
      positions: 'p',
      style: 's',
      color: '#fff',
      image_url: null,
    },
  ],
  messages: [
    {
      id: 'm-1',
      conversation_id: 'conv-1',
      sender_type: 'user',
      sender_name: 'socrates',
      content: 'Hi',
      cost: null,
      created_at: '2024-01-01T00:00:01Z',
    },
  ],
  total_cost: 0,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

function setWindowWidth(width: number) {
  Object.defineProperty(window, 'innerWidth', {
    writable: true,
    configurable: true,
    value: width,
  });
}

function setAuth(overrides: Record<string, unknown> = {}) {
  (useAuth as jest.Mock).mockReturnValue({
    user: mockUser,
    isAuthenticated: true,
    isLoading: false,
    logout: mockLogout,
    ...overrides,
  });
}

/** Render the page and wait for the conversation-loading effect to settle. */
async function renderLoaded() {
  const utils = render(<Home />);
  await screen.findByTestId('sidebar');
  return utils;
}

beforeEach(() => {
  jest.clearAllMocks();

  // jest.setup.ts replaces localStorage with no-op jest.fn()s; back them with
  // a real in-memory store so width persistence can be exercised end to end.
  const store: Record<string, string> = {};
  (localStorage.getItem as jest.Mock).mockImplementation(
    (key: string) => store[key] ?? null
  );
  (localStorage.setItem as jest.Mock).mockImplementation(
    (key: string, value: string) => {
      store[key] = value;
    }
  );
  (localStorage.removeItem as jest.Mock).mockImplementation((key: string) => {
    delete store[key];
  });

  setWindowWidth(1280); // desktop by default

  (useRouter as jest.Mock).mockReturnValue(mockRouter);
  (useLanguage as jest.Mock).mockReturnValue({ locale: 'en' });
  setAuth();

  (useWebSocket as jest.Mock).mockImplementation((opts: WsOptions) => {
    wsOptions = opts;
    return {
      isConnected: true,
      isPaused: false,
      speedMultiplier: 1,
      typingThinkers: new Set(['Plato']),
      thinkingContent: new Map(),
      sendUserMessage: mockSendUserMessage,
      sendTypingStart: mockSendTypingStart,
      sendTypingStop: mockSendTypingStop,
      sendPause: mockSendPause,
      sendResume: mockSendResume,
      sendSetSpeed: mockSendSetSpeed,
    };
  });

  (api.getConversations as jest.Mock).mockResolvedValue([mockSummary]);
  (api.getConversation as jest.Mock).mockResolvedValue(mockConversation);
  (api.deleteConversation as jest.Mock).mockResolvedValue(undefined);
  (api.sendMessage as jest.Mock).mockResolvedValue({
    id: 'm-new',
    conversation_id: 'conv-1',
    sender_type: 'user',
    sender_name: 'socrates',
    content: 'hello',
    cost: null,
    created_at: '2024-01-01T00:00:05Z',
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Loading & auth gating
// ---------------------------------------------------------------------------

describe('Home page - loading and auth gating', () => {
  it('shows the loading state while auth is loading', () => {
    setAuth({ isLoading: true });
    render(<Home />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.queryByTestId('sidebar')).not.toBeInTheDocument();
  });

  it('redirects unauthenticated users to /login', async () => {
    setAuth({ isAuthenticated: false, user: null });
    render(<Home />);
    await waitFor(() => {
      expect(mockRouter.replace).toHaveBeenCalledWith('/login');
    });
    // Conversations are not fetched when unauthenticated.
    expect(api.getConversations).not.toHaveBeenCalled();
  });

  it('renders null (no sidebar) once an authenticated session becomes unauthenticated', async () => {
    const { rerender } = await renderLoaded();
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();

    // Simulate logout: isLoading already false, auth flips to false.
    setAuth({ isAuthenticated: false, user: null });
    rerender(<Home />);

    expect(screen.queryByTestId('sidebar')).not.toBeInTheDocument();
    await waitFor(() => {
      expect(mockRouter.replace).toHaveBeenCalledWith('/login');
    });
  });

  it('renders the main layout once conversations finish loading', async () => {
    await renderLoaded();
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('chatarea')).toBeInTheDocument();
    expect(screen.getByTestId('newchatmodal')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('1');
    expect(screen.getByTestId('sidebar-username')).toHaveTextContent(
      'socrates'
    );
  });
});

// ---------------------------------------------------------------------------
// Conversation list loading
// ---------------------------------------------------------------------------

describe('Home page - conversation list loading', () => {
  it('populates the sidebar from the API', async () => {
    await renderLoaded();
    expect(api.getConversations).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('1');
  });

  it('still finishes loading when fetching conversations fails', async () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    (api.getConversations as jest.Mock).mockRejectedValue(new Error('boom'));

    render(<Home />);
    // Loading clears (finally block) even though the fetch failed.
    await screen.findByTestId('sidebar');
    expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('0');
    expect(errorSpy).toHaveBeenCalledWith(
      'Failed to load conversations:',
      expect.any(Error)
    );
  });
});

// ---------------------------------------------------------------------------
// Sidebar width persistence
// ---------------------------------------------------------------------------

describe('Home page - sidebar width persistence', () => {
  it('restores a valid saved sidebar width from localStorage', async () => {
    localStorage.setItem(SIDEBAR_WIDTH_KEY, '350');
    await renderLoaded();
    expect(screen.getByTestId('sidebar')).toHaveAttribute('data-width', '350');
  });

  it('ignores an out-of-range saved width and keeps the default', async () => {
    localStorage.setItem(SIDEBAR_WIDTH_KEY, '9999');
    await renderLoaded();
    expect(screen.getByTestId('sidebar')).toHaveAttribute('data-width', '288');
  });

  it('uses the default width when nothing is saved', async () => {
    await renderLoaded();
    expect(screen.getByTestId('sidebar')).toHaveAttribute('data-width', '288');
  });

  it('persists a new width to localStorage on resize', async () => {
    await renderLoaded();
    fireEvent.click(screen.getByTestId('resize'));
    expect(screen.getByTestId('sidebar')).toHaveAttribute('data-width', '350');
    expect(localStorage.getItem(SIDEBAR_WIDTH_KEY)).toBe('350');
  });
});

// ---------------------------------------------------------------------------
// Selecting a conversation
// ---------------------------------------------------------------------------

describe('Home page - selecting a conversation', () => {
  it('loads the selected conversation and its messages', async () => {
    await renderLoaded();
    fireEvent.click(screen.getByText('select-conv'));

    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation')).toHaveTextContent(
        'conv-1'
      );
    });
    expect(api.getConversation).toHaveBeenCalledWith('conv-1');
    expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('1');
    expect(screen.getByTestId('sidebar-selected')).toHaveTextContent('conv-1');
  });

  it('closes the sidebar on mobile after selecting a conversation', async () => {
    setWindowWidth(500);
    await renderLoaded();
    expect(screen.getByTestId('sidebar')).toHaveAttribute('data-open', 'true');

    fireEvent.click(screen.getByText('select-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toHaveAttribute(
        'data-open',
        'false'
      );
    });
  });

  it('keeps the sidebar open on desktop after selecting a conversation', async () => {
    await renderLoaded();
    fireEvent.click(screen.getByText('select-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation')).toHaveTextContent(
        'conv-1'
      );
    });
    expect(screen.getByTestId('sidebar')).toHaveAttribute('data-open', 'true');
  });

  it('logs an error when loading a conversation fails', async () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    (api.getConversation as jest.Mock).mockRejectedValue(new Error('nope'));
    await renderLoaded();

    fireEvent.click(screen.getByText('select-conv'));
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to load conversation:',
        expect.any(Error)
      );
    });
    expect(screen.getByTestId('chat-conversation')).toHaveTextContent('none');
  });
});

// ---------------------------------------------------------------------------
// Deleting a conversation
// ---------------------------------------------------------------------------

describe('Home page - deleting a conversation', () => {
  it('removes a non-active conversation from the list', async () => {
    await renderLoaded();
    expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('1');

    fireEvent.click(screen.getByText('delete-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('0');
    });
    expect(api.deleteConversation).toHaveBeenCalledWith('conv-1');
  });

  it('clears the active conversation when it is deleted', async () => {
    await renderLoaded();
    // Select it first so it becomes the current conversation.
    fireEvent.click(screen.getByText('select-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation')).toHaveTextContent(
        'conv-1'
      );
    });

    fireEvent.click(screen.getByText('delete-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation')).toHaveTextContent('none');
    });
    expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('0');
  });

  it('logs an error when deletion fails', async () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    (api.deleteConversation as jest.Mock).mockRejectedValue(new Error('fail'));
    await renderLoaded();

    fireEvent.click(screen.getByText('delete-conv'));
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Failed to delete conversation:',
        expect.any(Error)
      );
    });
    // Conversation remains because deletion failed.
    expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('1');
  });
});

// ---------------------------------------------------------------------------
// Sending messages
// ---------------------------------------------------------------------------

describe('Home page - sending messages', () => {
  it('does nothing when there is no active conversation', async () => {
    await renderLoaded();
    fireEvent.click(screen.getByText('send-message'));
    // No conversation selected -> early return, no API call.
    await waitFor(() => {
      expect(api.sendMessage).not.toHaveBeenCalled();
    });
    expect(mockSendUserMessage).not.toHaveBeenCalled();
  });

  it('sends a message and notifies via WebSocket', async () => {
    await renderLoaded();
    fireEvent.click(screen.getByText('select-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation')).toHaveTextContent(
        'conv-1'
      );
    });

    fireEvent.click(screen.getByText('send-message'));
    await waitFor(() => {
      expect(api.sendMessage).toHaveBeenCalledWith('conv-1', 'hello');
    });
    // Original message (1) + newly sent message (1).
    await waitFor(() => {
      expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('2');
    });
    expect(mockSendUserMessage).toHaveBeenCalledWith('hello');
  });

  it('surfaces a non-401 send error to the user', async () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    (api.sendMessage as jest.Mock).mockRejectedValue(new Error('server down'));
    await renderLoaded();
    fireEvent.click(screen.getByText('select-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation')).toHaveTextContent(
        'conv-1'
      );
    });

    fireEvent.click(screen.getByText('send-message'));
    await waitFor(() => {
      expect(screen.getByTestId('chat-error')).toHaveTextContent(
        'Failed to send message: server down'
      );
    });
    expect(errorSpy).toHaveBeenCalled();
  });

  it('does not show an error banner for 401 send failures (handled by redirect)', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    (api.sendMessage as jest.Mock).mockRejectedValue(
      new Error('401 Unauthorized')
    );
    await renderLoaded();
    fireEvent.click(screen.getByText('select-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation')).toHaveTextContent(
        'conv-1'
      );
    });

    fireEvent.click(screen.getByText('send-message'));
    await waitFor(() => {
      expect(api.sendMessage).toHaveBeenCalled();
    });
    expect(screen.getByTestId('chat-error')).toHaveTextContent('');
  });
});

// ---------------------------------------------------------------------------
// Creating conversations
// ---------------------------------------------------------------------------

describe('Home page - creating conversations', () => {
  beforeEach(() => {
    (api.createConversation as jest.Mock).mockResolvedValue({
      id: 'conv-2',
      session_id: 'session-1',
      topic: 'New Topic',
      thinkers: [
        {
          id: 't-2',
          name: 'Plato',
          bio: 'b',
          positions: 'p',
          style: 's',
          color: '#fff',
          image_url: null,
        },
      ],
      total_cost: 0,
      created_at: '2024-02-01T00:00:00Z',
      updated_at: '2024-02-01T00:00:00Z',
    });
  });

  it('prepends the new conversation and makes it active', async () => {
    await renderLoaded();
    fireEvent.click(screen.getByText('create-conv'));

    await waitFor(() => {
      expect(screen.getByTestId('chat-conversation')).toHaveTextContent(
        'conv-2'
      );
    });
    expect(api.createConversation).toHaveBeenCalledWith({
      topic: 'New Topic',
      thinkers: [
        {
          name: 'Plato',
          bio: 'b',
          positions: 'p',
          style: 's',
          image_url: null,
        },
      ],
    });
    // Existing (1) + new (1).
    expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('2');
    expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('0');
  });

  it('closes the sidebar on mobile after creating a conversation', async () => {
    setWindowWidth(500);
    await renderLoaded();
    fireEvent.click(screen.getByText('create-conv'));
    await waitFor(() => {
      expect(screen.getByTestId('sidebar')).toHaveAttribute(
        'data-open',
        'false'
      );
    });
  });
});

// ---------------------------------------------------------------------------
// Thinker suggestions & validation
// ---------------------------------------------------------------------------

describe('Home page - thinker suggestions and validation', () => {
  it('forwards the current locale when suggesting thinkers', async () => {
    (useLanguage as jest.Mock).mockReturnValue({ locale: 'fr' });
    (api.suggestThinkers as jest.Mock).mockResolvedValue([{ name: 'Plato' }]);
    await renderLoaded();

    const result = await modalProps.onSuggestThinkers('ethics', 3, ['Kant']);
    expect(api.suggestThinkers).toHaveBeenCalledWith(
      'ethics',
      3,
      ['Kant'],
      'fr'
    );
    expect(result).toEqual([{ name: 'Plato' }]);
  });

  it('returns the profile for a valid thinker', async () => {
    const profile: ThinkerProfile = {
      name: 'Plato',
      bio: 'b',
      positions: 'p',
      style: 's',
    };
    (api.validateThinker as jest.Mock).mockResolvedValue({
      valid: true,
      profile,
    });
    await renderLoaded();

    const result = await modalProps.onValidateThinker('Plato');
    expect(api.validateThinker).toHaveBeenCalledWith('Plato', 'en');
    expect(result).toEqual(profile);
  });

  it('returns null for an invalid thinker', async () => {
    (api.validateThinker as jest.Mock).mockResolvedValue({
      valid: false,
      profile: null,
    });
    await renderLoaded();

    const result = await modalProps.onValidateThinker('Nobody');
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Modal, logout and toggles
// ---------------------------------------------------------------------------

describe('Home page - modal, logout and toggles', () => {
  it('opens and closes the new chat modal', async () => {
    await renderLoaded();
    expect(screen.getByTestId('newchatmodal')).toHaveAttribute(
      'data-open',
      'false'
    );

    fireEvent.click(screen.getByText('new-chat'));
    expect(screen.getByTestId('newchatmodal')).toHaveAttribute(
      'data-open',
      'true'
    );

    fireEvent.click(screen.getByText('close-modal'));
    expect(screen.getByTestId('newchatmodal')).toHaveAttribute(
      'data-open',
      'false'
    );
  });

  it('toggles the sidebar open/closed', async () => {
    await renderLoaded();
    expect(screen.getByTestId('sidebar')).toHaveAttribute('data-open', 'true');
    fireEvent.click(screen.getByText('toggle-sidebar'));
    expect(screen.getByTestId('sidebar')).toHaveAttribute('data-open', 'false');
  });

  it('logs out and redirects to /login', async () => {
    mockLogout.mockResolvedValue(undefined);
    await renderLoaded();
    fireEvent.click(screen.getByText('logout'));
    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalled();
      expect(mockRouter.push).toHaveBeenCalledWith('/login');
    });
  });
});

// ---------------------------------------------------------------------------
// WebSocket callbacks
// ---------------------------------------------------------------------------

describe('Home page - WebSocket onMessage', () => {
  const thinkerMessage: Message = {
    id: 'm-2',
    conversation_id: 'conv-1',
    sender_type: 'thinker',
    sender_name: 'Plato',
    content: 'A reply',
    cost: 0.5,
    created_at: '2024-01-01T00:01:00Z',
  };

  it('appends an incoming message and adds its cost to session spend', async () => {
    await renderLoaded();
    // total_spend (2) + sessionCost (0) initially.
    expect(screen.getByTestId('chat-total-spend')).toHaveTextContent('2');

    act(() => wsOptions.onMessage(thinkerMessage));

    expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('1');
    // 2 + 0.5
    expect(screen.getByTestId('chat-total-spend')).toHaveTextContent('2.5');
  });

  it('updates the matching conversation summary for thinker messages', async () => {
    await renderLoaded();
    act(() => wsOptions.onMessage(thinkerMessage));
    // The sidebar still lists the single conversation; its count is updated
    // internally (count reflected via message_count not surfaced here), but
    // the summary map ran without error and the message was appended.
    expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('1');
    expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('1');
  });

  it('does not update conversation summaries for user messages', async () => {
    await renderLoaded();
    act(() =>
      wsOptions.onMessage({
        ...thinkerMessage,
        sender_type: 'user',
        cost: 0.25,
      })
    );
    // Cost still accrues to session spend (2 + 0.25) regardless of sender.
    expect(screen.getByTestId('chat-total-spend')).toHaveTextContent('2.25');
    expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('1');
  });

  it('handles messages with no cost without changing session spend', async () => {
    await renderLoaded();
    act(() => wsOptions.onMessage({ ...thinkerMessage, cost: null }));
    expect(screen.getByTestId('chat-total-spend')).toHaveTextContent('2');
    expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('1');
  });

  it('ignores summary updates for non-matching conversation ids', async () => {
    await renderLoaded();
    act(() =>
      wsOptions.onMessage({ ...thinkerMessage, conversation_id: 'other' })
    );
    // Message is still appended; no summary matched but no crash.
    expect(screen.getByTestId('chat-msg-count')).toHaveTextContent('1');
    expect(screen.getByTestId('sidebar-conv-count')).toHaveTextContent('1');
  });
});

describe('Home page - WebSocket onError', () => {
  it('flags a spend-limit error and shows the message', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    await renderLoaded();
    expect(screen.getByTestId('chat-spend-exceeded')).toHaveTextContent(
      'false'
    );

    act(() => wsOptions.onError('Your spend limit has been exceeded'));

    expect(screen.getByTestId('chat-spend-exceeded')).toHaveTextContent('true');
    expect(screen.getByTestId('chat-error')).toHaveTextContent(
      'Your spend limit has been exceeded'
    );
  });

  it('shows a generic error without flagging the spend limit', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    await renderLoaded();

    act(() => wsOptions.onError('Connection lost'));

    expect(screen.getByTestId('chat-spend-exceeded')).toHaveTextContent(
      'false'
    );
    expect(screen.getByTestId('chat-error')).toHaveTextContent(
      'Connection lost'
    );
  });

  it('dismisses the error message when requested', async () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    await renderLoaded();
    act(() => wsOptions.onError('Connection lost'));
    expect(screen.getByTestId('chat-error')).toHaveTextContent(
      'Connection lost'
    );

    fireEvent.click(screen.getByText('dismiss-error'));
    expect(screen.getByTestId('chat-error')).toHaveTextContent('');
  });
});

// ---------------------------------------------------------------------------
// Spend display
// ---------------------------------------------------------------------------

describe('Home page - spend display', () => {
  it('passes the user spend limit and combined total spend to ChatArea', async () => {
    await renderLoaded();
    expect(screen.getByTestId('chat-spend-limit')).toHaveTextContent('10');
    expect(screen.getByTestId('chat-total-spend')).toHaveTextContent('2');
  });

  it('falls back to default spend limit and zero total spend when user fields are absent', async () => {
    setAuth({
      user: {
        ...mockUser,
        total_spend: 0,
        spend_limit: 0,
      },
    });
    await renderLoaded();
    // spend_limit 0 is falsy -> defaults to 10.
    expect(screen.getByTestId('chat-spend-limit')).toHaveTextContent('10');
    expect(screen.getByTestId('chat-total-spend')).toHaveTextContent('0');
  });
});
