'use client';

import { useState, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import MessageList from './MessageList';
import ChatInput from './ChatInput';
import Header from './Header';
import TabBar from './tabs/TabBar';
import DisclaimerFooter from './DisclaimerFooter';
import { Message, ApiChatResponse } from '@/types/chat';
import { sendMessage, sendFeedback } from '@/lib/apiClient';

const WELCOME_MESSAGE: Message = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hello! I'm **WealthAdvisor AI**, your personal finance assistant. I can help you with:\n\n" +
    '- **Budgeting** — 50/30/20 rule, emergency funds\n' +
    '- **Investing** — index funds, dollar-cost averaging, asset allocation\n' +
    '- **Retirement** — 401(k), IRA, Social Security optimization\n' +
    '- **Debt management** — avalanche vs snowball, mortgages\n' +
    '- **Tax planning** — tax-loss harvesting, HSA strategy\n\n' +
    'Ask me anything about your financial goals!',
  sources: [],
  timestamp: new Date().toISOString(),
};

export default function ChatLayout() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDark, setIsDark] = useState(false);

  const toggleDark = useCallback(() => {
    setIsDark((prev) => {
      const next = !prev;
      document.documentElement.classList.toggle('dark', next);
      return next;
    });
  }, []);

  const handleSend = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;
    setError(null);

    const userMsg: Message = {
      id: uuidv4(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };

    // Optimistic UI — add user message immediately
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const data: ApiChatResponse = await sendMessage(text.trim());
      const assistantMsg: Message = {
        id: data.message_id,
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        latency_ms: data.latency_ms,
        timestamp: new Date().toISOString(),
        feedback: null,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'An error occurred. Please try again.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, [isLoading]);

  const handleFeedback = useCallback(async (messageId: string, rating: 'up' | 'down') => {
    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, feedback: rating } : m))
    );
    try {
      await sendFeedback(messageId, rating);
    } catch {
      // Best-effort — don't surface feedback errors to the user
    }
  }, []);

  const handleClearSession = useCallback(async () => {
    try {
      await fetch('/api/session', { method: 'DELETE', credentials: 'include' });
    } catch { /* ignore */ }
    setMessages([WELCOME_MESSAGE]);
    setError(null);
  }, []);

  const chatPanel = (
    <>
      <MessageList
        messages={messages}
        isLoading={isLoading}
        onFeedback={handleFeedback}
      />

      {error && (
        <div className="mx-2 mb-2 px-4 py-2 rounded-lg bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 text-red-700 dark:text-red-300 text-sm animate-fade-in">
          {error}
        </div>
      )}

      <ChatInput onSend={handleSend} isLoading={isLoading} />
    </>
  );

  return (
    <div className="flex flex-col h-screen bg-slate-50 dark:bg-slate-900 transition-colors duration-200">
      <Header isDark={isDark} onToggleDark={toggleDark} onClear={handleClearSession} />

      <main className="flex-1 overflow-hidden flex flex-col">
        <TabBar chatContent={chatPanel} />
      </main>

      <DisclaimerFooter />
    </div>
  );
}
