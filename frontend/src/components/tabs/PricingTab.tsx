'use client';

import { useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BillingCycle = 'monthly' | 'annual';

interface Plan {
  id:          string;
  name:        string;
  icon:        string;
  monthlyInr:  number;
  annualInr:   number;   // per-month equivalent on annual plan
  targetRole:  string;
  tagline:     string;
  /** ROI framing: what penalty / loss this plan helps avoid */
  roiHeadline: string;
  roiDetails:  string[];
  features:    { label: string; included: boolean }[];
  cta:         string;
  highlight:   boolean;
}

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const PLANS: Plan[] = [
  {
    id:         'free',
    name:       'Free',
    icon:       '🆓',
    monthlyInr: 0,
    annualInr:  0,
    targetRole: 'Individuals exploring the app',
    tagline:    'Try before you commit — no credit card needed.',
    roiHeadline: 'Avoid the cost of bad financial decisions',
    roiDetails: [
      'Access to AI Chat (10 queries/day)',
      'Budget planner + US Tax bracket estimator',
      'Missing a ₹1L deduction costs more than any plan',
    ],
    features: [
      { label: 'AI Chat (10/day)',       included: true  },
      { label: 'Budget planner',         included: true  },
      { label: 'US Tax calculator',      included: true  },
      { label: 'India Tax dashboard',    included: false },
      { label: 'GST filing assistant',   included: false },
      { label: 'WhatsApp alerts',        included: false },
      { label: 'CA client management',   included: false },
    ],
    cta:       'Start for free',
    highlight: false,
  },
  {
    id:         'individual',
    name:       'Individual',
    icon:       '👤',
    monthlyInr: 499,
    annualInr:  399,
    targetRole: 'Salaried professionals & investors',
    tagline:    'One missed 80C deduction costs ₹15,000+ in extra tax.',
    roiHeadline: '₹499/mo → avoid ₹15,000+ in missed deductions',
    roiDetails: [
      'Sec 80C optimizer: recover ₹46,800 in tax (30% bracket)',
      'HRA, 80D, NPS deduction guidance',
      'Capital gains planner: LTCG ₹1.25L exemption',
      'Advance tax reminders: avoid 234B/234C interest',
      '1 month subscription = 1 missed deduction recovered',
    ],
    features: [
      { label: 'AI Chat (100/day)',       included: true  },
      { label: 'Budget + Investment',     included: true  },
      { label: 'India Tax dashboard',     included: true  },
      { label: 'Deduction optimizer',     included: true  },
      { label: 'WhatsApp bot',            included: true  },
      { label: 'GST filing assistant',    included: false },
      { label: 'CA client management',    included: false },
    ],
    cta:       'Start saving on tax',
    highlight: false,
  },
  {
    id:         'business',
    name:       'Business',
    icon:       '🏪',
    monthlyInr: 1499,
    annualInr:  1199,
    targetRole: 'SME owners, traders & rice mill operators',
    tagline:    'One GSTR-3B late filing = ₹10,000 penalty. One month.',
    roiHeadline: '₹1,499/mo → avoid ₹50,000+ in annual penalties',
    roiDetails: [
      'GSTR-3B late filing penalty: ₹100/day (Sec 47 CGST)',
      'Sec 194C TDS miss: 30% disallowance on payments',
      'Sec 40A(3) cash payment: entire expense disallowed',
      'Advance tax 234B interest: 1%/month on shortfall',
      'Rice Mill Pack: MSP, milling logs, FCI billing, WhatsApp alerts',
    ],
    features: [
      { label: 'AI Chat (500/day)',       included: true  },
      { label: 'GST filing assistant',    included: true  },
      { label: 'Payroll (PF+ESI+TDS)',    included: true  },
      { label: 'P&L + Balance Sheet',     included: true  },
      { label: 'Rice Mill Control Center',included: true  },
      { label: 'Inventory management',    included: true  },
      { label: 'CA client management',    included: false },
    ],
    cta:       'Stop paying penalties',
    highlight: true,
  },
  {
    id:         'ca',
    name:       'CA Professional',
    icon:       '⚖️',
    monthlyInr: 3999,
    annualInr:  3199,
    targetRole: 'Chartered Accountants managing multiple clients',
    tagline:    'One client penalty notice avoided pays for 3 months.',
    roiHeadline: '₹3,999/mo → protect ₹2L+ in client billings',
    roiDetails: [
      'Anomaly detection catches unreported income before IT scrutiny',
      'GSTR-1 vs 3B mismatch alerts prevent ₹1L+ reconciliation costs',
      'Notice response templates (Sec 143/148/271) save 5+ hours/notice',
      'Bulk ITR generation: 10 returns in time of 2',
      'Client health scores → upsell opportunities for retainers',
    ],
    features: [
      { label: 'Unlimited AI Chat',          included: true },
      { label: 'CA Client Mgmt (100+)',       included: true },
      { label: 'Bulk ITR generation',         included: true },
      { label: 'Notice templates',            included: true },
      { label: 'Anomaly detection',           included: true },
      { label: 'Document vault (encrypted)',  included: true },
      { label: 'REST API access',             included: true },
    ],
    cta:       'Grow your practice',
    highlight: false,
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function inr(n: number) {
  return `₹${n.toLocaleString('en-IN')}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PricingTab() {
  const [billing, setBilling] = useState<BillingCycle>('monthly');

  return (
    <div className="space-y-8 pb-8">
      {/* Header */}
      <div className="text-center">
        <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Pricing Plans</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
          Every plan is priced below the cost of a single avoided penalty or missed deduction.
        </p>

        {/* Billing toggle */}
        <div className="inline-flex items-center gap-1 mt-4 bg-slate-100 dark:bg-slate-800 rounded-lg p-1">
          {(['monthly', 'annual'] as BillingCycle[]).map(cycle => (
            <button
              key={cycle}
              onClick={() => setBilling(cycle)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors capitalize ${
                billing === cycle
                  ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 shadow-sm'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
              }`}
            >
              {cycle}
              {cycle === 'annual' && (
                <span className="ml-1.5 px-1.5 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-[10px] font-semibold rounded">
                  Save ~20%
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Plan grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {PLANS.map(plan => {
          const price = billing === 'annual' ? plan.annualInr : plan.monthlyInr;

          return (
            <div
              key={plan.id}
              className={`relative flex flex-col rounded-2xl border p-5 ${
                plan.highlight
                  ? 'border-brand-500 dark:border-brand-400 bg-brand-50 dark:bg-brand-900/10 shadow-lg shadow-brand-100/50'
                  : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800'
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="px-3 py-1 bg-brand-600 text-white text-xs font-semibold rounded-full shadow">
                    Most popular
                  </span>
                </div>
              )}

              {/* Plan header */}
              <div className="mb-4">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-2xl">{plan.icon}</span>
                  <p className="font-bold text-slate-900 dark:text-slate-100">{plan.name}</p>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">{plan.targetRole}</p>
              </div>

              {/* Price */}
              <div className="mb-4">
                {price === 0 ? (
                  <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">Free</p>
                ) : (
                  <>
                    <p className="text-3xl font-bold text-slate-900 dark:text-slate-100">
                      {inr(price)}
                      <span className="text-base font-normal text-slate-400">/mo</span>
                    </p>
                    {billing === 'annual' && (
                      <p className="text-xs text-green-600 dark:text-green-400 mt-0.5">
                        Billed {inr(price * 12)}/yr
                      </p>
                    )}
                  </>
                )}
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 italic leading-relaxed">
                  {plan.tagline}
                </p>
              </div>

              {/* ROI framing */}
              <div className="mb-4 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-xl">
                <p className="text-xs font-semibold text-amber-800 dark:text-amber-200 mb-1.5">
                  {plan.roiHeadline}
                </p>
                <ul className="space-y-1">
                  {plan.roiDetails.map((d, i) => (
                    <li key={i} className="text-[11px] text-amber-700 dark:text-amber-300 flex items-start gap-1.5">
                      <span className="mt-0.5 shrink-0">•</span>
                      {d}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Features */}
              <ul className="space-y-1.5 mb-5 flex-1">
                {plan.features.map(f => (
                  <li key={f.label} className={`flex items-center gap-2 text-sm ${
                    f.included ? 'text-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-500'
                  }`}>
                    {f.included ? (
                      <svg className="w-3.5 h-3.5 text-green-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    )}
                    {f.label}
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <button
                className={`w-full py-2.5 rounded-xl text-sm font-semibold transition-colors ${
                  plan.highlight
                    ? 'bg-brand-600 hover:bg-brand-700 text-white'
                    : plan.monthlyInr === 0
                      ? 'bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-100'
                      : 'bg-slate-900 dark:bg-white hover:bg-slate-700 dark:hover:bg-slate-100 text-white dark:text-slate-900'
                }`}
              >
                {plan.cta}
              </button>
            </div>
          );
        })}
      </div>

      {/* Legal note */}
      <p className="text-xs text-center text-slate-400 dark:text-slate-500">
        Penalty figures cited are from Indian tax law (CGST Act, Income Tax Act 1961) for illustrative ROI purposes only.
        Actual penalties depend on individual circumstances. Consult a qualified CA for specific advice.
        Payments via Razorpay · Annual billing saves ~20%.
      </p>
    </div>
  );
}
