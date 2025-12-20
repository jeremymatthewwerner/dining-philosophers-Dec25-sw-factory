/**
 * Scrollable message list component.
 */

'use client';

import { useEffect, useRef } from 'react';
import type { ConversationThinker, Message as MessageType } from '@/types';
import { Message } from './Message';
import { ThinkerAvatar } from './ThinkerAvatar';

export interface MessageListProps {
  messages: MessageType[];
  thinkers: ConversationThinker[];
  typingThinkers?: string[];
  /** Map of thinker names to their thinking preview content */
  thinkingContent?: Map<string, string>;
}

export function MessageList({
  messages,
  thinkers,
  typingThinkers = [],
  thinkingContent,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Create a map of thinker data
  const thinkerMap = thinkers.reduce(
    (acc, t) => {
      acc[t.name] = t;
      return acc;
    },
    {} as Record<string, ConversationThinker>
  );

  // Auto-scroll to bottom when new messages arrive or typing status changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, typingThinkers.length]);

  if (messages.length === 0 && typingThinkers.length === 0) {
    return (
      <div
        className="flex-1 flex items-center justify-center text-zinc-400 dark:text-zinc-500"
        data-testid="message-list-empty"
      >
        <p>No messages yet. Start the conversation!</p>
      </div>
    );
  }

  return (
    <div
      className="flex-1 overflow-y-auto px-4 py-4"
      data-testid="message-list"
    >
      {messages.map((msg) => {
        const thinker = msg.sender_name
          ? thinkerMap[msg.sender_name]
          : undefined;
        return (
          <Message
            key={msg.id}
            message={msg}
            thinkerColor={thinker?.color}
            thinker={thinker}
            allThinkers={thinkers}
          />
        );
      })}
      {/* Inline typing indicators for thinkers */}
      {typingThinkers.map((name) => {
        const thinker = thinkerMap[name];
        const thinking = thinkingContent?.get(name);
        return (
          <div
            key={`typing-${name}`}
            className="mb-4 flex items-start gap-3"
            data-testid="thinker-typing-indicator"
          >
            <ThinkerAvatar
              name={name}
              imageUrl={thinker?.image_url}
              size="md"
              color={thinker?.color}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span
                  className="text-sm font-medium"
                  style={{ color: thinker?.color || '#6b7280' }}
                >
                  {name}
                </span>
              </div>
              <div className="bg-zinc-100 dark:bg-zinc-800 rounded-lg px-4 py-3 inline-block">
                <div className="flex items-center gap-2 text-zinc-400 dark:text-zinc-500">
                  <span className="text-sm italic">
                    {thinking || 'Thinking...'}
                  </span>
                  <div className="flex gap-1">
                    <span
                      className="w-1.5 h-1.5 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
                      style={{ animationDelay: '0ms' }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
                      style={{ animationDelay: '150ms' }}
                    />
                    <span
                      className="w-1.5 h-1.5 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
                      style={{ animationDelay: '300ms' }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
