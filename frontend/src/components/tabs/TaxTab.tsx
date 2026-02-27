'use client';

import { useState, useEffect } from 'react';
import clsx from 'clsx';

// ── Types ─────────────────────────────────────────────────────────────────

interface TaxDeadline {
  id: string;
  title: string;
  date: string; // ISO date
  description: string;
  form?: string;
  urgent: boolean;
  category: 'filing' | 'payment' | 'estimated' | 'retirement';
}

interface TaxBracket {
  min: number;
  max: number | null;
  rate: number;
}

// ── 2024 Tax Deadlines ────────────────────────────────────────────────────

const TAX_DEADLINES_2024: TaxDeadline[] = [
  { id: 'q1-est',    title: 'Q1 Estimated Tax Payment',      date: '2024-04-15', description: 'First quarter estimated tax payment for self-employed and those with significant investment income.', form: 'Form 1040-ES', urgent: false, category: 'estimated' },
  { id: 'main-file', title: 'Tax Return Filing Deadline',    date: '2024-04-15', description: 'Deadline to file 2023 federal income tax return or request a 6-month extension (Form 4868).', form: 'Form 1040',    urgent: false, category: 'filing' },
  { id: 'ira-2023',  title: '2023 IRA Contribution Deadline', date: '2024-04-15', description: 'Last day to make a 2023 Traditional or Roth IRA contribution ($6,500 limit; $7,500 if 50+).', form: undefined,   urgent: false, category: 'retirement' },
  { id: 'q2-est',    title: 'Q2 Estimated Tax Payment',      date: '2024-06-17', description: 'Second quarter estimated tax payment covering April 1 – May 31 income.', form: 'Form 1040-ES', urgent: false, category: 'estimated' },
  { id: 'q3-est',    title: 'Q3 Estimated Tax Payment',      date: '2024-09-16', description: 'Third quarter estimated tax payment covering June 1 – August 31 income.', form: 'Form 1040-ES', urgent: false, category: 'estimated' },
  { id: 'ext-file',  title: 'Extended Filing Deadline',      date: '2024-10-15', description: 'Deadline for returns filed on extension. Note: extension to file, NOT extension to pay — taxes were due April 15.', form: 'Form 1040', urgent: false, category: 'filing' },
  { id: 'q4-est',    title: 'Q4 Estimated Tax Payment',      date: '2025-01-15', description: 'Fourth quarter estimated tax payment covering September 1 – December 31 income.', form: 'Form 1040-ES', urgent: false, category: 'estimated' },
  { id: 'ira-2024',  title: '2024 IRA Contribution Deadline', date: '2025-04-15', description: 'Last day to make a 2024 IRA contribution ($7,000 limit; $8,000 if 50+). Roth income limits apply.', form: undefined,  urgent: false, category: 'retirement' },
];

// ── 2024 Tax Brackets (Single) ────────────────────────────────────────────

const BRACKETS_SINGLE_2024: TaxBracket[] = [
  { min: 0,       max: 11600,  rate: 10 },
  { min: 11600,   max: 47150,  rate: 12 },
  { min: 47150,   max: 100525, rate: 22 },
  { min: 100525,  max: 191950, rate: 24 },
  { min: 191950,  max: 243725, rate: 32 },
  { min: 243725,  max: 609350, rate: 35 },
  { min: 609350,  max: null,   rate: 37 },
];

const BRACKETS_MFJ_2024: TaxBracket[] = [
  { min: 0,       max: 23200,  rate: 10 },
  { min: 23200,   max: 94300,  rate: 12 },
  { min: 94300,   max: 201050, rate: 22 },
  { min: 201050,  max: 383900, rate: 24 },
  { min: 383900,  max: 487450, rate: 32 },
  { min: 487450,  max: 731200, rate: 35 },
  { min: 731200,  max: null,   rate: 37 },
];

const STANDARD_DEDUCTIONS_2024 = {
  single: 14600,
  mfj:    29200,
};

// ── Tax calculator helper ─────────────────────────────────────────────────

function calcTax(income: number, brackets: TaxBracket[]): { tax: number; effectiveRate: number; marginalRate: number } {
  let tax = 0;
  let marginal = 0;
  for (const bracket of brackets) {
    if (income <= bracket.min) break;
    const upper = bracket.max ?? Infinity;
    const taxable = Math.min(income, upper) - bracket.min;
    if (taxable > 0) {
      tax += taxable * (bracket.rate / 100);
      marginal = bracket.rate;
    }
  }
  return {
    tax: Math.round(tax),
    effectiveRate: income > 0 ? Math.round((tax / income) * 1000) / 10 : 0,
    marginalRate: marginal,
  };
}

// ── Deadline countdown ────────────────────────────────────────────────────

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - today.getTime()) / 86400000);
}

function DeadlineCard({ deadline }: { deadline: TaxDeadline & { daysLeft: number } }) {
  const past = deadline.daysLeft < 0;
  const imminent = !past && deadline.daysLeft <= 30;
  const soon = !past && !imminent && deadline.daysLeft <= 90;

  const CATEGORY_COLOR: Record<string, string> = {
    filing:     'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    payment:    'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    estimated:  'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300',
    retirement: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  };

  return (
    <div className={clsx(
      'rounded-xl border p-4 transition-all',
      past      ? 'opacity-50 border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800'
      : imminent ? 'border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20'
      : soon     ? 'border-yellow-300 dark:border-yellow-700 bg-yellow-50 dark:bg-yellow-900/20'
                 : 'border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-800'
    )}>
      <div className="flex flex-wrap items-start justify-between gap-2 mb-1">
        <div className="flex items-center gap-2">
          {imminent && !past && <span className="relative flex h-2 w-2 flex-shrink-0"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"/><span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"/></span>}
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{deadline.title}</span>
        </div>
        <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', CATEGORY_COLOR[deadline.category])}>
          {deadline.category}
        </span>
      </div>
      <div className="flex items-center gap-3 mb-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">
          📅 {new Date(deadline.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
        </span>
        {deadline.form && <span className="text-xs text-slate-400 dark:text-slate-500">{deadline.form}</span>}
        <span className={clsx('text-xs font-semibold ml-auto',
          past ? 'text-slate-400' : imminent ? 'text-red-600 dark:text-red-400' : soon ? 'text-yellow-600 dark:text-yellow-400' : 'text-slate-500 dark:text-slate-400'
        )}>
          {past ? 'Passed' : `${deadline.daysLeft}d away`}
        </span>
      </div>
      <p className="text-xs text-slate-600 dark:text-slate-400">{deadline.description}</p>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export default function TaxTab() {
  const [filingStatus, setFilingStatus] = useState<'single' | 'mfj'>('single');
  const [grossIncome, setGrossIncome] = useState(75000);
  const [showPast, setShowPast] = useState(false);
  const [activeFilter, setActiveFilter] = useState<string>('all');

  const brackets = filingStatus === 'single' ? BRACKETS_SINGLE_2024 : BRACKETS_MFJ_2024;
  const stdDeduction = STANDARD_DEDUCTIONS_2024[filingStatus];
  const taxableIncome = Math.max(0, grossIncome - stdDeduction);
  const { tax, effectiveRate, marginalRate } = calcTax(taxableIncome, brackets);

  const deadlinesWithCountdown = TAX_DEADLINES_2024.map(d => ({
    ...d,
    daysLeft: daysUntil(d.date),
  })).sort((a, b) => a.daysLeft - b.daysLeft);

  const filtered = deadlinesWithCountdown.filter(d => {
    if (!showPast && d.daysLeft < 0) return false;
    if (activeFilter !== 'all' && d.category !== activeFilter) return false;
    return true;
  });

  const imminentCount = deadlinesWithCountdown.filter(d => d.daysLeft >= 0 && d.daysLeft <= 30).length;

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Upcoming deadline alert ───────────────────────────────────── */}
      {imminentCount > 0 && (
        <div className="flex items-center gap-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-xl px-4 py-3">
          <span className="relative flex h-2.5 w-2.5 flex-shrink-0"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"/><span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"/></span>
          <p className="text-sm text-red-700 dark:text-red-300 font-medium">
            {imminentCount} tax deadline{imminentCount > 1 ? 's' : ''} within the next 30 days
          </p>
        </div>
      )}

      {/* ── Tax estimator ─────────────────────────────────────────────── */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 p-4 space-y-4">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100">2024 Tax Estimator</h3>

        <div className="grid grid-cols-2 gap-4">
          {/* Filing status */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Filing Status</label>
            <div className="flex rounded-lg overflow-hidden border border-slate-200 dark:border-slate-600">
              {(['single', 'mfj'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => setFilingStatus(s)}
                  className={clsx(
                    'flex-1 text-xs py-1.5 font-medium transition-colors',
                    filingStatus === s
                      ? 'bg-brand-600 text-white'
                      : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
                  )}
                >
                  {s === 'single' ? 'Single' : 'Married (MFJ)'}
                </button>
              ))}
            </div>
          </div>

          {/* Gross income */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Gross Income (2024)</label>
            <div className="flex items-center gap-1 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-1.5 bg-slate-50 dark:bg-slate-700">
              <span className="text-sm text-slate-500">$</span>
              <input
                type="number"
                value={grossIncome}
                onChange={e => setGrossIncome(Number(e.target.value))}
                className="flex-1 text-sm bg-transparent text-slate-800 dark:text-slate-100 outline-none"
              />
            </div>
          </div>
        </div>

        {/* Results */}
        <div className="grid grid-cols-3 gap-3 pt-1">
          {[
            { label: 'Estimated Tax', value: `$${tax.toLocaleString()}`, color: 'text-red-600 dark:text-red-400' },
            { label: 'Effective Rate', value: `${effectiveRate}%`, color: 'text-yellow-600 dark:text-yellow-400' },
            { label: 'Marginal Rate', value: `${marginalRate}%`, color: 'text-orange-600 dark:text-orange-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3 text-center">
              <p className={clsx('text-xl font-bold', color)}>{value}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
            </div>
          ))}
        </div>

        <p className="text-xs text-slate-400 dark:text-slate-500">
          Standard deduction applied: ${stdDeduction.toLocaleString()} → taxable income: ${taxableIncome.toLocaleString()}. Estimate only — consult a tax professional for accurate filing.
        </p>
      </div>

      {/* ── Filing deadlines ──────────────────────────────────────────── */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Filing Deadlines & Reminders</h3>
          <div className="flex items-center gap-2">
            {(['all', 'filing', 'estimated', 'retirement'] as const).map(f => (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={clsx(
                  'text-xs px-2.5 py-1 rounded-full border transition-colors',
                  activeFilter === f
                    ? 'bg-brand-600 border-brand-600 text-white'
                    : 'border-slate-200 dark:border-slate-600 text-slate-500 dark:text-slate-400 hover:border-slate-300'
                )}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          {filtered.map(d => <DeadlineCard key={d.id} deadline={d} />)}
        </div>

        <button
          onClick={() => setShowPast(v => !v)}
          className="text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
        >
          {showPast ? '▲ Hide past deadlines' : '▼ Show past deadlines'}
        </button>
      </div>
    </div>
  );
}
