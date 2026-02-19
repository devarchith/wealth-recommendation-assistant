'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import clsx from 'clsx';
import { Message } from '@/types/chat';
import SourceList from './SourceList';
import FeedbackButtons from './FeedbackButtons';
import LatencyBadge from './LatencyBadge';

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

        {/* Footer: sources, latency, feedback (assistant only) */}
        {!isUser && (
          <div className="mt-2 space-y-2">
            {message.sources && message.sources.length > 0 && (
              <SourceList sources={message.sources} />
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
          </div>
        )}
      </div>
    </div>
  );
}
