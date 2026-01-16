/**
 * Message input component for user to type and send messages.
 * Supports @mention autocomplete for thinkers in the conversation.
 */

'use client';

import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import type { ConversationThinker } from '@/types';
import { MentionAutocomplete, filterThinkers } from './MentionAutocomplete';

export interface MessageInputProps {
  /** Callback when message is submitted */
  onSend: (content: string) => void;
  /** Callback when user starts typing */
  onTypingStart?: () => void;
  /** Callback when user stops typing */
  onTypingStop?: () => void;
  /** Whether input is disabled */
  disabled?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Thinkers in the conversation for @mention autocomplete */
  thinkers?: ConversationThinker[];
}

interface MentionState {
  isActive: boolean;
  query: string;
  startIndex: number; // Position of @ in the text
  selectedIndex: number;
}

const initialMentionState: MentionState = {
  isActive: false,
  query: '',
  startIndex: -1,
  selectedIndex: 0,
};

export function MessageInput({
  onSend,
  onTypingStart,
  onTypingStop,
  disabled = false,
  placeholder,
  thinkers = [],
}: MessageInputProps) {
  const { t } = useLanguage();
  const [value, setValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [mentionState, setMentionState] =
    useState<MentionState>(initialMentionState);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 16 });
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  // Update dropdown position when autocomplete becomes active
  useEffect(() => {
    if (mentionState.isActive && textareaRef.current && formRef.current) {
      const form = formRef.current;
      const formRect = form.getBoundingClientRect();
      const textareaRect = textareaRef.current.getBoundingClientRect();

      // Position above the textarea
      const top = formRect.height - textareaRect.top + formRect.top + 8;
      const left = 16;

      setDropdownPosition({ top, left });
    }
  }, [mentionState.isActive]);

  // Update mention state based on cursor position
  const updateMentionState = useCallback(
    (text: string, cursorPos: number) => {
      if (thinkers.length === 0) {
        setMentionState(initialMentionState);
        return;
      }

      // Find the last @ before cursor
      const beforeCursor = text.slice(0, cursorPos);
      const lastAtIndex = beforeCursor.lastIndexOf('@');

      if (lastAtIndex === -1) {
        setMentionState(initialMentionState);
        return;
      }

      // Check if @ is at start of word (preceded by space, newline, or start of text)
      if (lastAtIndex > 0 && !/\s/.test(beforeCursor[lastAtIndex - 1])) {
        setMentionState(initialMentionState);
        return;
      }

      // Get the query (text between @ and cursor)
      const query = beforeCursor.slice(lastAtIndex + 1);

      // If query contains spaces (more than one word), close autocomplete
      // This allows typing "@ " to dismiss autocomplete
      if (query.includes(' ') && !query.trim()) {
        setMentionState(initialMentionState);
        return;
      }

      // Check if query matches any thinker (case-insensitive)
      const queryWord = query.split(' ')[0]; // First word of query for filtering
      const filtered = filterThinkers(thinkers, queryWord);

      if (filtered.length === 0 && queryWord.length > 0) {
        // No matches found for the query
        setMentionState(initialMentionState);
        return;
      }

      setMentionState((prev) => ({
        isActive: true,
        query: queryWord,
        startIndex: lastAtIndex,
        selectedIndex:
          prev.isActive && prev.startIndex === lastAtIndex
            ? Math.min(prev.selectedIndex, filtered.length - 1)
            : 0,
      }));
    },
    [thinkers]
  );

  const handleChange = useCallback(
    (e: ChangeEvent<HTMLTextAreaElement>) => {
      const newValue = e.target.value;
      const cursorPos = e.target.selectionStart ?? newValue.length;

      setValue(newValue);
      updateMentionState(newValue, cursorPos);

      // Handle typing indicators
      if (!isTyping) {
        setIsTyping(true);
        onTypingStart?.();
      }

      // Reset typing timeout
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }

      typingTimeoutRef.current = setTimeout(() => {
        setIsTyping(false);
        onTypingStop?.();
      }, 2000);
    },
    [isTyping, onTypingStart, onTypingStop, updateMentionState]
  );

  const selectMention = useCallback(
    (thinker: ConversationThinker) => {
      if (!textareaRef.current) return;

      // Replace @query with the thinker's name
      const beforeAt = value.slice(0, mentionState.startIndex);
      const afterQuery = value.slice(
        mentionState.startIndex + 1 + mentionState.query.length
      );
      const newValue = `${beforeAt}${thinker.name}${afterQuery}`;

      setValue(newValue);
      setMentionState(initialMentionState);

      // Focus textarea and set cursor after the inserted name
      const cursorPos = mentionState.startIndex + thinker.name.length;
      requestAnimationFrame(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          textareaRef.current.setSelectionRange(cursorPos, cursorPos);
        }
      });
    },
    [value, mentionState.startIndex, mentionState.query.length]
  );

  const handleSubmit = useCallback(
    (e?: FormEvent) => {
      e?.preventDefault();

      const trimmed = value.trim();
      if (!trimmed || disabled) return;

      // Clear typing timeout
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }

      if (isTyping) {
        setIsTyping(false);
        onTypingStop?.();
      }

      onSend(trimmed);
      setValue('');
      setMentionState(initialMentionState);

      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    },
    [value, disabled, isTyping, onSend, onTypingStop]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      const filteredThinkers = filterThinkers(thinkers, mentionState.query);

      if (mentionState.isActive && filteredThinkers.length > 0) {
        switch (e.key) {
          case 'ArrowUp':
            e.preventDefault();
            setMentionState((prev) => ({
              ...prev,
              selectedIndex:
                prev.selectedIndex > 0
                  ? prev.selectedIndex - 1
                  : filteredThinkers.length - 1,
            }));
            return;
          case 'ArrowDown':
            e.preventDefault();
            setMentionState((prev) => ({
              ...prev,
              selectedIndex:
                prev.selectedIndex < filteredThinkers.length - 1
                  ? prev.selectedIndex + 1
                  : 0,
            }));
            return;
          case 'Tab':
          case 'Enter':
            e.preventDefault();
            selectMention(filteredThinkers[mentionState.selectedIndex]);
            return;
          case 'Escape':
            e.preventDefault();
            setMentionState(initialMentionState);
            return;
        }
      }

      // Submit on Enter (without Shift) when autocomplete is not active
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [mentionState, thinkers, selectMention, handleSubmit]
  );

  // Handle cursor movement (click or arrow keys without autocomplete)
  const handleSelect = useCallback(() => {
    if (!textareaRef.current) return;
    const cursorPos = textareaRef.current.selectionStart ?? 0;
    updateMentionState(value, cursorPos);
  }, [value, updateMentionState]);

  // Auto-resize textarea
  const handleTextareaResize = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, []);

  const filteredThinkers = filterThinkers(thinkers, mentionState.query);
  const showAutocomplete =
    mentionState.isActive && filteredThinkers.length > 0 && thinkers.length > 0;

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      className="relative flex items-end gap-2 p-4 border-t border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900"
      data-testid="message-input"
    >
      {/* Mention autocomplete dropdown */}
      {showAutocomplete && (
        <MentionAutocomplete
          thinkers={thinkers}
          query={mentionState.query}
          selectedIndex={mentionState.selectedIndex}
          onSelect={selectMention}
          onIndexChange={(index) =>
            setMentionState((prev) => ({ ...prev, selectedIndex: index }))
          }
          position={dropdownPosition}
        />
      )}

      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          handleChange(e);
          handleTextareaResize();
        }}
        onKeyDown={handleKeyDown}
        onSelect={handleSelect}
        onClick={handleSelect}
        disabled={disabled}
        placeholder={placeholder || t.messageInput.placeholder}
        rows={1}
        className="flex-1 px-4 py-2 min-h-[44px] max-h-[200px] rounded-2xl border border-zinc-300 dark:border-zinc-600 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 resize-none disabled:opacity-50 disabled:cursor-not-allowed"
        data-testid="message-textarea"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="flex items-center justify-center w-11 h-11 rounded-full bg-blue-600 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:focus:ring-offset-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        data-testid="send-button"
        aria-label={t.messageInput.sendMessage}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-5 h-5"
        >
          <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
        </svg>
      </button>
    </form>
  );
}
