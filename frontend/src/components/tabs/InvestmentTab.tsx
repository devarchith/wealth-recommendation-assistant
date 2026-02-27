'use client';

import { useState } from 'react';
import clsx from 'clsx';

// ── Risk profile types ────────────────────────────────────────────────────

type RiskProfile = 'conservative' | 'moderate' | 'aggressive';
type TimeHorizon = '1-3' | '3-7' | '7-15' | '15+';

interface AllocationSlice {
  label: string;
  pct: number;
  color: string;
  examples: string[];
}

interface Recommendation {
  title: string;
  description: string;
  icon: string;
  tag: string;
  tagColor: string;
}

// ── Allocation presets per risk profile (paper §4.2) ─────────────────────

const ALLOCATIONS: Record<RiskProfile, AllocationSlice[]> = {
  conservative: [
    { label: 'US Bonds',            pct: 50, color: 'bg-blue-500',    examples: ['BND', 'AGG', 'VGIT'] },
    { label: 'US Equities',         pct: 25, color: 'bg-emerald-500', examples: ['VTI', 'FSKAX'] },
    { label: 'International Bonds', pct: 15, color: 'bg-sky-400',     examples: ['BNDX', 'IAGG'] },
    { label: 'Cash / Money Market', pct: 10, color: 'bg-slate-400',   examples: ['VMFXX', 'SPAXX'] },
  ],
  moderate: [
    { label: 'US Equities',         pct: 50, color: 'bg-emerald-500', examples: ['VTI', 'FSKAX', 'VTSAX'] },
    { label: 'International',       pct: 20, color: 'bg-teal-500',    examples: ['VXUS', 'IXUS'] },
    { label: 'US Bonds',            pct: 20, color: 'bg-blue-500',    examples: ['BND', 'AGG'] },
    { label: 'REITs',               pct: 10, color: 'bg-orange-500',  examples: ['VNQ', 'SCHH'] },
  ],
  aggressive: [
    { label: 'US Equities',         pct: 55, color: 'bg-emerald-500', examples: ['VTI', 'QQQ', 'VOO'] },
    { label: 'International',       pct: 25, color: 'bg-teal-500',    examples: ['VXUS', 'EEM'] },
    { label: 'Small-Cap Value',     pct: 10, color: 'bg-purple-500',  examples: ['VBR', 'VIOV'] },
    { label: 'Alternatives',        pct: 10, color: 'bg-rose-500',    examples: ['VNQ', 'PDBC'] },
  ],
};

const RECOMMENDATIONS: Record<RiskProfile, Recommendation[]> = {
  conservative: [
    { title: 'Three-Fund Portfolio (Conservative)', description: 'Total US market (25%), total international (15%), US bonds (50%). Low cost, tax-efficient, minimal volatility.', icon: '🛡️', tag: 'Low Risk', tagColor: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
    { title: 'High-Yield Savings Account (HYSA)', description: 'Keep 6–12 months of expenses in a HYSA earning 4–5% APY. Provides liquidity without market exposure.', icon: '🏦', tag: 'Capital Preservation', tagColor: 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300' },
    { title: 'I-Bonds (Inflation Protection)', description: 'Treasury I-Bonds adjust for inflation. $10K annual limit per person. Ideal for conservative long-term savings.', icon: '🇺🇸', tag: 'Inflation-Protected', tagColor: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' },
  ],
  moderate: [
    { title: 'Three-Fund Portfolio (Balanced)', description: 'VTI (50%) + VXUS (20%) + BND (20%) + VNQ (10%). Covers total market, international, bonds, and real estate.', icon: '⚖️', tag: 'Balanced', tagColor: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300' },
    { title: 'Max 401(k) + Roth IRA', description: 'Contribute $23,000 to 401(k) and $7,000 to Roth IRA annually. Tax-diversified retirement stack aligned with moderate risk.', icon: '🏛️', tag: 'Tax-Advantaged', tagColor: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300' },
    { title: 'Dollar-Cost Averaging', description: 'Invest a fixed amount monthly regardless of market conditions. Reduces timing risk and leverages compounding over time.', icon: '📅', tag: 'Systematic', tagColor: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' },
  ],
  aggressive: [
    { title: 'Growth-Tilted Portfolio', description: 'VTI (55%) + VXUS (25%) + VBR small-cap value (10%) + alternatives (10%). Historically higher returns with higher volatility.', icon: '🚀', tag: 'High Growth', tagColor: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300' },
    { title: 'Factor Investing (Small-Cap Value)', description: 'Academic research shows small-cap value stocks outperform the market by 1–3% annually over 20+ year periods (Fama-French factors).', icon: '📊', tag: 'Factor-Based', tagColor: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300' },
    { title: 'Tax-Loss Harvesting', description: 'Sell losing positions to offset capital gains. Reinvest in similar (not identical) ETFs within 30 days. Saves 15–20% on gains.', icon: '💡', tag: 'Tax Alpha', tagColor: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300' },
  ],
};

const PROFILE_META: Record<RiskProfile, { label: string; desc: string; icon: string; color: string }> = {
  conservative: { label: 'Conservative',  desc: 'Capital preservation, minimal volatility, stable income',       icon: '🛡️', color: 'border-blue-400 dark:border-blue-500' },
  moderate:     { label: 'Moderate',      desc: 'Balanced growth and stability, diversified across asset classes', icon: '⚖️', color: 'border-yellow-400 dark:border-yellow-500' },
  aggressive:   { label: 'Aggressive',    desc: 'Maximum long-term growth, high volatility tolerance',             icon: '🚀', color: 'border-rose-400 dark:border-rose-500' },
};

// ── Allocation donut (CSS-only) ───────────────────────────────────────────

function AllocationBar({ slices }: { slices: AllocationSlice[] }) {
  return (
    <div className="w-full h-4 rounded-full overflow-hidden flex gap-0.5">
      {slices.map(s => (
        <div
          key={s.label}
          className={clsx(s.color, 'h-full transition-all duration-500')}
          style={{ width: `${s.pct}%` }}
          title={`${s.label}: ${s.pct}%`}
        />
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export default function InvestmentTab() {
  const [profile, setProfile] = useState<RiskProfile>('moderate');
  const [horizon, setHorizon] = useState<TimeHorizon>('7-15');
  const [age, setAge] = useState(30);

  const slices = ALLOCATIONS[profile];
  const recs = RECOMMENDATIONS[profile];

  // Suggested equity allocation rule: 110 - age (adjusted for horizon)
  const suggestedEquity = Math.min(100, 110 - age + (horizon === '15+' ? 5 : horizon === '7-15' ? 0 : -5));

  return (
    <div className="space-y-6 animate-fade-in">

      {/* ── Risk profile selector (paper §4.2) ───────────────────────── */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 p-4 space-y-4">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100">Risk Profile</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {(Object.keys(PROFILE_META) as RiskProfile[]).map(p => {
            const meta = PROFILE_META[p];
            const selected = profile === p;
            return (
              <button
                key={p}
                onClick={() => setProfile(p)}
                className={clsx(
                  'rounded-xl border-2 p-3 text-left transition-all',
                  selected
                    ? `${meta.color} bg-slate-50 dark:bg-slate-700/60 shadow-sm`
                    : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xl">{meta.icon}</span>
                  <span className={clsx('text-sm font-semibold', selected ? 'text-slate-900 dark:text-white' : 'text-slate-700 dark:text-slate-300')}>
                    {meta.label}
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">{meta.desc}</p>
              </button>
            );
          })}
        </div>

        {/* Inputs */}
        <div className="grid grid-cols-2 gap-4 pt-1">
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Your Age</label>
            <div className="flex items-center gap-2">
              <input
                type="range" min={18} max={80} value={age}
                onChange={e => setAge(Number(e.target.value))}
                className="flex-1 accent-brand-600"
              />
              <span className="text-sm font-semibold text-slate-700 dark:text-slate-200 w-6">{age}</span>
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Time Horizon (years)</label>
            <select
              value={horizon}
              onChange={e => setHorizon(e.target.value as TimeHorizon)}
              className="w-full text-sm bg-slate-50 dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-1.5 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="1-3">1–3 years</option>
              <option value="3-7">3–7 years</option>
              <option value="7-15">7–15 years</option>
              <option value="15+">15+ years</option>
            </select>
          </div>
        </div>

        {/* Suggested equity % pill */}
        <div className="flex items-center gap-2 text-sm bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-300 rounded-lg px-3 py-2">
          <span>💡</span>
          <span>Suggested equity allocation: <b>{suggestedEquity}%</b> (110 − age ± horizon adjustment)</span>
        </div>
      </div>

      {/* ── Portfolio allocation ──────────────────────────────────────── */}
      <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 p-4 space-y-4">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100">Recommended Allocation</h3>
        <AllocationBar slices={slices} />
        <div className="grid grid-cols-2 gap-2">
          {slices.map(s => (
            <div key={s.label} className="flex items-center gap-2">
              <div className={clsx('w-3 h-3 rounded-full flex-shrink-0', s.color)} />
              <div className="min-w-0">
                <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{s.label}</p>
                <p className="text-xs text-slate-400 dark:text-slate-500">{s.pct}% — {s.examples.join(', ')}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Personalized recommendations ─────────────────────────────── */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Personalized Recommendations</h3>
        {recs.map(rec => (
          <div key={rec.title} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 p-4 flex gap-3 animate-slide-up">
            <span className="text-2xl flex-shrink-0 mt-0.5">{rec.icon}</span>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{rec.title}</span>
                <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', rec.tagColor)}>{rec.tag}</span>
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-400">{rec.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
