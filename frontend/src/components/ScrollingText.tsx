/**
 * ScrollingText component - displays text that scrolls on hover when truncated.
 *
 * When text overflows its container (showing ellipsis), hovering triggers a
 * marquee-style animation that scrolls right-to-left, then resets after a delay.
 */

'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

export interface ScrollingTextProps {
  /** The text content to display */
  text: string;
  /** Additional CSS classes for the text element */
  className?: string;
  /** Title attribute for browser tooltip (defaults to text if truncated) */
  title?: string;
  /** Delay in ms before animation starts and between cycles (default: 2000) */
  delayMs?: number;
  /** Scroll speed in pixels per second (default: 30) */
  speedPxPerSecond?: number;
}

export function ScrollingText({
  text,
  className = '',
  title,
  delayMs = 2000,
  speedPxPerSecond = 30,
}: ScrollingTextProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLSpanElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [isTruncated, setIsTruncated] = useState(false);
  const [scrollOffset, setScrollOffset] = useState(0);
  const animationRef = useRef<number | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Check if text is truncated (overflows container)
  const checkTruncation = useCallback(() => {
    if (containerRef.current && textRef.current) {
      const containerWidth = containerRef.current.clientWidth;
      const textWidth = textRef.current.scrollWidth;
      setIsTruncated(textWidth > containerWidth);
    }
  }, []);

  // Check truncation on mount and when text/container size changes
  useEffect(() => {
    checkTruncation();

    // Use ResizeObserver to detect container size changes (crucial for flex layouts)
    const container = containerRef.current;
    let resizeObserver: ResizeObserver | null = null;
    if (container && typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => {
        checkTruncation();
      });
      resizeObserver.observe(container);
    }

    // Also check on window resize as fallback
    window.addEventListener('resize', checkTruncation);

    return () => {
      window.removeEventListener('resize', checkTruncation);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
    };
  }, [text, checkTruncation]);

  // Reset scroll position when hover ends
  const handleMouseLeave = useCallback(() => {
    setIsHovered(false);
    setScrollOffset(0);
    // Cancel any running animations
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  // Animation logic - only runs when hovering and truncated
  useEffect(() => {
    if (!isHovered || !isTruncated) {
      return;
    }

    // Clean up any existing animation/timeouts at start of new animation
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    const containerWidth = containerRef.current?.clientWidth || 0;
    const textWidth = textRef.current?.scrollWidth || 0;
    const maxScroll = textWidth - containerWidth;

    if (maxScroll <= 0) return;

    let lastTimestamp: number | null = null;
    let isWaiting = true;
    let currentOffset = 0;

    const animate = (timestamp: number) => {
      if (!lastTimestamp) {
        lastTimestamp = timestamp;
        // Initial delay before starting
        timeoutRef.current = setTimeout(() => {
          isWaiting = false;
          lastTimestamp = null;
          animationRef.current = requestAnimationFrame(animate);
        }, delayMs);
        return;
      }

      if (isWaiting) {
        animationRef.current = requestAnimationFrame(animate);
        return;
      }

      const deltaMs = timestamp - lastTimestamp;
      lastTimestamp = timestamp;

      // Calculate scroll increment
      const scrollIncrement = (speedPxPerSecond * deltaMs) / 1000;
      currentOffset = Math.min(currentOffset + scrollIncrement, maxScroll);

      setScrollOffset(currentOffset);

      if (currentOffset >= maxScroll) {
        // Reached the end - wait, then reset
        isWaiting = true;
        lastTimestamp = null;
        timeoutRef.current = setTimeout(() => {
          currentOffset = 0;
          setScrollOffset(0);
          isWaiting = true;
          lastTimestamp = null;
          // Wait again before starting next cycle
          timeoutRef.current = setTimeout(() => {
            isWaiting = false;
            lastTimestamp = null;
            animationRef.current = requestAnimationFrame(animate);
          }, delayMs);
        }, delayMs);
        return;
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [isHovered, isTruncated, delayMs, speedPxPerSecond]);

  // When not hovering, show text directly with ellipsis (text-overflow only works on direct text)
  // When hovering (and truncated), use span with transform for scrolling animation
  const isAnimating = isHovered && isTruncated;

  return (
    <div
      ref={containerRef}
      className={`overflow-hidden whitespace-nowrap relative ${className}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      title={isTruncated ? (title ?? text) : undefined}
      style={{
        // Show ellipsis when truncated and not animating
        // text-overflow only works on direct text content, so we conditionally render
        textOverflow: !isAnimating ? 'ellipsis' : 'clip',
      }}
    >
      {isAnimating ? (
        // During animation: use span with transform for smooth scrolling
        <span
          ref={textRef}
          className="inline-block"
          style={{
            transform: `translateX(-${scrollOffset}px)`,
          }}
        >
          {text}
        </span>
      ) : (
        // When not animating: use hidden span for measurement + direct text for ellipsis
        <>
          {/* Hidden span for measuring text width */}
          <span
            ref={textRef}
            className="inline-block"
            style={{
              position: 'absolute',
              visibility: 'hidden',
              whiteSpace: 'nowrap',
            }}
          >
            {text}
          </span>
          {/* Direct text content so text-overflow: ellipsis works */}
          {text}
        </>
      )}
    </div>
  );
}
