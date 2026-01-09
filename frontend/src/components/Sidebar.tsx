/**
 * Sidebar component with conversation list and new chat button.
 */

'use client';

import Image from 'next/image';
import { useState } from 'react';
import type { ConversationSummary } from '@/types';
import { ConversationList } from './ConversationList';
import { CostMeter } from './CostMeter';
import { BuildInfo } from './BuildInfo';
import { FeedbackModal } from './FeedbackModal';
import { UserMenu } from './UserMenu';
import { generateBugReportUrl } from '@/utils/bugReport';
import { useLanguage } from '@/contexts/LanguageContext';

export interface SidebarProps {
  conversations: ConversationSummary[];
  selectedId: string | null;
  onSelectConversation: (id: string) => void;
  onDeleteConversation?: (id: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
  onToggle: () => void;
  isConnected?: boolean;
  isPaused?: boolean;
  sessionCost?: number;
  username?: string;
  displayName?: string | null;
  isAdmin?: boolean;
  onLogout?: () => void;
  /** Width in pixels for desktop view. Ignored on mobile. */
  width?: number;
}

export function Sidebar({
  conversations,
  selectedId,
  onSelectConversation,
  onDeleteConversation,
  onNewChat,
  isOpen,
  onToggle,
  isConnected = false,
  isPaused = false,
  sessionCost = 0,
  username,
  displayName,
  isAdmin = false,
  onLogout,
  width,
}: SidebarProps) {
  const { t } = useLanguage();
  const [isFeedbackModalOpen, setIsFeedbackModalOpen] = useState(false);

  // Generate bug report URL with user info
  const bugReportUrl = generateBugReportUrl({ username, displayName });

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={onToggle}
          data-testid="sidebar-overlay"
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-30 w-72 lg:w-auto bg-zinc-50 dark:bg-zinc-950 border-r lg:border-r-0 border-zinc-200 dark:border-zinc-800 transform transition-transform duration-300 ease-in-out lg:translate-x-0 flex-shrink-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={width ? { width: `${width}px` } : undefined}
        data-testid="sidebar"
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="px-4 py-4 border-b border-zinc-200 dark:border-zinc-800">
            <div className="flex items-center justify-between">
              <a
                href="https://github.com/jeremymatthewwerner/dining-philosophers-Dec25-sw-factory"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-lg font-bold text-zinc-900 dark:text-zinc-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
              >
                <Image
                  src="/icon.png"
                  alt="Dijkstra"
                  width={32}
                  height={32}
                  className="rounded-full"
                />
                {t.sidebar.appTitle}
              </a>
              <button
                onClick={onToggle}
                className="lg:hidden p-2 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded-lg transition-colors"
                aria-label={t.sidebar.closeSidebar}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                  className="w-5 h-5 text-zinc-500"
                >
                  <path
                    fillRule="evenodd"
                    d="M5.47 5.47a.75.75 0 011.06 0L12 10.94l5.47-5.47a.75.75 0 111.06 1.06L13.06 12l5.47 5.47a.75.75 0 11-1.06 1.06L12 13.06l-5.47 5.47a.75.75 0 01-1.06-1.06L10.94 12 5.47 6.53a.75.75 0 010-1.06z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            </div>
            <CostMeter totalCost={sessionCost} className="mt-2" />
          </div>

          {/* New chat button */}
          <div className="px-3 py-3">
            <button
              onClick={onNewChat}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-zinc-950 transition-colors"
              data-testid="new-chat-button"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className="w-5 h-5"
              >
                <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
              </svg>
              {t.sidebar.newConversation}
            </button>
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto px-3 pb-3">
            <ConversationList
              conversations={conversations}
              selectedId={selectedId}
              onSelect={onSelectConversation}
              onDelete={onDeleteConversation}
              isConnected={isConnected}
              isPaused={isPaused}
            />
          </div>

          {/* Footer with user info */}
          <div className="border-t border-zinc-200 dark:border-zinc-800">
            <div className="px-4 py-3">
              {username ? (
                <UserMenu
                  username={username}
                  displayName={displayName}
                  isAdmin={isAdmin}
                  bugReportUrl={bugReportUrl}
                  onLogout={onLogout}
                  onFeedbackClick={() => setIsFeedbackModalOpen(true)}
                />
              ) : (
                <p className="text-xs text-zinc-400 dark:text-zinc-500 text-center">
                  {t.sidebar.tagline}
                </p>
              )}
            </div>
            {/* Build timestamp */}
            <BuildInfo />
          </div>
        </div>
      </aside>

      {/* Feedback Modal */}
      <FeedbackModal
        isOpen={isFeedbackModalOpen}
        onClose={() => setIsFeedbackModalOpen(false)}
      />
    </>
  );
}
