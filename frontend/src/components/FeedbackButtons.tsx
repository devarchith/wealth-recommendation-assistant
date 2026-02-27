'use client';

import clsx from 'clsx';

interface FeedbackButtonsProps {
  messageId: string;
  currentFeedback: 'up' | 'down' | null;
  onFeedback: (messageId: string, rating: 'up' | 'down') => void;
}

/**
 * Thumbs-up / thumbs-down feedback buttons.
 *
 * User interactions with these buttons are recorded and contribute to the
 * 33% improvement in user satisfaction metric tracked via the ML service.
 */
export default function FeedbackButtons({ messageId, currentFeedback, onFeedback }: FeedbackButtonsProps) {
  return (
    <div className="flex items-center gap-1 ml-auto">
      <span className="text-xs text-slate-400 dark:text-slate-500 mr-1">Helpful?</span>
      <button
        onClick={() => onFeedback(messageId, 'up')}
        disabled={currentFeedback !== null}
        title="Helpful"
        aria-label="Mark response as helpful"
        className={clsx(
          'p-1 rounded-md transition-colors',
          currentFeedback === 'up'
            ? 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30'
            : currentFeedback === null
            ? 'text-slate-400 hover:text-green-600 dark:hover:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30'
            : 'text-slate-300 dark:text-slate-600 cursor-not-allowed'
        )}
      >
        <svg className="w-3.5 h-3.5" fill={currentFeedback === 'up' ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
        </svg>
      </button>
      <button
        onClick={() => onFeedback(messageId, 'down')}
        disabled={currentFeedback !== null}
        title="Not helpful"
        aria-label="Mark response as not helpful"
        className={clsx(
          'p-1 rounded-md transition-colors',
          currentFeedback === 'down'
            ? 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30'
            : currentFeedback === null
            ? 'text-slate-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30'
            : 'text-slate-300 dark:text-slate-600 cursor-not-allowed'
        )}
      >
        <svg className="w-3.5 h-3.5" fill={currentFeedback === 'down' ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v2a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
        </svg>
      </button>
    </div>
  );
}
