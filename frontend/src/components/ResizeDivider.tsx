/**
 * Draggable divider component for resizing the sidebar width.
 * Desktop only - hidden on mobile (lg breakpoint).
 */

'use client';

import { useCallback, useEffect, useState } from 'react';

export interface ResizeDividerProps {
  /** Callback when the divider is dragged. Receives the new sidebar width in pixels. */
  onResize: (width: number) => void;
  /** Minimum width for the sidebar in pixels */
  minWidth?: number;
  /** Maximum width for the sidebar in pixels */
  maxWidth?: number;
}

export function ResizeDivider({
  onResize,
  minWidth = 200,
  maxWidth = 500,
}: ResizeDividerProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging) return;

      const newWidth = Math.min(maxWidth, Math.max(minWidth, e.clientX));
      onResize(newWidth);
    },
    [isDragging, minWidth, maxWidth, onResize]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Add/remove global mouse listeners when dragging
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      // Prevent text selection while dragging
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'col-resize';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  return (
    <div
      className={`hidden lg:flex w-1 bg-zinc-200 dark:bg-zinc-800 cursor-col-resize hover:bg-blue-500 dark:hover:bg-blue-600 transition-colors flex-shrink-0 items-center justify-center group ${
        isDragging ? 'bg-blue-500 dark:bg-blue-600' : ''
      }`}
      onMouseDown={handleMouseDown}
      data-testid="resize-divider"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize sidebar"
    >
      {/* Visual indicator (dots) shown on hover */}
      <div
        className={`flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity ${
          isDragging ? 'opacity-100' : ''
        }`}
      >
        <div className="w-1 h-1 rounded-full bg-white dark:bg-zinc-300" />
        <div className="w-1 h-1 rounded-full bg-white dark:bg-zinc-300" />
        <div className="w-1 h-1 rounded-full bg-white dark:bg-zinc-300" />
      </div>
    </div>
  );
}
