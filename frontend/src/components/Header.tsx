'use client';

interface HeaderProps {
  isDark: boolean;
  onToggleDark: () => void;
  onClear: () => void;
  /** Active role label shown in header, e.g. "⚖️ CA Professional" */
  roleLabel?: string;
  /** Called when the user wants to switch to a different role workspace */
  onSwitchRole?: () => void;
}

export default function Header({ isDark, onToggleDark, onClear, roleLabel, onSwitchRole }: HeaderProps) {
  return (
    <header className="sticky top-0 z-10 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 shadow-sm">
      <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
        {/* Logo + title */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-sm select-none">
            W
          </div>
          <div>
            <p className="font-semibold text-slate-900 dark:text-white text-sm leading-tight">
              WealthAdvisor AI
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-tight">
              {roleLabel
                ? <span className="font-medium text-brand-600 dark:text-brand-400">{roleLabel}</span>
                : 'RAG + LangChain · Internal benchmark F1@4: 0.92'
              }
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {onSwitchRole && (
            <button
              onClick={onSwitchRole}
              className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              title="Switch workspace role"
            >
              Switch role
            </button>
          )}
          <button
            onClick={onClear}
            className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            title="Clear conversation"
          >
            New chat
          </button>
          <button
            onClick={onToggleDark}
            className="p-1.5 rounded-lg text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label="Toggle dark mode"
          >
            {isDark ? (
              /* Sun icon */
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707M17.657 17.657l-.707-.707M6.343 6.343l-.707-.707M12 7a5 5 0 100 10A5 5 0 0012 7z" />
              </svg>
            ) : (
              /* Moon icon */
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
              </svg>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
