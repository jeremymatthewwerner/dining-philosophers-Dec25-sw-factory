'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import type {
  Conversation,
  ConversationSummary,
  Message,
  ThinkerProfile,
  ThinkerSuggestion,
} from '@/types';
import { ChatArea, NewChatModal, Sidebar } from '@/components';
import { useAuth } from '@/contexts';
import { useWebSocket } from '@/hooks';
import * as api from '@/lib/api';

export default function Home() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading, logout } = useAuth();

  // State
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [currentConversation, setCurrentConversation] =
    useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionCost, setSessionCost] = useState(0);
  // Sidebar always starts open - it's the main interface for starting conversations
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [spendLimitExceeded, setSpendLimitExceeded] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Calculate current total spend (user's base spend + this session's cost)
  const userTotalSpend = (user?.total_spend || 0) + sessionCost;
  const userSpendLimit = user?.spend_limit || 10;

  // WebSocket connection
  const {
    isConnected,
    isPaused,
    speedMultiplier,
    typingThinkers,
    thinkingContent,
    sendUserMessage,
    sendTypingStart,
    sendTypingStop,
    sendPause,
    sendResume,
    sendSetSpeed,
  } = useWebSocket({
    conversationId: currentConversation?.id || null,
    onMessage: useCallback((message: Message) => {
      setMessages((prev) => [...prev, message]);
      if (message.cost) {
        setSessionCost((prev) => prev + message.cost!);
      }
      // Update conversation summary in sidebar (only count thinker messages since user messages are free)
      if (message.sender_type === 'thinker') {
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === message.conversation_id
              ? {
                  ...conv,
                  message_count: conv.message_count + 1,
                  total_cost: conv.total_cost + (message.cost || 0),
                  updated_at: message.created_at,
                }
              : conv
          )
        );
      }
    }, []),
    onError: useCallback((errorMessage: string) => {
      // Check if this is a spend limit error
      if (errorMessage.toLowerCase().includes('spend limit')) {
        setSpendLimitExceeded(true);
      }
      // Set generic error message for display
      setErrorMessage(errorMessage);
      console.error('WebSocket error:', errorMessage);
    }, []),
  });

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  // Load conversations when authenticated
  useEffect(() => {
    const loadConversations = async () => {
      if (!isAuthenticated) return;
      try {
        const convs = await api.getConversations();
        setConversations(convs);
      } catch (error) {
        console.error('Failed to load conversations:', error);
      } finally {
        setIsLoading(false);
      }
    };
    if (isAuthenticated) {
      loadConversations();
    }
  }, [isAuthenticated]);

  // Load conversation when selected
  const handleSelectConversation = useCallback(async (id: string) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
      setMessages(conv.messages);
      // Note: sessionCost is not reset - it tracks all spending since page load
      // Only close sidebar on mobile (window width < 1024px)
      if (typeof window !== 'undefined' && window.innerWidth < 1024) {
        setSidebarOpen(false);
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  }, []);

  // Delete conversation
  const handleDeleteConversation = useCallback(
    async (id: string) => {
      try {
        await api.deleteConversation(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (currentConversation?.id === id) {
          setCurrentConversation(null);
          setMessages([]);
        }
      } catch (error) {
        console.error('Failed to delete conversation:', error);
      }
    },
    [currentConversation]
  );

  // Send message
  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!currentConversation) return;

      try {
        const message = await api.sendMessage(currentConversation.id, content);
        setMessages((prev) => [...prev, message]);
        sendUserMessage(content); // Notify via WebSocket
      } catch (error) {
        console.error('Failed to send message:', error);
      }
    },
    [currentConversation, sendUserMessage]
  );

  // Create new conversation
  const handleCreateConversation = useCallback(
    async (
      topic: string,
      thinkers: {
        name: string;
        bio: string;
        positions: string;
        style: string;
        image_url?: string | null;
      }[]
    ) => {
      const conv = await api.createConversation({
        topic,
        thinkers,
      });
      // Update conversations list with summary
      setConversations((prev) => [
        {
          id: conv.id,
          topic: conv.topic,
          thinker_names: conv.thinkers.map((t) => t.name),
          thinkers: conv.thinkers.map((t) => ({
            name: t.name,
            image_url: t.image_url,
          })),
          message_count: 0,
          total_cost: 0,
          created_at: conv.created_at,
          updated_at: conv.created_at, // Use created_at since updated_at may not be in response
        },
        ...prev,
      ]);
      // Set current conversation - add empty messages array since create endpoint doesn't return messages
      setCurrentConversation({ ...conv, messages: [], total_cost: 0 });
      setMessages([]); // New conversation has no messages
      // Only close sidebar on mobile (window width < 1024px)
      if (typeof window !== 'undefined' && window.innerWidth < 1024) {
        setSidebarOpen(false);
      }
    },
    []
  );

  // Suggest thinkers for topic
  const handleSuggestThinkers = useCallback(
    async (
      topic: string,
      count: number = 5,
      exclude: string[] = []
    ): Promise<ThinkerSuggestion[]> => {
      return api.suggestThinkers(topic, count, exclude);
    },
    []
  );

  // Validate custom thinker
  const handleValidateThinker = useCallback(
    async (name: string): Promise<ThinkerProfile | null> => {
      const result = await api.validateThinker(name);
      return result.valid && result.profile ? result.profile : null;
    },
    []
  );

  // Handle logout
  const handleLogout = useCallback(async () => {
    await logout();
    router.push('/login');
  }, [logout, router]);

  if (authLoading || isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-900">
        <div className="text-zinc-500 dark:text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect to login
  }

  return (
    <div className="flex h-screen overflow-hidden bg-zinc-50 dark:bg-zinc-900">
      <Sidebar
        conversations={conversations}
        selectedId={currentConversation?.id || null}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
        onNewChat={() => setModalOpen(true)}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        isConnected={isConnected}
        isPaused={isPaused}
        sessionCost={sessionCost}
        username={user?.username}
        displayName={user?.display_name}
        isAdmin={user?.is_admin}
        onLogout={handleLogout}
      />

      <ChatArea
        conversation={currentConversation}
        messages={messages}
        typingThinkers={Array.from(typingThinkers)}
        thinkingContent={thinkingContent}
        onSendMessage={handleSendMessage}
        onTypingStart={sendTypingStart}
        onTypingStop={sendTypingStop}
        isConnected={isConnected}
        isPaused={isPaused}
        onPause={sendPause}
        onResume={sendResume}
        speedMultiplier={speedMultiplier}
        onSpeedChange={sendSetSpeed}
        userTotalSpend={userTotalSpend}
        userSpendLimit={userSpendLimit}
        spendLimitExceeded={spendLimitExceeded}
        errorMessage={errorMessage}
        onDismissError={() => setErrorMessage('')}
        onSidebarToggle={() => setSidebarOpen(!sidebarOpen)}
        sidebarOpen={sidebarOpen}
      />

      <NewChatModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreate={handleCreateConversation}
        onSuggestThinkers={handleSuggestThinkers}
        onValidateThinker={handleValidateThinker}
      />
    </div>
  );
}
