/**
 * Message component for displaying individual chat messages.
 */

'use client';

import type { ConversationThinker, Message as MessageType } from '@/types';
import { ThinkerAvatar } from './ThinkerAvatar';

export interface MessageProps {
  message: MessageType;
  /** Color for thinker messages */
  thinkerColor?: string;
  /** Thinker data for avatar image */
  thinker?: ConversationThinker;
  /** All thinkers in the conversation for mention detection */
  allThinkers?: ConversationThinker[];
}

// Default colors for thinkers if no color specified
const DEFAULT_THINKER_COLORS = [
  '#3B82F6', // blue
  '#10B981', // emerald
  '#F59E0B', // amber
  '#EF4444', // red
  '#8B5CF6', // violet
  '#EC4899', // pink
];

function getColorFromName(name: string): string {
  const hash = name
    .split('')
    .reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return DEFAULT_THINKER_COLORS[hash % DEFAULT_THINKER_COLORS.length];
}

/**
 * Renders message content with highlighted mentions of thinkers.
 * Mentions are styled with the thinker's color and include their avatar inline.
 */
function renderContentWithMentions(
  content: string,
  thinkers: ConversationThinker[]
): React.ReactNode {
  if (!thinkers || thinkers.length === 0) {
    return content;
  }

  // Build a map of names to thinker data (case-insensitive)
  const thinkerMap = new Map<string, ConversationThinker>();
  thinkers.forEach((t) => {
    thinkerMap.set(t.name.toLowerCase(), t);
    // Also map individual name parts for partial matches (first name, last name, etc.)
    const nameParts = t.name.split(' ');
    nameParts.forEach((part) => {
      if (part.length > 2) {
        thinkerMap.set(part.toLowerCase(), t);
      }
    });
  });

  // Create regex pattern matching any thinker name (case-insensitive)
  const names = Array.from(thinkerMap.keys()).sort(
    (a, b) => b.length - a.length
  ); // Longest first
  if (names.length === 0) return content;

  const pattern = new RegExp(
    `\\b(${names.map(escapeRegex).join('|')})\\b`,
    'gi'
  );

  // Split content by mentions
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(content)) !== null) {
    // Add text before this match
    if (match.index > lastIndex) {
      parts.push(content.slice(lastIndex, match.index));
    }

    // Add the highlighted mention
    const matchedName = match[1];
    const thinker = thinkerMap.get(matchedName.toLowerCase());
    if (thinker) {
      const color = thinker.color || getColorFromName(thinker.name);
      parts.push(
        <span
          key={key++}
          className="inline-flex items-center gap-0.5 font-semibold rounded px-0.5 -mx-0.5"
          style={{
            color,
            backgroundColor: `${color}15`,
          }}
        >
          <ThinkerAvatar
            name={thinker.name}
            imageUrl={thinker.image_url}
            size="xs"
            color={color}
          />
          {matchedName}
        </span>
      );
    } else {
      parts.push(matchedName);
    }

    lastIndex = match.index + matchedName.length;
  }

  // Add remaining text
  if (lastIndex < content.length) {
    parts.push(content.slice(lastIndex));
  }

  return parts.length > 0 ? parts : content;
}

function escapeRegex(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function Message({
  message,
  thinkerColor,
  thinker,
  allThinkers = [],
}: MessageProps) {
  const { sender_type, sender_name, content, cost, created_at } = message;

  const isUser = sender_type === 'user';
  const isSystem = sender_type === 'system';

  // Get color for thinker
  const color =
    thinkerColor || (sender_name ? getColorFromName(sender_name) : '#666');

  // Format timestamp
  const formatTime = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (isSystem) {
    return (
      <div
        className="flex justify-center my-2"
        data-testid="message"
        data-sender-type="system"
      >
        <span className="text-sm text-zinc-500 dark:text-zinc-400 italic">
          {content}
        </span>
      </div>
    );
  }

  return (
    <div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}
      data-testid="message"
      data-sender-type={sender_type}
    >
      {/* Thinker avatar */}
      {!isUser && sender_name && (
        <div className="flex-shrink-0 mr-2 mt-1">
          <ThinkerAvatar
            name={sender_name}
            imageUrl={thinker?.image_url}
            size="md"
            color={color}
          />
        </div>
      )}
      <div
        className={`max-w-[75%] ${
          isUser
            ? 'bg-blue-500 text-white rounded-2xl rounded-br-sm'
            : 'bg-zinc-100 dark:bg-zinc-800 rounded-2xl rounded-bl-sm'
        }`}
      >
        {/* Thinker name header */}
        {!isUser && sender_name && (
          <div
            className="px-4 pt-2 pb-0.5 font-medium text-sm"
            style={{ color }}
            data-testid="thinker-name"
          >
            {sender_name}
          </div>
        )}

        {/* Message content */}
        <div
          className={`px-4 ${!isUser && sender_name ? 'pt-0.5' : 'pt-3'} pb-1 whitespace-pre-wrap`}
        >
          {renderContentWithMentions(content, allThinkers)}
        </div>

        {/* Timestamp and cost */}
        <div
          className={`px-4 pb-2 flex items-center gap-2 text-xs ${
            isUser ? 'text-blue-200' : 'text-zinc-400 dark:text-zinc-500'
          }`}
        >
          <span>{formatTime(created_at)}</span>
          {cost !== null && cost > 0 && (
            <span className="opacity-70">${cost.toFixed(4)}</span>
          )}
        </div>
      </div>
    </div>
  );
}
