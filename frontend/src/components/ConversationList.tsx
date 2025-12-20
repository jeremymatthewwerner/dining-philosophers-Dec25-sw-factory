/**
 * Conversation list component showing previous chats.
 */

'use client';

import type { ConversationSummary } from '@/types';
import { ThinkerAvatar } from './ThinkerAvatar';

export interface ConversationListProps {
  conversations: ConversationSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete?: (id: string) => void;
  isConnected?: boolean;
  isPaused?: boolean;
}

export function ConversationList({
  conversations,
  selectedId,
  onSelect,
  onDelete,
  isConnected = false,
  isPaused = false,
}: ConversationListProps) {
  // Get status for a conversation
  const getStatus = (convId: string): 'running' | 'paused' | 'inactive' => {
    if (convId !== selectedId) return 'inactive';
    if (!isConnected) return 'inactive';
    return isPaused ? 'paused' : 'running';
  };
  // Format relative time
  const formatTime = (isoString: string): string => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  if (conversations.length === 0) {
    return (
      <div
        className="px-3 py-8 text-center text-sm text-zinc-500 dark:text-zinc-400"
        data-testid="conversation-list-empty"
      >
        No conversations yet
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1" data-testid="conversation-list">
      {conversations.map((conv) => (
        <div
          key={conv.id}
          className={`group relative px-3 py-2 rounded-lg cursor-pointer transition-colors ${
            selectedId === conv.id
              ? 'bg-zinc-200 dark:bg-zinc-700'
              : 'hover:bg-zinc-100 dark:hover:bg-zinc-800'
          }`}
          onClick={() => onSelect(conv.id)}
          data-testid="conversation-item"
          data-selected={selectedId === conv.id}
        >
          <div className="flex justify-between items-start mb-1 gap-2">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              {/* Status indicator */}
              <span
                className={`flex-shrink-0 w-2 h-2 rounded-full ${
                  getStatus(conv.id) === 'running'
                    ? 'bg-green-500 animate-pulse'
                    : getStatus(conv.id) === 'paused'
                      ? 'bg-yellow-500'
                      : 'bg-zinc-400 dark:bg-zinc-600'
                }`}
                title={
                  getStatus(conv.id) === 'running'
                    ? 'Thinkers are active'
                    : getStatus(conv.id) === 'paused'
                      ? 'Conversation paused'
                      : 'Inactive'
                }
                data-testid="status-indicator"
              />
              <h3
                className="font-medium text-sm text-zinc-900 dark:text-zinc-100 truncate"
                title={conv.topic}
              >
                {conv.topic}
              </h3>
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              <span className="text-xs text-zinc-400 dark:text-zinc-500">
                {formatTime(conv.updated_at)}
              </span>
              {/* Delete button - inline with timestamp */}
              {onDelete && (
                <button
                  className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-zinc-300 dark:hover:bg-zinc-600 transition-opacity"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(conv.id);
                  }}
                  aria-label="Delete conversation"
                  data-testid="delete-conversation"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-4 h-4 text-zinc-500 dark:text-zinc-400"
                  >
                    <path
                      fillRule="evenodd"
                      d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1 mt-1">
            {conv.thinkers.slice(0, 3).map((thinker) => (
              <ThinkerAvatar
                key={thinker.name}
                name={thinker.name}
                imageUrl={thinker.image_url}
                size="sm"
              />
            ))}
            {conv.thinkers.length > 3 && (
              <span className="text-xs text-zinc-400 dark:text-zinc-500 ml-1">
                +{conv.thinkers.length - 3}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs text-zinc-400 dark:text-zinc-500">
              {conv.message_count} thinker messages
            </span>
            {conv.total_cost > 0 && (
              <span className="text-xs text-zinc-400 dark:text-zinc-500">
                ${conv.total_cost.toFixed(3)}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
