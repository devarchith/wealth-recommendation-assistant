'use client';

import { useEffect, useRef } from 'react';
import { Message } from '@/types/chat';
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  onFeedback: (messageId: string, rating: 'up' | 'down') => void;
}

export default function MessageList({ messages, isLoading, onFeedback }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto chat-scroll py-4 space-y-2">
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          onFeedback={onFeedback}
        />
      ))}

      {isLoading && <TypingIndicator />}

      <div ref={bottomRef} />
    </div>
  );
}
