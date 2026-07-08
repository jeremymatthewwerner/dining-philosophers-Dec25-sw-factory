/**
 * Integration-gap coverage for the real-time WebSocket hook.
 *
 * These tests exercise the WebSocket message-handling paths that were not
 * covered by the primary useWebSocket suite:
 *   - `thinker_thinking` streaming-preview updates (thinkingContent map)
 *   - `speed_changed` server-driven speed multiplier updates
 *   - `sendSetSpeed()` client command
 *   - cross-conversation message filtering (stale messages after a switch)
 *   - `onopen` firing after the connection is no longer active
 *
 * Focus: integration-gaps (issue #1012).
 */
import { renderHook, act, waitFor, createThinkerMessage } from '@/test-utils';
import { useWebSocket } from '@/hooks/useWebSocket';

// Mock the api module so getAccessToken returns a stable token.
jest.mock('@/lib/api', () => ({
  getAccessToken: jest.fn(() => 'mock-jwt-token'),
}));

import * as api from '@/lib/api';

// Minimal mock WebSocket mirroring the primary suite's harness.
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  send = jest.fn();
  close = jest.fn();

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  simulateMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(
        new MessageEvent('message', { data: JSON.stringify(data) })
      );
    }
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }
}

let mockWsInstance: MockWebSocket;

const createMockedWebSocket = () => {
  const MockedWs = jest.fn(() => mockWsInstance) as unknown as typeof WebSocket;
  Object.defineProperty(MockedWs, 'CONNECTING', { value: 0 });
  Object.defineProperty(MockedWs, 'OPEN', { value: 1 });
  Object.defineProperty(MockedWs, 'CLOSING', { value: 2 });
  Object.defineProperty(MockedWs, 'CLOSED', { value: 3 });
  return MockedWs;
};

beforeEach(() => {
  jest.useFakeTimers();
  mockWsInstance = new MockWebSocket();
  global.WebSocket = createMockedWebSocket();
  (api.getAccessToken as jest.Mock).mockReturnValue('mock-jwt-token');
});

afterEach(() => {
  jest.useRealTimers();
  jest.clearAllMocks();
});

describe('useWebSocket integration gaps', () => {
  describe('thinker_thinking streaming preview', () => {
    it('populates thinkingContent and calls onThinkerThinking', async () => {
      const onThinkerThinking = jest.fn();
      const { result } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
          onThinkerThinking,
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      act(() => {
        mockWsInstance.simulateMessage({
          type: 'thinker_thinking',
          sender_name: 'Kant',
          content: 'Considering the categorical imperative...',
        });
      });

      await waitFor(() => {
        expect(result.current.thinkingContent.get('Kant')).toBe(
          'Considering the categorical imperative...'
        );
        expect(onThinkerThinking).toHaveBeenCalledWith(
          'Kant',
          'Considering the categorical imperative...'
        );
      });
    });

    it('ignores thinker_thinking messages that lack content', async () => {
      const onThinkerThinking = jest.fn();
      const { result } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
          onThinkerThinking,
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      // No `content` field -> the guard short-circuits and nothing updates.
      act(() => {
        mockWsInstance.simulateMessage({
          type: 'thinker_thinking',
          sender_name: 'Kant',
        });
      });

      expect(result.current.thinkingContent.size).toBe(0);
      expect(onThinkerThinking).not.toHaveBeenCalled();
    });

    it('clears thinkingContent for a thinker when it stops typing', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      act(() => {
        mockWsInstance.simulateMessage({
          type: 'thinker_thinking',
          sender_name: 'Kant',
          content: 'A preview',
        });
      });

      await waitFor(() => {
        expect(result.current.thinkingContent.has('Kant')).toBe(true);
      });

      act(() => {
        mockWsInstance.simulateMessage({
          type: 'thinker_stopped_typing',
          sender_name: 'Kant',
        });
      });

      await waitFor(() => {
        expect(result.current.thinkingContent.has('Kant')).toBe(false);
      });
    });
  });

  describe('speed_changed updates', () => {
    it('updates speedMultiplier from a speed_changed message', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      expect(result.current.speedMultiplier).toBe(1.0);

      act(() => {
        mockWsInstance.simulateMessage({
          type: 'speed_changed',
          conversation_id: 'conv-123',
          speed_multiplier: 6,
        });
      });

      await waitFor(() => {
        expect(result.current.speedMultiplier).toBe(6);
      });
    });

    it('accepts a speed_multiplier of 0 (uses !== undefined guard)', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      act(() => {
        mockWsInstance.simulateMessage({
          type: 'speed_changed',
          conversation_id: 'conv-123',
          speed_multiplier: 0,
        });
      });

      await waitFor(() => {
        expect(result.current.speedMultiplier).toBe(0);
      });
    });

    it('ignores speed_changed messages without a multiplier', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      act(() => {
        mockWsInstance.simulateMessage({
          type: 'speed_changed',
          conversation_id: 'conv-123',
        });
      });

      // Multiplier stays at the default because the guard rejects undefined.
      expect(result.current.speedMultiplier).toBe(1.0);
    });
  });

  describe('sendSetSpeed command', () => {
    it('sends a set_speed message with the requested multiplier', async () => {
      const { result } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      act(() => {
        result.current.sendSetSpeed(2.5);
      });

      expect(mockWsInstance.send).toHaveBeenCalledWith(
        JSON.stringify({
          type: 'set_speed',
          conversation_id: 'conv-123',
          speed_multiplier: 2.5,
        })
      );
    });

    it('does not send set_speed when the socket is not open', () => {
      const { result } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
        })
      );

      // Socket never opened -> readyState is CONNECTING, so send is skipped.
      act(() => {
        result.current.sendSetSpeed(3);
      });

      expect(mockWsInstance.send).not.toHaveBeenCalled();
    });
  });

  describe('cross-conversation message filtering', () => {
    it('ignores messages tagged with a different conversation_id', async () => {
      const onMessage = jest.fn();
      renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
          onMessage,
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      // A message for a stale/other conversation must be dropped.
      const staleMessage = createThinkerMessage({
        conversation_id: 'conv-999',
      });
      act(() => {
        mockWsInstance.simulateMessage(staleMessage);
      });

      expect(onMessage).not.toHaveBeenCalled();
    });

    it('still processes messages that omit conversation_id', async () => {
      const onThinkerTyping = jest.fn();
      renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
          onThinkerTyping,
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      // No conversation_id -> the filter guard is skipped, message is handled.
      act(() => {
        mockWsInstance.simulateMessage({
          type: 'thinker_typing',
          sender_name: 'Plato',
        });
      });

      await waitFor(() => {
        expect(onThinkerTyping).toHaveBeenCalledWith('Plato');
      });
    });
  });

  describe('partial thinker message fields', () => {
    it('applies fallbacks when optional message fields are missing', async () => {
      const onMessage = jest.fn();
      renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
          onMessage,
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      // A thinker message with only the required discriminator fields.
      // sender_name/content/cost/timestamp are all absent -> fallbacks apply.
      act(() => {
        mockWsInstance.simulateMessage({
          type: 'message',
          sender_type: 'thinker',
          message_id: 'msg-1',
          conversation_id: 'conv-123',
        });
      });

      await waitFor(() => {
        expect(onMessage).toHaveBeenCalledTimes(1);
      });
      const delivered = onMessage.mock.calls[0][0];
      expect(delivered.id).toBe('msg-1');
      expect(delivered.sender_name).toBeNull();
      expect(delivered.content).toBe('');
      expect(delivered.cost).toBeNull();
      // Missing timestamp falls back to a generated ISO string.
      expect(typeof delivered.created_at).toBe('string');
      expect(delivered.created_at.length).toBeGreaterThan(0);
    });

    it('does not deliver a message when sender_type is not thinker', async () => {
      const onMessage = jest.fn();
      renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
          onMessage,
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      act(() => {
        mockWsInstance.simulateMessage({
          type: 'message',
          sender_type: 'user',
          message_id: 'msg-2',
          conversation_id: 'conv-123',
        });
      });

      expect(onMessage).not.toHaveBeenCalled();
    });

    it('falls back to "Unknown error" for an error message without content', async () => {
      const onError = jest.fn();
      renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
          onError,
        })
      );

      act(() => {
        mockWsInstance.simulateOpen();
      });

      act(() => {
        mockWsInstance.simulateMessage({
          type: 'error',
          conversation_id: 'conv-123',
        });
      });

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('Unknown error');
      });
    });
  });

  describe('inactive connection handling', () => {
    it('closes the socket if onopen fires after the effect was torn down', () => {
      const { unmount } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
        })
      );

      const instance = mockWsInstance;

      // Unmount marks the connection inactive (isActive = false) and clears the ref.
      unmount();
      instance.close.mockClear();

      // A late onopen event should trigger an immediate close, not state updates.
      act(() => {
        instance.simulateOpen();
      });

      expect(instance.close).toHaveBeenCalled();
    });

    it('ignores a message that arrives after the effect was torn down', () => {
      const onMessage = jest.fn();
      const { unmount } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
          onMessage,
        })
      );

      const instance = mockWsInstance;

      act(() => {
        instance.simulateOpen();
      });

      unmount();

      // A late message on the torn-down connection must be dropped (isActive false).
      act(() => {
        instance.simulateMessage(
          createThinkerMessage({ conversation_id: 'conv-123' })
        );
      });

      expect(onMessage).not.toHaveBeenCalled();
    });

    it('does not schedule a reconnect when close fires after teardown', () => {
      const { unmount } = renderHook(() =>
        useWebSocket({
          conversationId: 'conv-123',
        })
      );

      const instance = mockWsInstance;

      act(() => {
        instance.simulateOpen();
      });

      unmount();
      const wsCtor = global.WebSocket as unknown as jest.Mock;
      wsCtor.mockClear();

      // A late close event on the torn-down connection returns early (isActive
      // is false), so no reconnect timer should be armed.
      act(() => {
        instance.simulateClose();
      });

      act(() => {
        jest.advanceTimersByTime(5000);
      });

      // No new WebSocket was constructed by a reconnect.
      expect(wsCtor).not.toHaveBeenCalled();
    });
  });
});
