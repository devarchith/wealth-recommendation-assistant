'use client';

import { useState } from 'react';

// ---------------------------------------------------------------------------
// Role definitions
// ---------------------------------------------------------------------------

export type UserRole = 'individual' | 'ca' | 'ricemill' | 'business';

interface RoleOption {
  role:        UserRole;
  label:       string;
  subtitle:    string;
  icon:        string;
  accentColor: string;
  features:    string[];
  /** Which tabs to show when this role is active */
  visibleTabs: string[];
  /** First tab to highlight on entry */
  defaultTab:  string;
}

export const ROLE_OPTIONS: RoleOption[] = [
  {
    role:        'individual',
    label:       'Personal Finance',
    subtitle:    'For individuals managing budgets, investments, and taxes',
    icon:        '👤',
    accentColor: 'brand',
    features:    ['AI Chat advisor', 'Budget planner', 'Investment tool', 'US & India Tax'],
    visibleTabs: ['chat', 'budget', 'investment', 'tax', 'india-tax', 'pricing', 'privacy'],
    defaultTab:  'chat',
  },
  {
    role:        'ca',
    label:       'CA Professional',
    subtitle:    'Multi-client dashboard, compliance tracking & anomaly detection',
    icon:        '⚖️',
    accentColor: 'blue',
    features:    ['Client health scores', 'GST & ITR deadlines', 'Anomaly flags', 'Billing tracker'],
    visibleTabs: ['ca', 'chat', 'india-tax', 'pricing', 'privacy'],
    defaultTab:  'ca',
  },
  {
    role:        'ricemill',
    label:       'Rice Mill Owner',
    subtitle:    'Milling operations, penalty alerts, stock & MSP tracking',
    icon:        '🌾',
    accentColor: 'green',
    features:    ['Penalty & GST alerts', 'Stock & inventory', 'Lot milling log', 'MSP reference'],
    visibleTabs: ['ricemill', 'chat', 'business', 'pricing', 'privacy'],
    defaultTab:  'ricemill',
  },
  {
    role:        'business',
    label:       'Business Owner',
    subtitle:    'P&L, GST compliance, payroll and cash flow for SMEs',
    icon:        '🏪',
    accentColor: 'purple',
    features:    ['Quick P&L estimator', 'GST compliance', 'Cash flow tracker', 'Payroll summary'],
    visibleTabs: ['business', 'chat', 'india-tax', 'budget', 'pricing', 'privacy'],
    defaultTab:  'business',
  },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RoleSelectorProps {
  onSelect: (role: UserRole) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RoleSelector({ onSelect }: RoleSelectorProps) {
  const [hovered, setHovered] = useState<UserRole | null>(null);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex flex-col items-center justify-center p-6">
      {/* Logo */}
      <div className="flex items-center gap-2.5 mb-8">
        <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center text-white font-bold text-lg select-none">
          W
        </div>
        <div>
          <p className="font-bold text-slate-900 dark:text-white text-lg leading-tight">WealthAdvisor AI</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Choose your workspace to get started</p>
        </div>
      </div>

      {/* Role grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full max-w-2xl">
        {ROLE_OPTIONS.map(opt => (
          <button
            key={opt.role}
            onClick={() => onSelect(opt.role)}
            onMouseEnter={() => setHovered(opt.role)}
            onMouseLeave={() => setHovered(null)}
            className={`text-left p-5 rounded-2xl border-2 transition-all duration-150 bg-white dark:bg-slate-800 ${
              hovered === opt.role
                ? 'border-brand-500 dark:border-brand-400 shadow-lg shadow-brand-100/50 dark:shadow-none scale-[1.02]'
                : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
            }`}
          >
            {/* Header row */}
            <div className="flex items-start gap-3 mb-3">
              <span className="text-3xl shrink-0">{opt.icon}</span>
              <div>
                <p className="font-semibold text-slate-900 dark:text-slate-100 text-base">{opt.label}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 leading-relaxed">{opt.subtitle}</p>
              </div>
            </div>

            {/* Feature list */}
            <ul className="space-y-1">
              {opt.features.map(f => (
                <li key={f} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>

            {/* CTA */}
            <div className={`mt-4 text-xs font-semibold transition-colors ${
              hovered === opt.role ? 'text-brand-600 dark:text-brand-400' : 'text-slate-400 dark:text-slate-500'
            }`}>
              {hovered === opt.role ? 'Click to enter →' : 'Select workspace'}
            </div>
          </button>
        ))}
      </div>

      {/* Fine print */}
      <p className="mt-8 text-xs text-slate-400 dark:text-slate-500 text-center max-w-md">
        You can switch your workspace at any time from the header. All workspaces are for educational use only — not licensed CA or IA advice.
      </p>
    </div>
  );
}
