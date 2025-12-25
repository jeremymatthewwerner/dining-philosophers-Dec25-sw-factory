/**
 * Main chat area component combining messages, typing indicator, and input.
 */

'use client';

import { useState } from 'react';
import type { Conversation, Message } from '@/types';
import { exportAsHtml, exportAsMarkdown } from '@/lib/export';
import { MessageInput } from './MessageInput';
import { MessageList } from './MessageList';
import { SpendLimitBanner } from './SpendLimitBanner';
import { ErrorBanner } from './ErrorBanner';

export interface ChatAreaProps {
  conversation: Conversation | null;
  messages: Message[];
  typingThinkers: string[];
  /** Map of thinker names to their thinking preview content */
  thinkingContent?: Map<string, string>;
  onSendMessage: (content: string) => void;
  onTypingStart?: () => void;
  onTypingStop?: () => void;
  isConnected: boolean;
  isPaused?: boolean;
  onPause?: () => void;
  onResume?: () => void;
  /** Speed multiplier (1.0 = normal, 0.5 = fast, 2.0+ = slow) */
  speedMultiplier?: number;
  onSpeedChange?: (multiplier: number) => void;
  /** User's current total spend */
  userTotalSpend?: number;
  /** User's spend limit */
  userSpendLimit?: number;
  /** Whether the spend limit has been exceeded (from WebSocket error) */
  spendLimitExceeded?: boolean;
  /** Generic error message from WebSocket (e.g., billing errors) */
  errorMessage?: string;
  /** Callback to dismiss the error message */
  onDismissError?: () => void;
  /** Callback to toggle the sidebar (mobile only) */
  onSidebarToggle?: () => void;
  /** Whether the sidebar is currently open */
  sidebarOpen?: boolean;
}

// Speed labels for display
const SPEED_LABELS: Record<number, string> = {
  0.5: 'Fast',
  1.0: 'Normal',
  2.0: 'Relaxed',
  4.0: 'Slow',
  6.0: 'Contemplative',
};

function getSpeedLabel(speed: number): string {
  // Find closest match
  const speeds = [0.5, 1.0, 2.0, 4.0, 6.0];
  const closest = speeds.reduce((prev, curr) =>
    Math.abs(curr - speed) < Math.abs(prev - speed) ? curr : prev
  );
  return SPEED_LABELS[closest];
}

export function ChatArea({
  conversation,
  messages,
  typingThinkers,
  thinkingContent,
  onSendMessage,
  onTypingStart,
  onTypingStop,
  isConnected,
  isPaused = false,
  onPause,
  onResume,
  speedMultiplier = 1.0,
  onSpeedChange,
  userTotalSpend = 0,
  userSpendLimit = 10,
  spendLimitExceeded = false,
  errorMessage,
  onDismissError,
  onSidebarToggle,
  sidebarOpen = false,
}: ChatAreaProps) {
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [dismissedWarning, setDismissedWarning] = useState(false);

  // Calculate spend limit status
  const percentUsed =
    userSpendLimit > 0 ? (userTotalSpend / userSpendLimit) * 100 : 0;
  const isNearLimit = percentUsed >= 85 && !spendLimitExceeded;
  const showSpendBanner =
    (isNearLimit && !dismissedWarning) || spendLimitExceeded;

  const handleExportHtml = () => {
    if (conversation) {
      exportAsHtml(conversation, messages);
      setShowExportMenu(false);
    }
  };

  const handleExportMarkdown = () => {
    if (conversation) {
      exportAsMarkdown(conversation, messages);
      setShowExportMenu(false);
    }
  };

  if (!conversation) {
    return (
      <div
        className="flex-1 flex flex-col items-center justify-center bg-zinc-50 dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400"
        data-testid="chat-area-empty"
      >
        <div className="text-center max-w-md px-4">
          <h2 className="text-2xl font-semibold mb-2 text-zinc-900 dark:text-zinc-100">
            Welcome to Dining Philosophers
          </h2>
          <p className="mb-4">
            Start a new conversation to discuss topics with historical and
            contemporary thinkers.
          </p>
          <p className="text-sm">
            Select a conversation from the sidebar or create a new one.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex-1 flex flex-col bg-white dark:bg-zinc-900 min-h-0"
      data-testid="chat-area"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-zinc-700 gap-2 sm:gap-3 bg-white dark:bg-zinc-900 flex-shrink-0 sticky top-0 z-10">
        {/* Left side: Hamburger + Topic */}
        <div className="flex items-center gap-2 sm:gap-3 min-w-0 flex-1">
          {/* Hamburger button - only visible on mobile when sidebar is closed */}
          {onSidebarToggle && !sidebarOpen && (
            <button
              onClick={onSidebarToggle}
              className="lg:hidden p-2 bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors flex-shrink-0 touch-manipulation"
              style={{
                minWidth: '44px',
                minHeight: '44px',
              }}
              aria-label="Open sidebar"
              data-testid="sidebar-toggle"
              title="Open sidebar"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                className="w-5 h-5 text-zinc-700 dark:text-zinc-300"
              >
                <path
                  fillRule="evenodd"
                  d="M3 6.75A.75.75 0 013.75 6h16.5a.75.75 0 010 1.5H3.75A.75.75 0 013 6.75zM3 12a.75.75 0 01.75-.75h16.5a.75.75 0 010 1.5H3.75A.75.75 0 013 12zm0 5.25a.75.75 0 01.75-.75h16.5a.75.75 0 010 1.5H3.75a.75.75 0 01-.75-.75z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          )}
          <div className="min-w-0 flex-1 min-w-[120px]">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 truncate">
              {conversation.topic}
            </h2>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 truncate">
              with {conversation.thinkers.map((t) => t.name).join(', ')}
            </p>
          </div>
        </div>

        {/* Right side: Controls */}
        <div className="flex items-center gap-3 sm:gap-3 flex-shrink-0">
          {/* Speed control */}
          {onSpeedChange && (
            <div
              className="flex items-center gap-2 sm:gap-2"
              data-testid="speed-control"
            >
              <label className="text-xs text-zinc-500 dark:text-zinc-400 whitespace-nowrap hidden sm:inline">
                Pace:
              </label>
              <input
                type="range"
                min="0.5"
                max="6"
                step="0.5"
                value={speedMultiplier}
                onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
                className="w-20 sm:w-24 h-2.5 accent-blue-600 cursor-pointer touch-manipulation"
                style={{
                  minHeight: '44px',
                  padding: '0',
                  margin: '0',
                }}
                title={`Conversation pace: ${getSpeedLabel(speedMultiplier)}`}
                data-testid="speed-slider"
              />
              <span className="text-xs text-zinc-600 dark:text-zinc-300 w-12 sm:w-16 text-center">
                {getSpeedLabel(speedMultiplier)}
              </span>
            </div>
          )}

          {/* Export button */}
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(!showExportMenu)}
              className="flex items-center justify-center gap-1 sm:gap-1.5 px-3 sm:px-3 py-2.5 text-sm rounded-lg transition-colors bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 touch-manipulation"
              style={{
                minWidth: '44px',
                minHeight: '44px',
              }}
              data-testid="export-button"
              title="Export conversation"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-4 h-4"
              >
                <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
                <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
              </svg>
              <span className="hidden sm:inline">Export</span>
            </button>
            {showExportMenu && (
              <>
                {/* Backdrop to close menu */}
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowExportMenu(false)}
                />
                {/* Dropdown menu */}
                <div
                  className="absolute right-0 top-full mt-1 z-20 bg-white dark:bg-zinc-800 rounded-lg shadow-lg border border-zinc-200 dark:border-zinc-700 py-1 min-w-[140px]"
                  data-testid="export-menu"
                >
                  <button
                    onClick={handleExportHtml}
                    className="w-full text-left px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 flex items-center gap-2"
                    data-testid="export-html-option"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="w-4 h-4 text-orange-500"
                    >
                      <path
                        fillRule="evenodd"
                        d="M4.5 2A1.5 1.5 0 003 3.5v13A1.5 1.5 0 004.5 18h11a1.5 1.5 0 001.5-1.5V7.621a1.5 1.5 0 00-.44-1.06l-4.12-4.122A1.5 1.5 0 0011.378 2H4.5zM10 8a.75.75 0 01.75.75v1.5h1.5a.75.75 0 010 1.5h-1.5v1.5a.75.75 0 01-1.5 0v-1.5h-1.5a.75.75 0 010-1.5h1.5v-1.5A.75.75 0 0110 8z"
                        clipRule="evenodd"
                      />
                    </svg>
                    HTML
                  </button>
                  <button
                    onClick={handleExportMarkdown}
                    className="w-full text-left px-4 py-2 text-sm text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-700 flex items-center gap-2"
                    data-testid="export-markdown-option"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="w-4 h-4 text-blue-500"
                    >
                      <path
                        fillRule="evenodd"
                        d="M4.5 2A1.5 1.5 0 003 3.5v13A1.5 1.5 0 004.5 18h11a1.5 1.5 0 001.5-1.5V7.621a1.5 1.5 0 00-.44-1.06l-4.12-4.122A1.5 1.5 0 0011.378 2H4.5zM8 12.25a.75.75 0 01.75-.75h2.5a.75.75 0 010 1.5h-2.5a.75.75 0 01-.75-.75z"
                        clipRule="evenodd"
                      />
                    </svg>
                    Markdown
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Pause/Resume button */}
          {(onPause || onResume) && (
            <button
              onClick={isPaused ? onResume : onPause}
              className={`flex items-center justify-center gap-1 sm:gap-1.5 px-3 sm:px-3 py-2.5 text-sm rounded-lg transition-colors touch-manipulation ${
                isPaused
                  ? 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400 dark:hover:bg-green-900/50'
                  : 'bg-orange-100 text-orange-700 hover:bg-orange-200 dark:bg-orange-900/30 dark:text-orange-400 dark:hover:bg-orange-900/50'
              }`}
              style={{
                minWidth: '44px',
                minHeight: '44px',
              }}
              data-testid="pause-resume-button"
              title={isPaused ? 'Resume thinkers' : 'Pause thinkers'}
            >
              {isPaused ? (
                <>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-4 h-4"
                  >
                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                  </svg>
                  <span className="hidden sm:inline">Resume</span>
                </>
              ) : (
                <>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-4 h-4"
                  >
                    <path d="M5.75 3a.75.75 0 00-.75.75v12.5c0 .414.336.75.75.75h1.5a.75.75 0 00.75-.75V3.75A.75.75 0 007.25 3h-1.5zM12.75 3a.75.75 0 00-.75.75v12.5c0 .414.336.75.75.75h1.5a.75.75 0 00.75-.75V3.75a.75.75 0 00-.75-.75h-1.5z" />
                  </svg>
                  <span className="hidden sm:inline">Pause</span>
                </>
              )}
            </button>
          )}
          {!isConnected && (
            <span
              className="text-xs text-orange-500"
              data-testid="connection-status"
            >
              Reconnecting...
            </span>
          )}
        </div>
      </div>

      {/* Generic error banner */}
      {errorMessage && (
        <ErrorBanner message={errorMessage} onDismiss={onDismissError} />
      )}

      {/* Spend limit warning/error banner */}
      {showSpendBanner && (
        <SpendLimitBanner
          currentSpend={userTotalSpend}
          spendLimit={userSpendLimit}
          isExceeded={spendLimitExceeded}
          onDismiss={isNearLimit ? () => setDismissedWarning(true) : undefined}
        />
      )}

      {/* Messages */}
      <MessageList
        messages={messages}
        thinkers={conversation.thinkers}
        typingThinkers={typingThinkers}
        thinkingContent={thinkingContent}
      />

      {/* Input */}
      <MessageInput
        onSend={onSendMessage}
        onTypingStart={onTypingStart}
        onTypingStop={onTypingStop}
        disabled={!isConnected || spendLimitExceeded}
        placeholder={
          spendLimitExceeded
            ? 'Spend limit reached - contact admin to continue'
            : isConnected
              ? `Message ${conversation.thinkers.map((t) => t.name).join(', ')}...`
              : 'Connecting...'
        }
      />
    </div>
  );
}
