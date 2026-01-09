/**
 * Modal for submitting feedback without requiring a GitHub account.
 */

'use client';

import {
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { type FeedbackType, getStoredUser, submitFeedback } from '@/lib/api';

// Max file size: 5MB
const MAX_FILE_SIZE = 5 * 1024 * 1024;
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];

interface ScreenshotData {
  data: string; // base64 data
  filename: string;
  previewUrl: string; // data URL for thumbnail preview
}

type UploadState = 'idle' | 'loading' | 'done';

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
  const [screenshot, setScreenshot] = useState<ScreenshotData | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);

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
      // Revoke object URL to prevent memory leaks
      if (screenshot?.previewUrl) {
        URL.revokeObjectURL(screenshot.previewUrl);
      }
      setScreenshot(null);
      setUploadState('idle');
      setError(null);
      setSuccess(false);
      setIsDragging(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [isOpen, screenshot?.previewUrl]);

  // Process a file and update screenshot state
  const processFile = useCallback(
    (file: File, inputElement?: HTMLInputElement) => {
      // Validate file type
      if (!ALLOWED_TYPES.includes(file.type)) {
        setError(
          t.feedbackModal?.invalidFileType ||
            'Please upload an image file (PNG, JPEG, GIF, or WebP)'
        );
        if (inputElement) inputElement.value = '';
        setUploadState('idle');
        return;
      }

      // Validate file size
      if (file.size > MAX_FILE_SIZE) {
        setError(
          t.feedbackModal?.fileTooLarge || 'Screenshot must be less than 5MB'
        );
        if (inputElement) inputElement.value = '';
        setUploadState('idle');
        return;
      }

      setError(null);
      setUploadState('loading');

      // Revoke previous preview URL if exists
      if (screenshot?.previewUrl) {
        URL.revokeObjectURL(screenshot.previewUrl);
      }

      // Create object URL for preview (faster than waiting for FileReader)
      const previewUrl = URL.createObjectURL(file);

      // Convert to base64
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result as string;
        // Remove the data URL prefix to get just the base64 data
        const base64Data = base64.split(',')[1];
        setScreenshot({
          data: base64Data,
          filename: file.name,
          previewUrl,
        });
        setUploadState('done');
      };
      reader.onerror = () => {
        setError(
          t.feedbackModal?.fileReadError || 'Failed to read screenshot file'
        );
        URL.revokeObjectURL(previewUrl);
        setUploadState('idle');
      };
      reader.readAsDataURL(file);
    },
    [t.feedbackModal, screenshot?.previewUrl]
  );

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      setScreenshot(null);
      setUploadState('idle');
      return;
    }
    processFile(file, e.target);
  };

  const removeScreenshot = () => {
    // Revoke object URL to prevent memory leaks
    if (screenshot?.previewUrl) {
      URL.revokeObjectURL(screenshot.previewUrl);
    }
    setScreenshot(null);
    setUploadState('idle');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Handle clipboard paste
  const handlePaste = useCallback(
    (e: ClipboardEvent<HTMLDivElement>) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      for (const item of items) {
        if (item.type.startsWith('image/')) {
          e.preventDefault();
          const file = item.getAsFile();
          if (file) {
            // Generate a filename for pasted images
            const extension = item.type.split('/')[1] || 'png';
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const pastedFile = new File(
              [file],
              `screenshot-${timestamp}.${extension}`,
              { type: file.type }
            );
            processFile(pastedFile);
          }
          break;
        }
      }
    },
    [processFile]
  );

  // Handle drag and drop
  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set isDragging to false if we're leaving the drop zone entirely
    if (!dropZoneRef.current?.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const files = e.dataTransfer?.files;
      if (files && files.length > 0) {
        // Take only the first image file
        for (const file of files) {
          if (ALLOWED_TYPES.includes(file.type)) {
            processFile(file);
            break;
          }
        }
      }
    },
    [processFile]
  );

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
                {uploadState === 'loading' ? (
                  /* Loading state with spinner */
                  <div
                    className="flex items-center justify-center gap-3 p-6 bg-zinc-100 dark:bg-zinc-800 rounded-lg"
                    data-testid="screenshot-loading"
                  >
                    <svg
                      className="animate-spin h-6 w-6 text-blue-600"
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
                    <span className="text-sm text-zinc-600 dark:text-zinc-400">
                      {t.feedbackModal?.processingScreenshot ||
                        'Processing screenshot...'}
                    </span>
                  </div>
                ) : screenshot ? (
                  /* Screenshot preview with thumbnail */
                  <div className="p-3 bg-zinc-100 dark:bg-zinc-800 rounded-lg">
                    <div className="flex items-start gap-3">
                      {/* Thumbnail preview */}
                      <div className="relative w-20 h-20 flex-shrink-0 rounded-lg overflow-hidden bg-zinc-200 dark:bg-zinc-700">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={screenshot.previewUrl}
                          alt="Screenshot preview"
                          className="w-full h-full object-cover"
                          data-testid="screenshot-preview"
                        />
                      </div>
                      {/* File info and remove button */}
                      <div className="flex-1 min-w-0">
                        <p
                          className="text-sm text-zinc-700 dark:text-zinc-300 truncate"
                          title={screenshot.filename}
                        >
                          {screenshot.filename}
                        </p>
                        <button
                          type="button"
                          onClick={removeScreenshot}
                          className="mt-2 flex items-center gap-1.5 text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 transition-colors"
                          aria-label={
                            t.feedbackModal?.removeScreenshot ||
                            'Remove screenshot'
                          }
                          data-testid="remove-screenshot"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            className="w-4 h-4"
                          >
                            <path
                              fillRule="evenodd"
                              d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z"
                              clipRule="evenodd"
                            />
                          </svg>
                          {t.feedbackModal?.removeScreenshot ||
                            'Remove screenshot'}
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* Upload area with drag & drop and paste support */
                  <div
                    ref={dropZoneRef}
                    className="relative"
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onPaste={handlePaste}
                    tabIndex={0}
                    data-testid="screenshot-dropzone"
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/png,image/jpeg,image/gif,image/webp"
                      onChange={handleFileChange}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      data-testid="screenshot-input"
                    />
                    <div
                      className={`flex flex-col items-center justify-center gap-2 px-4 py-5 border-2 border-dashed rounded-lg transition-colors cursor-pointer ${
                        isDragging
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                          : 'border-zinc-300 dark:border-zinc-600 text-zinc-500 dark:text-zinc-400 hover:border-zinc-400 dark:hover:border-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300'
                      }`}
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        className="w-6 h-6"
                      >
                        <path d="M9.25 13.25a.75.75 0 001.5 0V4.636l2.955 3.129a.75.75 0 001.09-1.03l-4.25-4.5a.75.75 0 00-1.09 0l-4.25 4.5a.75.75 0 101.09 1.03L9.25 4.636v8.614z" />
                        <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
                      </svg>
                      <span className="text-sm font-medium">
                        {isDragging
                          ? t.feedbackModal?.dropScreenshot || 'Drop image here'
                          : t.feedbackModal?.uploadScreenshot ||
                            'Upload screenshot'}
                      </span>
                      <span className="text-xs text-zinc-400 dark:text-zinc-500">
                        {t.feedbackModal?.pasteHint ||
                          'or paste from clipboard (Ctrl+V / Cmd+V)'}
                      </span>
                    </div>
                  </div>
                )}
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {t.feedbackModal?.screenshotHint ||
                    'Max 5MB. Supports PNG, JPEG, GIF, WebP'}
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
