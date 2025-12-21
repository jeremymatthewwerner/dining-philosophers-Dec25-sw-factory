/**
 * Modal for creating a new conversation.
 */

'use client';

import {
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import type { ThinkerProfile, ThinkerSuggestion } from '@/types';
import { type SelectedThinker, ThinkerSelector } from './ThinkerSelector';

export interface ThinkerData {
  name: string;
  bio: string;
  positions: string;
  style: string;
  image_url?: string | null;
}

export interface NewChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (topic: string, thinkers: ThinkerData[]) => Promise<void>;
  onSuggestThinkers: (
    topic: string,
    count?: number,
    exclude?: string[]
  ) => Promise<ThinkerSuggestion[]>;
  onValidateThinker: (name: string) => Promise<ThinkerProfile | null>;
}

export function NewChatModal({
  isOpen,
  onClose,
  onCreate,
  onSuggestThinkers,
  onValidateThinker,
}: NewChatModalProps) {
  const [step, setStep] = useState<'topic' | 'thinkers'>('topic');
  const [topic, setTopic] = useState('');
  const [suggestions, setSuggestions] = useState<ThinkerSuggestion[]>([]);
  const [selectedThinkers, setSelectedThinkers] = useState<SelectedThinker[]>(
    []
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isFetchingMore, setIsFetchingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && step === 'topic') {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, step]);

  // Reset state when closed
  useEffect(() => {
    if (!isOpen) {
      setStep('topic');
      setTopic('');
      setSuggestions([]);
      setSelectedThinkers([]);
      setError(null);
    }
  }, [isOpen]);

  const handleTopicSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      if (!topic.trim()) return;

      setIsLoading(true);
      setError(null);

      try {
        const results = await onSuggestThinkers(topic.trim(), 5);
        setSuggestions(results);
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to get thinker suggestions';
        setError(message);
        // Still proceed with empty suggestions - user can add thinkers manually
        setSuggestions([]);
      } finally {
        setIsLoading(false);
        // Always advance to thinker selection step, even if suggestions failed
        setStep('thinkers');
      }
    },
    [topic, onSuggestThinkers]
  );

  const handleCreate = useCallback(async () => {
    if (selectedThinkers.length === 0) {
      setError('Please select at least one thinker');
      return;
    }

    setIsCreating(true);
    setError(null);

    try {
      await onCreate(
        topic.trim(),
        selectedThinkers.map((t) => ({
          name: t.profile.name,
          bio: t.profile.bio,
          positions: t.profile.positions,
          style: t.profile.style,
          image_url: t.profile.image_url,
        }))
      );
      onClose();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to create conversation';
      setError(message);
    } finally {
      setIsCreating(false);
    }
  }, [topic, selectedThinkers, onCreate, onClose]);

  const handleSelectThinker = useCallback(
    async (thinker: SelectedThinker) => {
      setSelectedThinkers((prev) => [...prev, thinker]);

      // Auto-fetch a new suggestion to replace the one just selected
      if (topic.trim()) {
        setIsFetchingMore(true);
        try {
          // Build exclude list: all current suggestions + all selected thinkers + the one just selected
          const excludeNames = [
            ...suggestions.map((s) => s.name),
            ...selectedThinkers.map((t) => t.name),
            thinker.name,
          ];
          // Request just 1 replacement suggestion for faster response
          const results = await onSuggestThinkers(
            topic.trim(),
            1,
            excludeNames
          );

          // Add the new suggestion if valid
          if (results.length > 0) {
            setSuggestions((prev) => {
              const existingNames = new Set(
                prev.map((s) => s.name.toLowerCase())
              );
              const newSuggestion = results.find(
                (s) => !existingNames.has(s.name.toLowerCase())
              );
              if (newSuggestion) {
                return [...prev, newSuggestion];
              }
              return prev;
            });
          }
        } catch {
          // Silently fail - not critical if we can't fetch a replacement
        } finally {
          setIsFetchingMore(false);
        }
      }
    },
    [topic, suggestions, selectedThinkers, onSuggestThinkers]
  );

  const handleRemoveThinker = useCallback((name: string) => {
    setSelectedThinkers((prev) => prev.filter((t) => t.name !== name));
  }, []);

  const handleRefreshSuggestion = useCallback(
    async (nameToReplace: string) => {
      if (!topic.trim()) return;

      try {
        // Build exclude list: all current suggestions (except the one being replaced) + selected thinkers
        const excludeNames = [
          ...suggestions
            .filter((s) => s.name !== nameToReplace)
            .map((s) => s.name),
          ...selectedThinkers.map((t) => t.name),
        ];
        // Request just 1 replacement suggestion
        const results = await onSuggestThinkers(topic.trim(), 1, excludeNames);
        // Find the first result to use as replacement
        setSuggestions((prev) => {
          const existingNames = new Set(prev.map((s) => s.name.toLowerCase()));
          const selectedNames = new Set(
            selectedThinkers.map((t) => t.name.toLowerCase())
          );

          // Find a new suggestion that's unique (API should handle this, but double-check)
          const replacement = results.find(
            (s) =>
              !existingNames.has(s.name.toLowerCase()) &&
              !selectedNames.has(s.name.toLowerCase())
          );

          if (replacement) {
            // Replace the old suggestion with the new one
            return prev.map((s) =>
              s.name === nameToReplace ? replacement : s
            );
          }
          // If no unique replacement found, just remove the old one
          return prev.filter((s) => s.name !== nameToReplace);
        });
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to get replacement suggestion';
        setError(message);
      }
    },
    [topic, onSuggestThinkers, selectedThinkers, suggestions]
  );

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      data-testid="new-chat-modal"
    >
      <div className="w-full max-w-lg mx-4 bg-white dark:bg-zinc-900 rounded-xl shadow-xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {step === 'topic' ? 'New Conversation' : 'Select Thinkers'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            aria-label="Close modal"
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

        {/* Content */}
        <div
          className={`px-6 py-4 flex-1 min-h-0 ${step === 'topic' ? 'overflow-y-auto' : 'overflow-hidden flex flex-col'}`}
        >
          {step === 'topic' ? (
            <form onSubmit={handleTopicSubmit}>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                What would you like to discuss?
              </label>
              <input
                ref={inputRef}
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g., The nature of consciousness"
                className="w-full px-4 py-3 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                data-testid="topic-input"
              />
              {error && (
                <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                  {error}
                </p>
              )}
            </form>
          ) : (
            <>
              <ThinkerSelector
                topic={topic}
                suggestions={suggestions}
                selectedThinkers={selectedThinkers}
                onSelect={handleSelectThinker}
                onRemove={handleRemoveThinker}
                onValidateCustom={onValidateThinker}
                onRefreshSuggestion={handleRefreshSuggestion}
                isLoading={isLoading}
                isFetchingMore={isFetchingMore}
              />
              {error && (
                <p className="flex-shrink-0 text-sm text-red-600 dark:text-red-400 mt-2">
                  {error}
                </p>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between px-6 py-4 border-t border-zinc-200 dark:border-zinc-700 flex-shrink-0">
          {step === 'thinkers' && (
            <button
              onClick={() => setStep('topic')}
              className="px-4 py-2 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            >
              Back
            </button>
          )}
          <div className="flex gap-2 ml-auto">
            {step === 'topic' ? (
              <button
                onClick={(e) => handleTopicSubmit(e as unknown as FormEvent)}
                disabled={!topic.trim() || isLoading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                data-testid="next-button"
              >
                {isLoading ? (
                  <>
                    <svg
                      className="animate-spin h-4 w-4"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Suggesting thinkers...
                  </>
                ) : (
                  'Next'
                )}
              </button>
            ) : (
              <button
                onClick={handleCreate}
                disabled={selectedThinkers.length === 0 || isCreating}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="create-button"
              >
                {isCreating ? 'Creating...' : 'Start Conversation'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
