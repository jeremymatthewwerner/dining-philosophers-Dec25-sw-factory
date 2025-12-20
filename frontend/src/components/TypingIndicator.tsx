/**
 * Typing indicator showing which thinkers are currently typing.
 * Can optionally show what each thinker is thinking about.
 */

'use client';

export interface TypingIndicatorProps {
  /** Names of thinkers currently typing */
  typingThinkers: string[];
  /** Map of thinker names to their thinking preview content */
  thinkingContent?: Map<string, string>;
}

export function TypingIndicator({
  typingThinkers,
  thinkingContent,
}: TypingIndicatorProps) {
  if (typingThinkers.length === 0) {
    return null;
  }

  // If we have thinking content, show individual indicators for each thinker
  const hasThinkingContent = thinkingContent && thinkingContent.size > 0;

  if (hasThinkingContent) {
    return (
      <div className="space-y-2" data-testid="typing-indicator">
        {typingThinkers.map((thinker) => {
          const thinking = thinkingContent.get(thinker);
          return (
            <div
              key={thinker}
              className="flex items-center gap-2 px-4 py-2 text-sm"
            >
              <div className="flex gap-1">
                <span
                  className="w-2 h-2 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
                  style={{ animationDelay: '0ms' }}
                />
                <span
                  className="w-2 h-2 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
                  style={{ animationDelay: '150ms' }}
                />
                <span
                  className="w-2 h-2 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
                  style={{ animationDelay: '300ms' }}
                />
              </div>
              <span className="font-medium text-zinc-700 dark:text-zinc-300">
                {thinker}
              </span>
              {thinking ? (
                <span className="italic text-zinc-500 dark:text-zinc-400">
                  {thinking}
                </span>
              ) : (
                <span className="text-zinc-500 dark:text-zinc-400">
                  is thinking...
                </span>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  // Fallback to simple format if no thinking content
  const formatNames = (): string => {
    if (typingThinkers.length === 1) {
      return `${typingThinkers[0]} is thinking...`;
    }
    if (typingThinkers.length === 2) {
      return `${typingThinkers[0]} and ${typingThinkers[1]} are thinking...`;
    }
    return `${typingThinkers.slice(0, -1).join(', ')}, and ${
      typingThinkers[typingThinkers.length - 1]
    } are thinking...`;
  };

  return (
    <div
      className="flex items-center gap-2 px-4 py-2 text-sm text-zinc-500 dark:text-zinc-400"
      data-testid="typing-indicator"
    >
      <div className="flex gap-1">
        <span
          className="w-2 h-2 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
          style={{ animationDelay: '0ms' }}
        />
        <span
          className="w-2 h-2 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
          style={{ animationDelay: '150ms' }}
        />
        <span
          className="w-2 h-2 bg-zinc-400 dark:bg-zinc-500 rounded-full animate-bounce"
          style={{ animationDelay: '300ms' }}
        />
      </div>
      <span>{formatNames()}</span>
    </div>
  );
}
