/**
 * Status line component for displaying background activity status.
 * Shows research progress, cache retrieval, and other async operations.
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';

export type ResearchStatus = 'pending' | 'in_progress' | 'complete' | 'failed';

export interface ThinkerResearchStatus {
  name: string;
  status: ResearchStatus;
  hasData: boolean;
  updatedAt?: string;
}

export interface StatusLineProps {
  /** List of thinker names to monitor for research status */
  thinkerNames: string[];
  /** API base URL for fetching status */
  apiBaseUrl?: string;
  /** Polling interval in milliseconds (default: 5000) */
  pollInterval?: number;
  /** Whether to show the status line (can be toggled) */
  visible?: boolean;
}

/**
 * Fetches research status for a single thinker
 */
async function fetchThinkerStatus(
  name: string,
  apiBaseUrl: string
): Promise<ThinkerResearchStatus | null> {
  try {
    const response = await fetch(
      `${apiBaseUrl}/api/thinkers/knowledge/${encodeURIComponent(name)}/status`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('access_token') || ''}`,
        },
      }
    );
    if (!response.ok) {
      return null;
    }
    const data = await response.json();
    return {
      name: data.name,
      status: data.status as ResearchStatus,
      hasData: data.has_data,
      updatedAt: data.updated_at,
    };
  } catch {
    return null;
  }
}

export function StatusLine({
  thinkerNames,
  apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  pollInterval = 5000,
  visible = true,
}: StatusLineProps) {
  const { t } = useLanguage();
  const [statuses, setStatuses] = useState<Map<string, ThinkerResearchStatus>>(
    new Map()
  );
  const [isPolling, setIsPolling] = useState(false);

  const fetchAllStatuses = useCallback(async () => {
    if (thinkerNames.length === 0 || isPolling) return;

    setIsPolling(true);
    try {
      const results = await Promise.all(
        thinkerNames.map((name) => fetchThinkerStatus(name, apiBaseUrl))
      );

      const newStatuses = new Map<string, ThinkerResearchStatus>();
      results.forEach((result) => {
        if (result) {
          newStatuses.set(result.name, result);
        }
      });
      setStatuses(newStatuses);
    } finally {
      setIsPolling(false);
    }
  }, [thinkerNames, apiBaseUrl, isPolling]);

  // Initial fetch and continuous polling
  // We always poll while mounted with thinkers - the render logic decides
  // whether to show anything based on current status
  useEffect(() => {
    if (thinkerNames.length === 0) return;

    // Initial fetch
    fetchAllStatuses();

    // Always set up polling - the component will hide itself when not needed
    // This fixes the bug where polling would never start because statuses was
    // empty on first render (hasActiveResearch was always false initially)
    const interval = setInterval(fetchAllStatuses, pollInterval);
    return () => clearInterval(interval);
  }, [thinkerNames, fetchAllStatuses, pollInterval]);

  if (!visible || thinkerNames.length === 0) {
    return null;
  }

  // Determine what to display
  const activeResearch = Array.from(statuses.values()).filter(
    (s) => s.status === 'pending' || s.status === 'in_progress'
  );

  const recentlyCompleted = Array.from(statuses.values()).filter((s) => {
    if (s.status !== 'complete') return false;
    // Show completed items that finished in the last 30 seconds
    if (!s.updatedAt) return false;
    const updatedAt = new Date(s.updatedAt);
    const thirtySecondsAgo = new Date(Date.now() - 30000);
    return updatedAt > thirtySecondsAgo;
  });

  const failedResearch = Array.from(statuses.values()).filter(
    (s) => s.status === 'failed'
  );

  // Don't show if nothing interesting is happening
  if (
    activeResearch.length === 0 &&
    recentlyCompleted.length === 0 &&
    failedResearch.length === 0
  ) {
    return null;
  }

  return (
    <div
      className="px-4 py-2 bg-zinc-100 dark:bg-zinc-800 border-b border-zinc-200 dark:border-zinc-700 text-xs text-zinc-600 dark:text-zinc-400 flex items-center gap-2 flex-wrap"
      data-testid="status-line"
    >
      {/* Active research indicator */}
      {activeResearch.length > 0 && (
        <div className="flex items-center gap-2" data-testid="active-research">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
          </span>
          <span>
            {t.statusLine?.researching ||
              'Researching background information...'}
          </span>
          <span className="text-zinc-500 dark:text-zinc-400">
            ({activeResearch.map((s) => s.name).join(', ')})
          </span>
        </div>
      )}

      {/* Recently completed */}
      {recentlyCompleted.length > 0 && activeResearch.length === 0 && (
        <div
          className="flex items-center gap-2 text-green-600 dark:text-green-400"
          data-testid="research-complete"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3 h-3"
          >
            <path
              fillRule="evenodd"
              d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
              clipRule="evenodd"
            />
          </svg>
          <span>
            {t.statusLine?.researchComplete || 'Background research complete'}
          </span>
        </div>
      )}

      {/* Failed research (shown with warning) */}
      {failedResearch.length > 0 && (
        <div
          className="flex items-center gap-2 text-orange-600 dark:text-orange-400"
          data-testid="research-failed"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3 h-3"
          >
            <path
              fillRule="evenodd"
              d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
              clipRule="evenodd"
            />
          </svg>
          <span>
            {t.statusLine?.researchFailed ||
              'Could not load background research'}
          </span>
        </div>
      )}
    </div>
  );
}
