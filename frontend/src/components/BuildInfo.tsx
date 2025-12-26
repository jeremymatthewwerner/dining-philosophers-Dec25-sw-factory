'use client';

import { useEffect } from 'react';

/**
 * Client component that displays build information in the footer
 * This helps identify when users are running stale cached versions
 */
export function BuildInfo() {
  const buildTime = process.env.NEXT_PUBLIC_BUILD_TIME;

  useEffect(() => {
    if (buildTime) {
      console.log(
        `%c🏗️ dining philosophers - Build: ${buildTime}`,
        'color: #0070f3; font-weight: bold; font-size: 14px;'
      );
    }
  }, [buildTime]);

  // Format the build time for display
  const formatBuildTime = (isoString: string): string => {
    const date = new Date(isoString);
    const options: Intl.DateTimeFormatOptions = {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    };
    const formatted = date.toLocaleString('en-US', options);
    // Convert "Dec 26, 2025, 1:05 AM" to "Dec 26, 2025 at 1:05 AM"
    // Replace the last comma (before time) with " at", keep first comma (after day)
    const lastCommaIndex = formatted.lastIndexOf(',');
    if (lastCommaIndex !== -1) {
      return (
        formatted.substring(0, lastCommaIndex) +
        ' at' +
        formatted.substring(lastCommaIndex + 1)
      );
    }
    return formatted;
  };

  if (!buildTime) {
    return null;
  }

  return (
    <div
      className="text-xs text-zinc-400 dark:text-zinc-500 text-center py-2"
      data-testid="build-info"
    >
      Built: {formatBuildTime(buildTime)}
    </div>
  );
}
