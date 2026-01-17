/**
 * Mention autocomplete dropdown component for @-mentioning thinkers.
 * Shows filtered thinker suggestions with avatars and colors.
 */

'use client';

import { useEffect, useRef } from 'react';
import type { ConversationThinker } from '@/types';
import { ThinkerAvatar } from './ThinkerAvatar';

export interface MentionAutocompleteProps {
  /** List of thinkers to show in autocomplete */
  thinkers: ConversationThinker[];
  /** Current search query (text after @) */
  query: string;
  /** Currently selected index for keyboard navigation */
  selectedIndex: number;
  /** Callback when a thinker is selected */
  onSelect: (thinker: ConversationThinker) => void;
  /** Callback when selection index changes via keyboard */
  onIndexChange: (index: number) => void;
  /** Position to render the dropdown */
  position: { top: number; left: number };
}

/**
 * Filters thinkers based on query (case-insensitive).
 * Matches against full name or individual name parts.
 */
export function filterThinkers(
  thinkers: ConversationThinker[],
  query: string
): ConversationThinker[] {
  if (!query) return thinkers;

  const lowerQuery = query.toLowerCase();
  return thinkers.filter((thinker) => {
    const lowerName = thinker.name.toLowerCase();
    // Match full name
    if (lowerName.includes(lowerQuery)) return true;
    // Match individual name parts (first name, last name)
    const parts = thinker.name.split(' ');
    return parts.some((part) => part.toLowerCase().startsWith(lowerQuery));
  });
}

export function MentionAutocomplete({
  thinkers,
  query,
  selectedIndex,
  onSelect,
  onIndexChange,
  position,
}: MentionAutocompleteProps) {
  const filteredThinkers = filterThinkers(thinkers, query);
  const listRef = useRef<HTMLDivElement>(null);
  const selectedRef = useRef<HTMLButtonElement>(null);

  // Scroll selected item into view
  useEffect(() => {
    if (selectedRef.current && listRef.current) {
      const list = listRef.current;
      const item = selectedRef.current;
      const listRect = list.getBoundingClientRect();
      const itemRect = item.getBoundingClientRect();

      if (itemRect.bottom > listRect.bottom) {
        item.scrollIntoView({ block: 'nearest' });
      } else if (itemRect.top < listRect.top) {
        item.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  // Clamp selectedIndex to valid range
  useEffect(() => {
    if (
      filteredThinkers.length > 0 &&
      selectedIndex >= filteredThinkers.length
    ) {
      onIndexChange(filteredThinkers.length - 1);
    }
  }, [filteredThinkers.length, selectedIndex, onIndexChange]);

  if (filteredThinkers.length === 0) {
    return null;
  }

  return (
    <div
      className="absolute z-50 bg-white dark:bg-zinc-800 rounded-lg shadow-lg border border-zinc-200 dark:border-zinc-700 py-1 max-h-48 overflow-y-auto min-w-[200px] max-w-[280px]"
      style={{
        bottom: position.top,
        left: position.left,
      }}
      ref={listRef}
      role="listbox"
      aria-label="Mention suggestions"
      data-testid="mention-autocomplete"
    >
      {filteredThinkers.map((thinker, index) => {
        const isSelected = index === selectedIndex;
        return (
          <button
            key={thinker.id}
            ref={isSelected ? selectedRef : null}
            type="button"
            className={`w-full text-left px-3 py-2 flex items-center gap-2 transition-colors ${
              isSelected
                ? 'bg-blue-50 dark:bg-blue-900/30'
                : 'hover:bg-zinc-50 dark:hover:bg-zinc-700'
            }`}
            onClick={() => onSelect(thinker)}
            role="option"
            aria-selected={isSelected}
            data-testid={`mention-option-${thinker.name.toLowerCase().replace(/\s+/g, '-')}`}
          >
            <ThinkerAvatar
              name={thinker.name}
              imageUrl={thinker.image_url}
              size="sm"
              color={thinker.color}
            />
            <span
              className="font-semibold text-sm truncate"
              style={{ color: thinker.color }}
            >
              {thinker.name}
            </span>
          </button>
        );
      })}
    </div>
  );
}
