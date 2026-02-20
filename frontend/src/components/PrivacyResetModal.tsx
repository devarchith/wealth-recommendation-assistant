'use client';

import { useState, useRef, useEffect } from 'react';

export interface PrivacyResetModalProps {
  /** Human-readable name of what is being reset, e.g. "Rice Mill › Stock & Inventory" */
  targetLabel: string;
  /** Called when the user successfully confirms the reset */
  onConfirm: () => Promise<void> | void;
  /** Called when the user cancels */
  onCancel: () => void;
}

/**
 * Two-step confirmation modal for privacy reset.
 *
 * Step 1 — Warns the user with consequences.
 * Step 2 — Requires the user to manually type "RESET" before the button becomes active.
 *
 * This intentional friction prevents accidental or impulsive data deletion.
 */
export default function PrivacyResetModal({
  targetLabel,
  onConfirm,
  onCancel,
}: PrivacyResetModalProps) {
  const [step, setStep]           = useState<1 | 2>(1);
  const [typed, setTyped]         = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const inputRef                  = useRef<HTMLInputElement>(null);

  // Focus the input when we reach step 2
  useEffect(() => {
    if (step === 2) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [step]);

  const confirmed = typed === 'RESET';

  async function handleConfirm() {
    if (!confirmed) return;
    setIsLoading(true);
    setError(null);
    try {
      await onConfirm();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Reset failed. Please try again.');
      setIsLoading(false);
    }
  }

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="w-full max-w-md bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden">

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 bg-red-50 dark:bg-red-900/20 border-b border-red-200 dark:border-red-800">
          <div className="w-9 h-9 flex items-center justify-center rounded-full bg-red-100 dark:bg-red-900/40 shrink-0">
            <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          </div>
          <div>
            <p className="font-semibold text-red-800 dark:text-red-200 text-sm">Privacy Reset</p>
            <p className="text-xs text-red-600 dark:text-red-400 truncate max-w-[280px]">{targetLabel}</p>
          </div>
        </div>

        {/* Body */}
        <div className="px-5 py-5 space-y-4">
          {step === 1 && (
            <>
              <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                This will <strong>permanently overwrite</strong> your real data in{' '}
                <strong>{targetLabel}</strong> with placeholder values.
              </p>
              <ul className="text-sm text-slate-600 dark:text-slate-300 space-y-1.5">
                {[
                  'All selected data fields will be replaced with demo values.',
                  'Your account and login remain intact — only the data is reset.',
                  'This action cannot be undone.',
                  'Use this to clear data before sharing a demo or transferring your account.',
                ].map((point, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-red-500 mt-0.5 shrink-0">•</span>
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
              <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-lg">
                <p className="text-xs text-amber-700 dark:text-amber-300">
                  Regulation: Under India DPDP Act 2023 (Sec 13), you have the right to erase personal data.
                  This reset fulfils that right by replacing identifiable data with anonymised placeholders.
                </p>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <p className="text-sm text-slate-700 dark:text-slate-200">
                Type <strong className="font-mono text-red-600 dark:text-red-400">RESET</strong> below to confirm:
              </p>
              <input
                ref={inputRef}
                type="text"
                value={typed}
                onChange={e => setTyped(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && confirmed) handleConfirm(); }}
                placeholder="Type RESET"
                className={`w-full px-4 py-2.5 rounded-lg border text-sm font-mono transition-colors focus:outline-none focus:ring-2 ${
                  typed.length > 0 && !confirmed
                    ? 'border-red-300 dark:border-red-700 focus:ring-red-400 bg-red-50 dark:bg-red-900/10 text-red-700 dark:text-red-300'
                    : confirmed
                      ? 'border-green-400 dark:border-green-600 focus:ring-green-400 bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-300'
                      : 'border-slate-300 dark:border-slate-600 focus:ring-brand-400 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100'
                }`}
              />
              {typed.length > 0 && !confirmed && (
                <p className="text-xs text-red-600 dark:text-red-400">Must type exactly: RESET (all caps)</p>
              )}
              {error && (
                <p className="text-xs text-red-600 dark:text-red-400 p-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  {error}
                </p>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            Cancel
          </button>

          {step === 1 && (
            <button
              onClick={() => setStep(2)}
              className="px-4 py-2 text-sm rounded-lg bg-red-600 hover:bg-red-700 text-white font-medium transition-colors"
            >
              I understand — continue
            </button>
          )}

          {step === 2 && (
            <button
              onClick={handleConfirm}
              disabled={!confirmed || isLoading}
              className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors flex items-center gap-2 ${
                confirmed && !isLoading
                  ? 'bg-red-600 hover:bg-red-700 text-white'
                  : 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed'
              }`}
            >
              {isLoading ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  Resetting…
                </>
              ) : (
                'Confirm Reset'
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
