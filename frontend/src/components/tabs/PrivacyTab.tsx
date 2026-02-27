'use client';

import { useState, useCallback } from 'react';
import PrivacyResetModal from '@/components/PrivacyResetModal';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CategoryOption {
  key:   string;
  label: string;
}

interface ModuleConfig {
  module:      string;
  label:       string;
  icon:        string;
  description: string;
  categories:  CategoryOption[];
}

// ---------------------------------------------------------------------------
// Module definitions (mirrors api-gateway/src/services/privacyPlaceholders.js)
// ---------------------------------------------------------------------------

const MODULES: ModuleConfig[] = [
  {
    module: 'rice_mill',
    label:  'Rice Mill',
    icon:   '🌾',
    description: 'Milling operations, stock levels, GST records, and FCI billing data.',
    categories: [
      { key: 'stock',      label: 'Stock & Inventory'      },
      { key: 'financials', label: 'Financial Records'      },
      { key: 'compliance', label: 'GST & Compliance'       },
      { key: 'milling',    label: 'Milling Logs'           },
    ],
  },
  {
    module: 'ca',
    label:  'CA Portal',
    icon:   '⚖️',
    description: 'Client roster, billing data, and tax notice records.',
    categories: [
      { key: 'clients', label: 'Client Records'       },
      { key: 'billing', label: 'Billing & Revenue'    },
      { key: 'notices', label: 'Tax Notice Records'   },
    ],
  },
  {
    module: 'business',
    label:  'Business',
    icon:   '🏪',
    description: 'P&L records, receivables, payables, payroll, and GST filings.',
    categories: [
      { key: 'pl',       label: 'P&L Records'              },
      { key: 'cashflow', label: 'Receivables & Payables'   },
      { key: 'payroll',  label: 'Payroll & Statutory'      },
      { key: 'gst',      label: 'GST Filing Records'       },
    ],
  },
  {
    module: 'budget',
    label:  'Budget',
    icon:   '📊',
    description: 'Monthly income and category-wise spending data.',
    categories: [
      { key: 'income',   label: 'Income Records'    },
      { key: 'spending', label: 'Spending Data'     },
    ],
  },
  {
    module: 'investment',
    label:  'Investment',
    icon:   '📈',
    description: 'Portfolio holdings, allocation, and XIRR records.',
    categories: [
      { key: 'portfolio', label: 'Portfolio Holdings' },
    ],
  },
  {
    module: 'personal',
    label:  'Profile',
    icon:   '👤',
    description: 'Name, contact information, PAN, and GSTIN.',
    categories: [
      { key: 'profile', label: 'Profile Information' },
    ],
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function callPrivacyReset(module: string, categories: string[]) {
  const res = await fetch('/api/privacy/reset', {
    method:      'POST',
    credentials: 'include',
    headers:     { 'Content-Type': 'application/json' },
    body:        JSON.stringify({ module, categories, confirm: 'RESET' }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { message?: string }).message || `Reset failed (${res.status})`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ModuleCard({
  mod,
  onReset,
}: {
  mod: ModuleConfig;
  onReset: (mod: ModuleConfig, selected: string[]) => void;
}) {
  const [selected, setSelected] = useState<Set<string>>(new Set(mod.categories.map(c => c.key)));
  const [lastReset, setLastReset] = useState<string | null>(null);

  const toggleAll = () => {
    if (selected.size === mod.categories.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(mod.categories.map(c => c.key)));
    }
  };

  const toggle = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const handleReset = () => {
    if (selected.size === 0) return;
    onReset(mod, Array.from(selected));
  };

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      {/* Module header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl">{mod.icon}</span>
          <div>
            <p className="font-semibold text-slate-900 dark:text-slate-100 text-sm">{mod.label}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 max-w-xs">{mod.description}</p>
          </div>
        </div>
        {lastReset && (
          <span className="text-xs text-green-600 dark:text-green-400 shrink-0 mt-0.5">
            Reset {lastReset}
          </span>
        )}
      </div>

      {/* Category checkboxes */}
      <div className="space-y-1.5 mb-4">
        <label className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={selected.size === mod.categories.length}
            onChange={toggleAll}
            className="accent-brand-600 w-3.5 h-3.5"
          />
          Select all
        </label>
        <div className="ml-1 grid grid-cols-2 gap-1.5">
          {mod.categories.map(cat => (
            <label key={cat.key} className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={selected.has(cat.key)}
                onChange={() => toggle(cat.key)}
                className="accent-brand-600 w-3.5 h-3.5 shrink-0"
              />
              <span className="truncate">{cat.label}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Reset button */}
      <button
        onClick={handleReset}
        disabled={selected.size === 0}
        className={`w-full py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
          selected.size > 0
            ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/30'
            : 'bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed border border-transparent'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
        Reset {selected.size > 0 ? `${selected.size} categor${selected.size > 1 ? 'ies' : 'y'}` : 'data'}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PrivacyTab() {
  const [modalState, setModalState] = useState<{
    mod:        ModuleConfig;
    selected:   string[];
    targetLabel: string;
  } | null>(null);

  const [successLog, setSuccessLog] = useState<string[]>([]);

  const handleResetRequest = useCallback((mod: ModuleConfig, selected: string[]) => {
    const catLabels = selected
      .map(k => mod.categories.find(c => c.key === k)?.label ?? k)
      .join(', ');
    setModalState({ mod, selected, targetLabel: `${mod.label} › ${catLabels}` });
  }, []);

  const handleConfirm = useCallback(async () => {
    if (!modalState) return;
    await callPrivacyReset(modalState.mod.module, modalState.selected);
    const ts = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    setSuccessLog(prev => [`${modalState.targetLabel} — reset at ${ts}`, ...prev.slice(0, 4)]);
    setModalState(null);
  }, [modalState]);

  const handleCancel = useCallback(() => setModalState(null), []);

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Data Privacy Center</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Selectively reset module data to placeholders — your account and login are never affected.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 text-xs font-medium shrink-0">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
          </svg>
          DPDP Act 2023 — Right to Erasure
        </span>
      </div>

      {/* Info banner */}
      <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl text-sm text-amber-700 dark:text-amber-300">
        <strong>What this does:</strong> Selected data fields are overwritten with realistic placeholder values.
        Your account structure, login, and subscription remain intact. This is useful before sharing a demo,
        transferring your account, or exercising your right to data erasure under the DPDP Act 2023.
      </div>

      {/* Recent resets */}
      {successLog.length > 0 && (
        <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded-xl">
          <p className="text-xs font-semibold text-green-700 dark:text-green-300 mb-1.5">Recent Resets</p>
          <ul className="space-y-0.5">
            {successLog.map((entry, i) => (
              <li key={i} className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1.5">
                <svg className="w-3 h-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                {entry}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Module grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {MODULES.map(mod => (
          <ModuleCard key={mod.module} mod={mod} onReset={handleResetRequest} />
        ))}
      </div>

      {/* Modal */}
      {modalState && (
        <PrivacyResetModal
          targetLabel={modalState.targetLabel}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </div>
  );
}
