'use client';

import { useState } from 'react';
import { Source } from '@/types/chat';

interface SourceListProps {
  sources: Source[];
}

const CATEGORY_COLORS: Record<string, string> = {
  budgeting:  'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
  savings:    'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  investing:  'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  retirement: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
  debt:       'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  tax:        'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300',
  insurance:  'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300',
  wealth:     'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300',
};

export default function SourceList({ sources }: SourceListProps) {
  const [expanded, setExpanded] = useState(false);

  if (!sources.length) return null;

  return (
    <div className="border-t border-slate-100 dark:border-slate-700 pt-2 mt-2">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        {sources.length} source{sources.length > 1 ? 's' : ''}
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <ul className="mt-2 space-y-2">
          {sources.map((src, i) => {
            const colorClass = CATEGORY_COLORS[src.category] ?? 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300';
            return (
              <li key={i} className="rounded-lg bg-slate-50 dark:bg-slate-700/50 p-2 border border-slate-100 dark:border-slate-600">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${colorClass}`}>
                    {src.category}
                  </span>
                  <span className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">
                    {src.title}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2">
                  {src.snippet}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
