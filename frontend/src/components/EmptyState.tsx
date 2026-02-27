'use client';

/**
 * Displayed when the chat has no messages yet (after clearing a session).
 * Responsive layout with suggestion cards for common financial queries.
 */

const SUGGESTIONS = [
  { icon: '💰', title: 'Build an emergency fund', q: 'How much should I save in an emergency fund?' },
  { icon: '📈', title: 'Start investing', q: 'What is the best way to start investing as a beginner?' },
  { icon: '🏦', title: 'Maximize retirement', q: 'How do I maximize my 401(k) and IRA contributions?' },
  { icon: '💳', title: 'Pay off debt', q: 'What is the fastest way to pay off credit card debt?' },
];

interface EmptyStateProps {
  onSuggest: (question: string) => void;
}

export default function EmptyState({ onSuggest }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 py-12 px-4 text-center animate-fade-in">
      <div className="w-16 h-16 rounded-2xl bg-brand-100 dark:bg-brand-900/40 flex items-center justify-center text-3xl mb-4">
        💼
      </div>
      <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-100 mb-2">
        WealthAdvisor AI
      </h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm mb-8">
        Ask me anything about personal finance — budgeting, investing,
        retirement planning, debt management, and more.
      </p>

      {/* Suggestion grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.q}
            onClick={() => onSuggest(s.q)}
            className="flex items-start gap-3 p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-brand-300 dark:hover:border-brand-600 hover:shadow-sm transition-all text-left group"
          >
            <span className="text-xl flex-shrink-0">{s.icon}</span>
            <div>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-200 group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
                {s.title}
              </p>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 line-clamp-1">
                {s.q}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
