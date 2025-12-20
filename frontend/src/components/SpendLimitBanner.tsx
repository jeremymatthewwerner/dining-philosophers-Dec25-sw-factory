/**
 * Banner component for spend limit warnings and errors.
 */

'use client';

export interface SpendLimitBannerProps {
  /** Current spend amount */
  currentSpend: number;
  /** Maximum spend limit */
  spendLimit: number;
  /** Whether the limit has been exceeded */
  isExceeded: boolean;
  /** Callback to dismiss the banner (optional) */
  onDismiss?: () => void;
}

export function SpendLimitBanner({
  currentSpend,
  spendLimit,
  isExceeded,
  onDismiss,
}: SpendLimitBannerProps) {
  const percentUsed = Math.min(100, (currentSpend / spendLimit) * 100);
  const isNearLimit = percentUsed >= 85 && !isExceeded;

  if (!isNearLimit && !isExceeded) {
    return null;
  }

  return (
    <div
      className={`px-4 py-3 border-b ${
        isExceeded
          ? 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
          : 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800'
      }`}
      data-testid="spend-limit-banner"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {isExceeded ? (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0"
            >
              <path
                fillRule="evenodd"
                d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
          )}
          <div>
            <p
              className={`text-sm font-medium ${
                isExceeded
                  ? 'text-red-800 dark:text-red-200'
                  : 'text-yellow-800 dark:text-yellow-200'
              }`}
            >
              {isExceeded ? 'Spend limit reached' : 'Approaching spend limit'}
            </p>
            <p
              className={`text-xs ${
                isExceeded
                  ? 'text-red-600 dark:text-red-400'
                  : 'text-yellow-600 dark:text-yellow-400'
              }`}
            >
              ${currentSpend.toFixed(2)} / ${spendLimit.toFixed(2)} (
              {percentUsed.toFixed(0)}%)
              {isExceeded && ' - Contact admin to increase your limit'}
            </p>
          </div>
        </div>
        {onDismiss && !isExceeded && (
          <button
            onClick={onDismiss}
            className="text-yellow-600 dark:text-yellow-400 hover:text-yellow-800 dark:hover:text-yellow-200"
            aria-label="Dismiss"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-5 h-5"
            >
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
