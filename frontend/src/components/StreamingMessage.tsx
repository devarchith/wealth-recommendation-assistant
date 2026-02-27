'use client';

import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { streamChatMessage, fetchChatMessage } from '@/lib/streamingClient';
import { Source } from '@/types/chat';

interface StreamingMessageProps {
  message: string;
  onComplete: (params: {
    content: string;
    sources: Source[];
    latencyMs: number;
    messageId: string;
  }) => void;
  onError: (error: string) => void;
}

/**
 * Renders an assistant message that streams in token-by-token via SSE.
 * Falls back to the non-streaming endpoint if SSE is unavailable.
 */
export default function StreamingMessage({ message, onComplete, onError }: StreamingMessageProps) {
  const [tokens, setTokens] = useState('');
  const [isStreaming, setIsStreaming] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;

    let accumulated = '';
    let sources: Source[] = [];

    async function run() {
      try {
        await streamChatMessage(
          message,
          {
            onToken: (token) => {
              accumulated += token;
              setTokens(accumulated);
            },
            onSources: (s) => {
              sources = s as Source[];
            },
            onDone: (latencyMs, messageId) => {
              setIsStreaming(false);
              onComplete({ content: accumulated, sources, latencyMs, messageId });
            },
            onError: async (err) => {
              // SSE endpoint may not be available — fall back to non-streaming
              console.warn('[StreamingMessage] SSE error, falling back:', err);
              try {
                const data = await fetchChatMessage(message);
                setTokens(data.answer);
                setIsStreaming(false);
                onComplete({
                  content: data.answer,
                  sources: data.sources as Source[],
                  latencyMs: data.latency_ms,
                  messageId: data.message_id,
                });
              } catch (fallbackErr: unknown) {
                const msg = fallbackErr instanceof Error ? fallbackErr.message : 'Unknown error';
                setIsStreaming(false);
                onError(msg);
              }
            },
          },
          controller.signal
        );
      } catch (err: unknown) {
        if ((err as Error).name === 'AbortError') return;
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setIsStreaming(false);
        onError(msg);
      }
    }

    run();
    return () => controller.abort();
  }, [message, onComplete, onError]);

  return (
    <div className="prose prose-sm dark:prose-invert prose-slate max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{tokens}</ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-0.5 h-4 bg-brand-500 animate-pulse ml-0.5 align-middle" />
      )}
    </div>
  );
}
