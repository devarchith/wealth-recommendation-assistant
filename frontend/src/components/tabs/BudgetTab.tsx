'use client';

import { useState, useCallback } from 'react';
import clsx from 'clsx';

// ── Types ─────────────────────────────────────────────────────────────────

interface BudgetCategory {
  id: string;
  name: string;
  icon: string;
  allocated: number;
  spent: number;
  color: string;
  alertThreshold: number; // % of allocated before alert fires
}

interface SpendingAlert {
  id: string;
  categoryId: string;
  categoryName: string;
  message: string;
  severity: 'warning' | 'critical';
  timestamp: string;
}

// ── Default budget (50/30/20 seeded) ─────────────────────────────────────

const DEFAULT_INCOME = 5000;

const DEFAULT_CATEGORIES: BudgetCategory[] = [
  { id: 'housing',       name: 'Housing',       icon: '🏠', allocated: 1500, spent: 1500, color: 'bg-blue-500',   alertThreshold: 90 },
  { id: 'food',          name: 'Food',           icon: '🛒', allocated: 500,  spent: 420,  color: 'bg-green-500',  alertThreshold: 80 },
  { id: 'transport',     name: 'Transport',      icon: '🚗', allocated: 300,  spent: 310,  color: 'bg-yellow-500', alertThreshold: 90 },
  { id: 'utilities',     name: 'Utilities',      icon: '⚡', allocated: 200,  spent: 185,  color: 'bg-orange-500', alertThreshold: 90 },
  { id: 'entertainment', name: 'Entertainment',  icon: '🎬', allocated: 300,  spent: 275,  color: 'bg-purple-500', alertThreshold: 85 },
  { id: 'dining',        name: 'Dining Out',     icon: '🍽️', allocated: 200,  spent: 240,  color: 'bg-red-500',    alertThreshold: 80 },
  { id: 'savings',       name: 'Savings',        icon: '💰', allocated: 1000, spent: 1000, color: 'bg-emerald-500',alertThreshold: 100 },
  { id: 'emergency',     name: 'Emergency Fund', icon: '🛡️', allocated: 500,  spent: 500,  color: 'bg-teal-500',   alertThreshold: 100 },
  { id: 'investments',   name: 'Investments',    icon: '📈', allocated: 500,  spent: 500,  color: 'bg-indigo-500', alertThreshold: 100 },
];

// ── Helpers ───────────────────────────────────────────────────────────────

function computeAlerts(categories: BudgetCategory[]): SpendingAlert[] {
  const alerts: SpendingAlert[] = [];
  for (const cat of categories) {
    const pct = cat.allocated > 0 ? (cat.spent / cat.allocated) * 100 : 0;
    if (pct >= 100) {
      alerts.push({
        id: `${cat.id}-critical`,
        categoryId: cat.id,
        categoryName: cat.name,
        message: `${cat.name} is over budget by $${(cat.spent - cat.allocated).toFixed(0)}!`,
        severity: 'critical',
        timestamp: new Date().toISOString(),
      });
    } else if (pct >= cat.alertThreshold) {
      alerts.push({
        id: `${cat.id}-warning`,
        categoryId: cat.id,
        categoryName: cat.name,
        message: `${cat.name} is at ${pct.toFixed(0)}% of budget ($${(cat.allocated - cat.spent).toFixed(0)} remaining).`,
        severity: 'warning',
        timestamp: new Date().toISOString(),
      });
    }
  }
  return alerts;
}

// ── Progress Bar ──────────────────────────────────────────────────────────

function ProgressBar({ spent, allocated, color }: { spent: number; allocated: number; color: string }) {
  const pct = allocated > 0 ? Math.min((spent / allocated) * 100, 100) : 0;
  const overBudget = spent > allocated;
  return (
    <div className="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
      <div
        className={clsx('h-2 rounded-full transition-all duration-500', overBudget ? 'bg-red-500' : color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ── Budget Tab Component ──────────────────────────────────────────────────

export default function BudgetTab() {
  const [income, setIncome] = useState(DEFAULT_INCOME);
  const [categories, setCategories] = useState<BudgetCategory[]>(DEFAULT_CATEGORIES);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [dismissedAlerts, setDismissedAlerts] = useState<Set<string>>(new Set());

  const alerts = computeAlerts(categories).filter(a => !dismissedAlerts.has(a.id));

  const totalAllocated = categories.reduce((s, c) => s + c.allocated, 0);
  const totalSpent = categories.reduce((s, c) => s + c.spent, 0);
  const needs = categories.filter(c => ['housing','food','transport','utilities'].includes(c.id));
  const wants = categories.filter(c => ['entertainment','dining'].includes(c.id));
  const savingsInv = categories.filter(c => ['savings','emergency','investments'].includes(c.id));

  const needsPct  = Math.round(needs.reduce((s,c) => s+c.allocated,0) / income * 100);
  const wantsPct  = Math.round(wants.reduce((s,c) => s+c.allocated,0) / income * 100);
  const savingsPct = Math.round(savingsInv.reduce((s,c) => s+c.allocated,0) / income * 100);

  const updateSpent = useCallback((id: string, value: number) => {
    setCategories(prev => prev.map(c => c.id === id ? { ...c, spent: Math.max(0, value) } : c));
  }, []);

  const dismissAlert = useCallback((alertId: string) => {
    setDismissedAlerts(prev => new Set([...prev, alertId]));
  }, []);

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Real-time alerts ──────────────────────────────────────────── */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500" />
            </span>
            Real-Time Spending Alerts
          </h3>
          {alerts.map(alert => (
            <div
              key={alert.id}
              className={clsx(
                'flex items-start justify-between gap-3 rounded-lg px-4 py-3 text-sm border animate-slide-up',
                alert.severity === 'critical'
                  ? 'bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-700 text-red-800 dark:text-red-200'
                  : 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-700 text-yellow-800 dark:text-yellow-200'
              )}
            >
              <span>{alert.severity === 'critical' ? '🚨' : '⚠️'} {alert.message}</span>
              <button
                onClick={() => dismissAlert(alert.id)}
                className="text-xs opacity-60 hover:opacity-100 flex-shrink-0"
              >
                Dismiss
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Income + 50/30/20 summary ─────────────────────────────────── */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 p-4 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Monthly Budget Overview</h3>
          <div className="flex items-center gap-2 text-sm">
            <label className="text-slate-500 dark:text-slate-400">Income:</label>
            <span className="font-medium text-slate-800 dark:text-slate-100">$</span>
            <input
              type="number"
              value={income}
              onChange={e => setIncome(Number(e.target.value))}
              className="w-24 text-sm font-medium bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-2 py-1 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>

        {/* 50/30/20 gauge */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Needs', pct: needsPct, target: 50, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-100 dark:bg-blue-900/40' },
            { label: 'Wants', pct: wantsPct, target: 30, color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-100 dark:bg-purple-900/40' },
            { label: 'Savings', pct: savingsPct, target: 20, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-100 dark:bg-emerald-900/40' },
          ].map(({ label, pct, target, color, bg }) => (
            <div key={label} className={clsx('rounded-lg p-3 text-center', bg)}>
              <p className={clsx('text-2xl font-bold', color)}>{pct}%</p>
              <p className="text-xs font-medium text-slate-600 dark:text-slate-400">{label}</p>
              <p className="text-xs text-slate-400 dark:text-slate-500">target {target}%</p>
            </div>
          ))}
        </div>

        <div className="flex justify-between text-xs text-slate-500 dark:text-slate-400 pt-1">
          <span>Total allocated: <b className="text-slate-700 dark:text-slate-200">${totalAllocated.toLocaleString()}</b></span>
          <span>Total spent: <b className={totalSpent > income ? 'text-red-500' : 'text-emerald-600 dark:text-emerald-400'}>${totalSpent.toLocaleString()}</b></span>
        </div>
      </div>

      {/* ── Category breakdown ────────────────────────────────────────── */}
      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Category Breakdown</h3>
        <div className="space-y-2">
          {categories.map(cat => {
            const pct = cat.allocated > 0 ? (cat.spent / cat.allocated) * 100 : 0;
            const overBudget = cat.spent > cat.allocated;
            const editing = editingId === cat.id;
            return (
              <div key={cat.id} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 px-4 py-3">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-lg">{cat.icon}</span>
                  <span className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-200">{cat.name}</span>
                  <div className="flex items-center gap-1 text-xs">
                    {editing ? (
                      <input
                        autoFocus
                        type="number"
                        defaultValue={cat.spent}
                        onBlur={e => { updateSpent(cat.id, Number(e.target.value)); setEditingId(null); }}
                        onKeyDown={e => { if (e.key === 'Enter') { updateSpent(cat.id, Number((e.target as HTMLInputElement).value)); setEditingId(null); } }}
                        className="w-20 text-xs bg-slate-50 dark:bg-slate-700 border border-brand-400 rounded px-2 py-0.5 outline-none"
                      />
                    ) : (
                      <button onClick={() => setEditingId(cat.id)} className={clsx('font-semibold', overBudget ? 'text-red-500' : 'text-slate-700 dark:text-slate-200')}>
                        ${cat.spent.toLocaleString()}
                      </button>
                    )}
                    <span className="text-slate-400 dark:text-slate-500">/ ${cat.allocated.toLocaleString()}</span>
                    <span className={clsx('ml-1 px-1.5 py-0.5 rounded-full text-xs font-medium',
                      overBudget ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                                 : 'bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-300'
                    )}>
                      {pct.toFixed(0)}%
                    </span>
                  </div>
                </div>
                <ProgressBar spent={cat.spent} allocated={cat.allocated} color={cat.color} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
