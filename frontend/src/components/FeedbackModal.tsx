/**
 * Modal for submitting feedback without requiring a GitHub account.
 */

'use client';

import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useLanguage } from '@/contexts/LanguageContext';
import { type FeedbackType, submitFeedback } from '@/lib/api';

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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus textarea when modal opens
  useEffect(() => {
    if (isOpen && !success) {
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [isOpen, success]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setFeedbackType('bug');
      setMessage('');
      setEmail('');
      setName('');
      setError(null);
      setSuccess(false);
    }
  }, [isOpen]);

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
      await submitFeedback({
        feedback_type: feedbackType,
        message: message.trim(),
        email: email.trim() || undefined,
        name: name.trim() || undefined,
        user_agent:
          typeof navigator !== 'undefined' ? navigator.userAgent : undefined,
      });

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

              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                {t.feedbackModal?.privacyNote ||
                  'Your contact information is optional and will only be used to follow up on your feedback if needed.'}
              </p>

              {error && (
                <p className="text-sm text-red-600 dark:text-red-400">
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
