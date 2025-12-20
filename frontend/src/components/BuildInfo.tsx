'use client';

import { useEffect } from 'react';

/**
 * Client component that logs build information to the console
 * This helps identify when users are running stale cached versions
 */
export function BuildInfo() {
  useEffect(() => {
    const buildTime = process.env.NEXT_PUBLIC_BUILD_TIME;
    if (buildTime) {
      console.log(
        `%c🏗️ Dining Philosophers - Build: ${buildTime}`,
        'color: #0070f3; font-weight: bold; font-size: 14px;'
      );
    }
  }, []);

  // This component renders nothing - it only logs to console
  return null;
}
