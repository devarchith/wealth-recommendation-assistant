'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';
import { Message } from '@/types/chat';
import SourceList from './SourceList';
import FeedbackButtons from './FeedbackButtons';
import LatencyBadge from './LatencyBadge';
import ExplainabilityPanel from './ExplainabilityPanel';

interface MessageBubbleProps {
  message: Message;
  onFeedback: (messageId: string, rating: 'up' | 'down') => void;
}

export default function MessageBubble({ message, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={clsx(
        'flex gap-3 animate-slide-up',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={clsx(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold select-none',
          isUser
            ? 'bg-brand-600 text-white'
            : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
        )}
      >
        {isUser ? 'You' : 'AI'}
      </div>

      {/* Bubble */}
      <div
        className={clsx(
          'max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-brand-600 text-white rounded-tr-sm'
            : 'bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 shadow-sm border border-slate-100 dark:border-slate-700 rounded-tl-sm'
        )}
      >
        {/* Message content with Markdown rendering */}
        <div
          className={clsx(
            'prose prose-sm max-w-none',
            isUser
              ? 'prose-invert'
              : 'dark:prose-invert prose-slate'
          )}
        >
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        </div>

        {/* Footer: sources, confidence, regulation ref, latency, feedback (assistant only) */}
        {!isUser && (
          <div className="mt-2 space-y-2">
            {message.sources && message.sources.length > 0 && (
              <SourceList sources={message.sources} />
            )}

            {/* Confidence score + regulation reference */}
            {(message.confidence !== undefined || message.regulation_ref) && (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                {message.confidence !== undefined && (
                  <span
                    title="Internal benchmark confidence — not a guarantee"
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${
                      message.confidence >= 80
                        ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300'
                        : message.confidence >= 60
                          ? 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-700 text-amber-700 dark:text-amber-300'
                          : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300'
                    }`}
                  >
                    <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Confidence: {message.confidence}%
                  </span>
                )}
                {message.regulation_ref && (
                  <span
                    title="Relevant regulation or section cited"
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300"
                  >
                    <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    {message.regulation_ref}
                  </span>
                )}
              </div>
            )}

            <div className="flex items-center justify-between gap-2">
              {message.latency_ms !== undefined && (
                <LatencyBadge latencyMs={message.latency_ms} />
              )}
              <FeedbackButtons
                messageId={message.id}
                currentFeedback={message.feedback ?? null}
                onFeedback={onFeedback}
              />
            </div>

            {/* Explainability: why this answer */}
            <ExplainabilityPanel
              assumption={message.assumption}
              confidence={message.confidence}
              regulationRef={message.regulation_ref}
              intent={message.intent}
              strategy={message.strategy}
            />
          </div>
        )}
      </div>
    </div>
  );
}
