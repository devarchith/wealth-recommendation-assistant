'use client';

import { useState, useRef, KeyboardEvent } from 'react';
import clsx from 'clsx';

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

const EXAMPLE_QUESTIONS = [
  'What is the 50/30/20 rule?',
  'How much should I save for retirement?',
  'Explain index fund investing',
  'How do I pay off debt faster?',
];

export default function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isLoading) return;
    onSend(text);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 150)}px`;
  };

  return (
    <div className="space-y-2">
      {/* Example questions (shown when input is empty) */}
      {!input && (
        <div className="flex flex-wrap gap-2 px-1">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => { setInput(q); textareaRef.current?.focus(); }}
              className="text-xs px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-600 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div className="flex items-end gap-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-600 rounded-2xl px-4 py-3 shadow-sm focus-within:ring-2 focus-within:ring-brand-500 focus-within:border-transparent transition-all">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          rows={1}
          placeholder="Ask about budgeting, investing, retirement…"
          disabled={isLoading}
          className="flex-1 resize-none bg-transparent text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 outline-none min-h-[24px] max-h-[150px] overflow-y-auto"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className={clsx(
            'flex-shrink-0 w-8 h-8 rounded-xl flex items-center justify-center transition-all',
            input.trim() && !isLoading
              ? 'bg-brand-600 hover:bg-brand-700 text-white shadow-sm'
              : 'bg-slate-100 dark:bg-slate-700 text-slate-400 cursor-not-allowed'
          )}
          aria-label="Send message"
        >
          <svg className="w-4 h-4 -rotate-45" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </div>
      <p className="text-xs text-center text-slate-400 dark:text-slate-500">
        Press Enter to send · Shift+Enter for new line
      </p>
    </div>
  );
}
