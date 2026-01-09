/**
 * Modal for submitting feedback without requiring a GitHub account.
 */

'use client';

import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { type FeedbackType, getStoredUser, submitFeedback } from '@/lib/api';

// Max file size: 5MB
const MAX_FILE_SIZE = 5 * 1024 * 1024;
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

// localStorage keys for remembering feedback info
export const FEEDBACK_NAME_KEY = 'feedback_name';
export const FEEDBACK_EMAIL_KEY = 'feedback_email';

/**
 * Get saved feedback contact info from localStorage.
 */
export function getSavedFeedbackInfo(): { name: string; email: string } {
  if (typeof window === 'undefined') {
    return { name: '', email: '' };
  }
  return {
    name: localStorage.getItem(FEEDBACK_NAME_KEY) || '',
    email: localStorage.getItem(FEEDBACK_EMAIL_KEY) || '',
  };
}

/**
 * Save feedback contact info to localStorage.
 */
export function saveFeedbackInfo(name: string, email: string): void {
  if (typeof window === 'undefined') return;
  if (name.trim()) {
    localStorage.setItem(FEEDBACK_NAME_KEY, name.trim());
  }
  if (email.trim()) {
    localStorage.setItem(FEEDBACK_EMAIL_KEY, email.trim());
  }
}

/**
 * Clear saved feedback contact info from localStorage.
 */
export function clearFeedbackInfo(): void {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(FEEDBACK_NAME_KEY);
  localStorage.removeItem(FEEDBACK_EMAIL_KEY);
}

export interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function FeedbackModal({ isOpen, onClose }: FeedbackModalProps) {
  const { t } = useLanguage();
  const [feedbackType, setFeedbackType] = useState<FeedbackType>('bug');
  const [message, setMessage] = useState('');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [screenshot, setScreenshot] = useState<{
    data: string;
    filename: string;
  } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load saved name/email when modal opens
  useEffect(() => {
    if (isOpen && !success) {
      const saved = getSavedFeedbackInfo();
      setName(saved.name);
      setEmail(saved.email);
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [isOpen, success]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setFeedbackType('bug');
      setMessage('');
      // Reload saved values when modal reopens
      const saved = getSavedFeedbackInfo();
      setEmail(saved.email);
      setName(saved.name);
      setScreenshot(null);
      setError(null);
      setSuccess(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [isOpen]);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      setScreenshot(null);
      return;
    }

    // Validate file type
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError(
        t.feedbackModal?.invalidFileType ||
          'Please upload an image file (PNG, JPEG, GIF, or WebP)'
      );
      e.target.value = '';
      return;
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      setError(
        t.feedbackModal?.fileTooLarge || 'Screenshot must be less than 5MB'
      );
      e.target.value = '';
      return;
    }

    setError(null);

    // Convert to base64
    const reader = new FileReader();
    reader.onload = () => {
      const base64 = reader.result as string;
      // Remove the data URL prefix to get just the base64 data
      const base64Data = base64.split(',')[1];
      setScreenshot({
        data: base64Data,
        filename: file.name,
      });
    };
    reader.onerror = () => {
      setError(
        t.feedbackModal?.fileReadError || 'Failed to read screenshot file'
      );
    };
    reader.readAsDataURL(file);
  };

  const removeScreenshot = () => {
    setScreenshot(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (message.trim().length < 10) {
      setError(
        t.feedbackModal?.messageTooShort ||
          'Message must be at least 10 characters'
      );
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      // Get the current user's username if logged in
      const currentUser = getStoredUser();

      await submitFeedback({
        feedback_type: feedbackType,
        message: message.trim(),
        email: email.trim() || undefined,
        name: name.trim() || undefined,
        username: currentUser?.username || undefined,
        user_agent:
          typeof navigator !== 'undefined' ? navigator.userAgent : undefined,
        screenshot_data: screenshot?.data,
        screenshot_filename: screenshot?.filename,
      });

      // Save contact info for next time
      saveFeedbackInfo(name, email);

      setSuccess(true);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to submit feedback';
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      data-testid="feedback-modal"
    >
      <div className="w-full max-w-lg mx-4 bg-white dark:bg-zinc-900 rounded-xl shadow-xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {t.feedbackModal?.title || 'Send Feedback'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
            aria-label={t.feedbackModal?.close || 'Close'}
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
        <div className="px-6 py-4 flex-1 overflow-y-auto">
          {success ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center">
                <svg
                  className="w-8 h-8 text-green-600 dark:text-green-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                {t.feedbackModal?.thankYou || 'Thank you!'}
              </h3>
              <p className="text-zinc-600 dark:text-zinc-400">
                {t.feedbackModal?.successMessage ||
                  'Your feedback has been submitted successfully.'}
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Feedback Type */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  {t.feedbackModal?.typeLabel || 'Type'}
                </label>
                <div className="flex gap-2">
                  {(['bug', 'feature', 'other'] as const).map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setFeedbackType(type)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        feedbackType === type
                          ? 'bg-blue-600 text-white'
                          : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                      }`}
                      data-testid={`feedback-type-${type}`}
                    >
                      {t.feedbackModal?.[
                        `type${type.charAt(0).toUpperCase() + type.slice(1)}` as keyof typeof t.feedbackModal
                      ] ||
                        (type === 'bug'
                          ? 'Bug Report'
                          : type === 'feature'
                            ? 'Feature Request'
                            : 'Other')}
                    </button>
                  ))}
                </div>
              </div>

              {/* Message */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  {t.feedbackModal?.messageLabel || 'Message'} *
                </label>
                <textarea
                  ref={textareaRef}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder={
                    t.feedbackModal?.messagePlaceholder ||
                    'Describe your feedback...'
                  }
                  rows={4}
                  className="w-full px-4 py-3 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  data-testid="feedback-message"
                />
              </div>

              {/* Optional fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    {t.feedbackModal?.nameLabel || 'Name'} (
                    {t.feedbackModal?.optional || 'optional'})
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={
                      t.feedbackModal?.namePlaceholder || 'Your name'
                    }
                    className="w-full px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="feedback-name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                    {t.feedbackModal?.emailLabel || 'Email'} (
                    {t.feedbackModal?.optional || 'optional'})
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={
                      t.feedbackModal?.emailPlaceholder || 'your@email.com'
                    }
                    className="w-full px-4 py-2 rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="feedback-email"
                  />
                </div>
              </div>

              {/* Screenshot Upload */}
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  {t.feedbackModal?.screenshotLabel || 'Screenshot'} (
                  {t.feedbackModal?.optional || 'optional'})
                </label>
                {screenshot ? (
                  <div className="flex items-center gap-3 p-3 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="currentColor"
                      className="w-8 h-8 text-green-600 dark:text-green-400 flex-shrink-0"
                    >
                      <path
                        fillRule="evenodd"
                        d="M1.5 6a2.25 2.25 0 012.25-2.25h16.5A2.25 2.25 0 0122.5 6v12a2.25 2.25 0 01-2.25 2.25H3.75A2.25 2.25 0 011.5 18V6zM3 16.06V18c0 .414.336.75.75.75h16.5A.75.75 0 0021 18v-1.94l-2.69-2.689a1.5 1.5 0 00-2.12 0l-.88.879.97.97a.75.75 0 11-1.06 1.06l-5.16-5.159a1.5 1.5 0 00-2.12 0L3 16.061zm10.125-7.81a1.125 1.125 0 112.25 0 1.125 1.125 0 01-2.25 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                    <span className="flex-1 text-sm text-zinc-700 dark:text-zinc-300 truncate">
                      {screenshot.filename}
                    </span>
                    <button
                      type="button"
                      onClick={removeScreenshot}
                      className="p-1.5 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-lg transition-colors"
                      aria-label={
                        t.feedbackModal?.removeScreenshot || 'Remove screenshot'
                      }
                      data-testid="remove-screenshot"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="w-5 h-5 text-zinc-500"
                      >
                        <path
                          fillRule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/png,image/jpeg,image/gif,image/webp"
                      onChange={handleFileChange}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      data-testid="screenshot-input"
                    />
                    <div className="flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-zinc-300 dark:border-zinc-600 rounded-lg text-zinc-500 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors cursor-pointer">
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="w-5 h-5"
                      >
                        <path d="M9.25 13.25a.75.75 0 001.5 0V4.636l2.955 3.129a.75.75 0 001.09-1.03l-4.25-4.5a.75.75 0 00-1.09 0l-4.25 4.5a.75.75 0 101.09 1.03L9.25 4.636v8.614z" />
                        <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
                      </svg>
                      <span className="text-sm">
                        {t.feedbackModal?.uploadScreenshot ||
                          'Upload screenshot (PNG, JPEG, GIF, WebP)'}
                      </span>
                    </div>
                  </div>
                )}
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {t.feedbackModal?.screenshotHint || 'Max 5MB'}
                </p>
              </div>

              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                {t.feedbackModal?.privacyNote ||
                  'Your contact information is optional and will only be used to follow up on your feedback if needed.'}
              </p>

              {error && (
                <p
                  className="text-sm text-red-600 dark:text-red-400"
                  data-testid="feedback-error"
                >
                  {error}
                </p>
              )}
            </form>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end px-6 py-4 border-t border-zinc-200 dark:border-zinc-700 flex-shrink-0">
          {success ? (
            <button
              onClick={onClose}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              {t.feedbackModal?.done || 'Done'}
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors mr-2"
              >
                {t.feedbackModal?.cancel || 'Cancel'}
              </button>
              <button
                onClick={handleSubmit}
                disabled={!message.trim() || isSubmitting}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                data-testid="submit-feedback"
              >
                {isSubmitting ? (
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
                    {t.feedbackModal?.submitting || 'Submitting...'}
                  </>
                ) : (
                  t.feedbackModal?.submit || 'Submit Feedback'
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
