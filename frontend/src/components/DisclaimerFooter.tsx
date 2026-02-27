'use client';

/**
 * DisclaimerFooter
 * Appears at the bottom of every page / tab to clearly communicate
 * that AI output is educational, not licensed CA or financial advice.
 *
 * Complies with SEBI (IA) Regulations 2013 and ICAI guidelines which
 * restrict unregistered entities from rendering investment / tax advice.
 */
export default function DisclaimerFooter() {
  return (
    <footer className="mt-auto w-full border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/80">
      <div className="max-w-4xl mx-auto px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2">
        {/* Shield icon */}
        <svg
          className="w-4 h-4 text-slate-400 dark:text-slate-500 shrink-0"
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>

        <p className="text-[11px] leading-relaxed text-slate-400 dark:text-slate-500">
          <strong className="text-slate-500 dark:text-slate-400">Educational use only.</strong>{' '}
          WealthAdvisor AI provides general financial information for educational purposes.
          It is <strong>not</strong> a registered Investment Advisor (SEBI IA Reg. 2013),
          Chartered Accountant (ICAI), or licensed financial planner.
          Outputs should not be construed as professional tax, legal, or investment advice.
          Always consult a qualified CA / SEBI-registered IA before making financial decisions.
          Accuracy figures quoted are internal benchmarks on test datasets — not guarantees of
          performance on your specific queries.
          &nbsp;|&nbsp; India DPDP Act 2023 compliant.
        </p>
      </div>
    </footer>
  );
}
