'use client';

import { useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ExplainabilityProps {
  /** Key assumption the AI made to generate this answer */
  assumption?: string;
  /** Confidence score 0–100 */
  confidence?: number;
  /** Regulation or section cited, e.g. "Sec 80C IT Act 1961" */
  regulationRef?: string;
  /** Intent detected by BERT pipeline, e.g. "tax" */
  intent?: string;
  /** Response strategy chosen by LinUCB, e.g. "intent_boosted" */
  strategy?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Collapsible explainability panel attached to each AI response.
 * Shows the assumption, confidence, regulation, intent and strategy
 * so users understand why the AI gave a particular answer.
 */
export default function ExplainabilityPanel({
  assumption,
  confidence,
  regulationRef,
  intent,
  strategy,
}: ExplainabilityProps) {
  const [open, setOpen] = useState(false);

  // Don't render if there's nothing to explain
  const hasContent = assumption || confidence !== undefined || regulationRef || intent || strategy;
  if (!hasContent) return null;

  const confidenceColor =
    confidence === undefined ? 'slate'
    : confidence >= 80 ? 'green'
    : confidence >= 60 ? 'amber'
    : 'red';

  return (
    <div className="mt-1.5">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-[11px] text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
        aria-expanded={open}
      >
        <svg
          className={`w-3 h-3 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        Why this answer?
      </button>

      {open && (
        <div className="mt-2 p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 space-y-2 text-[11px]">

          {/* Confidence */}
          {confidence !== undefined && (
            <div className="flex items-center gap-2">
              <svg className="w-3 h-3 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-slate-500 dark:text-slate-400">Confidence (benchmark):</span>
              <span className={`font-semibold text-${confidenceColor}-600 dark:text-${confidenceColor}-400`}>
                {confidence}%
              </span>
              <span className="text-slate-400 dark:text-slate-500">
                — measured on test dataset, not a guarantee
              </span>
            </div>
          )}

          {/* Assumption */}
          {assumption && (
            <div className="flex items-start gap-2">
              <svg className="w-3 h-3 shrink-0 text-slate-400 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <span className="text-slate-500 dark:text-slate-400">Key assumption: </span>
                <span className="text-slate-700 dark:text-slate-300">{assumption}</span>
              </div>
            </div>
          )}

          {/* Regulation reference */}
          {regulationRef && (
            <div className="flex items-center gap-2">
              <svg className="w-3 h-3 shrink-0 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              <span className="text-slate-500 dark:text-slate-400">Regulation cited:</span>
              <span className="font-medium text-blue-700 dark:text-blue-300">{regulationRef}</span>
            </div>
          )}

          {/* Intent detected */}
          {intent && (
            <div className="flex items-center gap-2">
              <svg className="w-3 h-3 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
              </svg>
              <span className="text-slate-500 dark:text-slate-400">Intent (BERT):</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">{intent}</span>
            </div>
          )}

          {/* RL strategy */}
          {strategy && (
            <div className="flex items-center gap-2">
              <svg className="w-3 h-3 shrink-0 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span className="text-slate-500 dark:text-slate-400">Strategy (LinUCB):</span>
              <span className="font-mono text-slate-700 dark:text-slate-300">{strategy}</span>
            </div>
          )}

          <p className="text-slate-400 dark:text-slate-500 pt-1 border-t border-slate-200 dark:border-slate-700">
            This answer is for educational purposes only. Always verify with a qualified CA or licensed adviser.
          </p>
        </div>
      )}
    </div>
  );
}
