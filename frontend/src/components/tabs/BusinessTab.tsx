'use client';

import { useState, useMemo } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GSTStatus {
  gstin: string;
  gstr1Filed: boolean;
  gstr3bFiled: boolean;
  gstr1DueDate: string;
  gstr3bDueDate: string;
  pendingTax: number;
  pendingInterest: number;
}

interface AREntry { name: string; amount: number; daysOverdue: number; }
interface APEntry { name: string; amount: number; daysToDue: number; }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function inr(n: number): string {
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000)    return `₹${(n / 1_00_000).toFixed(2)} L`;
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
      ok ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
         : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
      {label}
    </span>
  );
}

function MetricCard({ label, value, sub, color = 'brand' }: {
  label: string; value: string; sub?: string; color?: string;
}) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
      <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold text-${color}-600 dark:text-${color}-400`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-sections
// ---------------------------------------------------------------------------

function GSTComplianceWidget({ gst }: { gst: GSTStatus }) {
  const allGood = gst.gstr1Filed && gst.gstr3bFiled && gst.pendingTax === 0;

  return (
    <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100">GST Compliance</h3>
        <StatusPill ok={allGood} label={allGood ? 'Compliant' : 'Action Required'} />
      </div>

      <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">GSTIN: {gst.gstin}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className={`p-3 rounded-lg ${gst.gstr1Filed ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'}`}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">GSTR-1</span>
            <StatusPill ok={gst.gstr1Filed} label={gst.gstr1Filed ? 'Filed' : 'Pending'} />
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Due: {gst.gstr1DueDate}</p>
        </div>

        <div className={`p-3 rounded-lg ${gst.gstr3bFiled ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'}`}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700 dark:text-slate-200">GSTR-3B</span>
            <StatusPill ok={gst.gstr3bFiled} label={gst.gstr3bFiled ? 'Filed' : 'Pending'} />
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Due: {gst.gstr3bDueDate}</p>
        </div>
      </div>

      {(gst.pendingTax > 0 || gst.pendingInterest > 0) && (
        <div className="mt-3 p-3 bg-orange-50 dark:bg-orange-900/20 rounded-lg">
          <p className="text-sm font-medium text-orange-800 dark:text-orange-200">
            Tax Due: {inr(gst.pendingTax)}
            {gst.pendingInterest > 0 && ` + Interest: ${inr(gst.pendingInterest)}`}
          </p>
          <p className="text-xs text-orange-600 dark:text-orange-400 mt-0.5">
            Pay via PMT-06 challan before due date to avoid further interest u/s 50.
          </p>
        </div>
      )}
    </section>
  );
}

function CashFlowSection({ ar, ap }: { ar: AREntry[]; ap: APEntry[] }) {
  const totalAR = ar.reduce((s, r) => s + r.amount, 0);
  const totalAP = ap.reduce((s, r) => s + r.amount, 0);
  const overdueAR = ar.filter(r => r.daysOverdue > 0).reduce((s, r) => s + r.amount, 0);

  return (
    <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Cash Flow Position</h3>

      <div className="grid grid-cols-3 gap-3 mb-4 text-center">
        <div className="p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
          <p className="text-xs text-slate-500 dark:text-slate-400">Receivable</p>
          <p className="text-lg font-bold text-green-600 dark:text-green-400">{inr(totalAR)}</p>
        </div>
        <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
          <p className="text-xs text-slate-500 dark:text-slate-400">Payable</p>
          <p className="text-lg font-bold text-red-600 dark:text-red-400">{inr(totalAP)}</p>
        </div>
        <div className={`p-3 rounded-lg ${totalAR - totalAP >= 0 ? 'bg-blue-50 dark:bg-blue-900/20' : 'bg-orange-50 dark:bg-orange-900/20'}`}>
          <p className="text-xs text-slate-500 dark:text-slate-400">Net</p>
          <p className={`text-lg font-bold ${totalAR - totalAP >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-orange-600 dark:text-orange-400'}`}>{inr(totalAR - totalAP)}</p>
        </div>
      </div>

      {overdueAR > 0 && (
        <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg mb-3">
          <p className="text-sm text-red-700 dark:text-red-300">
            Overdue Receivables: <strong>{inr(overdueAR)}</strong> — follow up immediately.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">Top Debtors</p>
          <div className="space-y-1.5">
            {ar.slice(0, 4).map(r => (
              <div key={r.name} className="flex items-center justify-between text-sm">
                <span className="text-slate-700 dark:text-slate-200 truncate max-w-[120px]">{r.name}</span>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-800 dark:text-slate-100">{inr(r.amount)}</span>
                  {r.daysOverdue > 0 && (
                    <span className="text-xs text-red-500">{r.daysOverdue}d</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">Upcoming Payments</p>
          <div className="space-y-1.5">
            {ap.slice(0, 4).map(r => (
              <div key={r.name} className="flex items-center justify-between text-sm">
                <span className="text-slate-700 dark:text-slate-200 truncate max-w-[120px]">{r.name}</span>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-800 dark:text-slate-100">{inr(r.amount)}</span>
                  <span className={`text-xs ${r.daysToDue <= 3 ? 'text-red-500' : 'text-slate-400'}`}>
                    {r.daysToDue}d
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function StatutoryCalendar() {
  const items = [
    { label: 'GSTR-1 (monthly)',     due: '11th of next month',   type: 'GST',    urgent: false },
    { label: 'GSTR-3B',              due: '20th / 22nd of next month', type: 'GST', urgent: false },
    { label: 'TDS Challan 281',      due: '7th of next month',    type: 'TDS',    urgent: true  },
    { label: 'EPF Deposit',          due: '15th of next month',   type: 'PF',     urgent: true  },
    { label: 'ESIC Deposit',         due: '15th of next month',   type: 'ESIC',   urgent: true  },
    { label: 'Advance Tax Q4',       due: '15 Mar 2025',          type: 'IT',     urgent: false },
    { label: 'ITR Filing (business)',due: '31 Jul 2025',          type: 'IT',     urgent: false },
    { label: 'GSTR-9 Annual Return', due: '31 Dec 2025',          type: 'GST',    urgent: false },
  ];

  const typeColors: Record<string, string> = {
    GST:  'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
    TDS:  'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
    PF:   'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300',
    ESIC: 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300',
    IT:   'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
  };

  return (
    <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
      <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Statutory Compliance Calendar</h3>
      <div className="space-y-2">
        {items.map(item => (
          <div key={item.label} className={`flex items-center justify-between p-3 rounded-lg ${item.urgent ? 'bg-orange-50 dark:bg-orange-900/20' : 'bg-slate-50 dark:bg-slate-700/50'}`}>
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${typeColors[item.type]}`}>{item.type}</span>
              <span className="text-sm text-slate-700 dark:text-slate-200">{item.label}</span>
            </div>
            <span className={`text-xs font-medium ${item.urgent ? 'text-orange-700 dark:text-orange-300' : 'text-slate-500 dark:text-slate-400'}`}>{item.due}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const DEMO_GST: GSTStatus = {
  gstin:           '27AABCU9603R1ZX',
  gstr1Filed:      true,
  gstr3bFiled:     false,
  gstr1DueDate:    '11 Mar 2025',
  gstr3bDueDate:   '20 Mar 2025',
  pendingTax:      18_500,
  pendingInterest: 0,
};

const DEMO_AR: AREntry[] = [
  { name: 'Mahesh Traders',      amount: 1_25_000, daysOverdue: 35 },
  { name: 'Ravi Enterprises',    amount: 88_000,   daysOverdue: 0  },
  { name: 'Lakshmi Stores',      amount: 62_500,   daysOverdue: 12 },
  { name: 'Anand & Co',          amount: 45_000,   daysOverdue: 0  },
];

const DEMO_AP: APEntry[] = [
  { name: 'Wholesale Supplies',  amount: 95_000,   daysToDue: 3  },
  { name: 'Packing Materials',   amount: 28_000,   daysToDue: 7  },
  { name: 'Rent',                amount: 35_000,   daysToDue: 10 },
  { name: 'Utilities',           amount: 12_000,   daysToDue: 15 },
];

export default function BusinessTab() {
  const [revenue, setRevenue]     = useState(0);
  const [cogs, setCogs]           = useState(0);
  const [opex, setOpex]           = useState(0);

  const grossProfit   = revenue - cogs;
  const netProfit     = grossProfit - opex;
  const grossMargin   = revenue > 0 ? (grossProfit / revenue * 100) : 0;
  const netMargin     = revenue > 0 ? (netProfit / revenue * 100) : 0;

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Business Dashboard</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          GST compliance, cash flow, payroll, and statutory calendar — India SME
        </p>
      </div>

      {/* Quick P&L */}
      <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Quick P&L Estimator</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
          {[
            { label: 'Revenue', value: revenue, set: setRevenue },
            { label: 'Cost of Goods', value: cogs, set: setCogs },
            { label: 'Operating Expenses', value: opex, set: setOpex },
          ].map(f => (
            <div key={f.label}>
              <label className="text-xs font-medium text-slate-600 dark:text-slate-400">{f.label}</label>
              <div className="relative mt-1">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">₹</span>
                <input
                  type="number"
                  min={0}
                  value={f.value || ''}
                  onChange={e => f.set(Math.max(0, Number(e.target.value)))}
                  className="w-full pl-7 pr-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                             bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100
                             text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="0"
                />
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <MetricCard label="Gross Profit"    value={inr(grossProfit)} sub={`${grossMargin.toFixed(1)}% margin`} color={grossProfit >= 0 ? 'green' : 'red'} />
          <MetricCard label="Net Profit"      value={inr(netProfit)}   sub={`${netMargin.toFixed(1)}% margin`}   color={netProfit >= 0 ? 'brand' : 'red'} />
          <MetricCard label="Est. GST (18%)"  value={inr(revenue * 0.18)} sub="on revenue"   color="blue" />
          <MetricCard label="Est. Tax (30%)"  value={inr(Math.max(0, netProfit) * 0.30)} sub="on net profit" color="purple" />
        </div>
      </section>

      {/* GST compliance widget */}
      <GSTComplianceWidget gst={DEMO_GST} />

      {/* Cash flow */}
      <CashFlowSection ar={DEMO_AR} ap={DEMO_AP} />

      {/* Payroll summary */}
      <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Payroll Compliance (Mar 2025)</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { label: 'TDS to Deposit',  value: '₹28,400',  due: '7 Apr 2025',  code: 'Challan 281' },
            { label: 'EPF to Deposit',  value: '₹42,000',  due: '15 Apr 2025', code: 'EPFO Portal' },
            { label: 'ESIC to Deposit', value: '₹8,750',   due: '15 Apr 2025', code: 'ESIC Portal' },
          ].map(d => (
            <div key={d.label} className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
              <p className="text-xs text-slate-500 dark:text-slate-400">{d.label}</p>
              <p className="text-lg font-bold text-slate-900 dark:text-slate-100">{d.value}</p>
              <p className="text-xs text-slate-400 dark:text-slate-500">{d.code} · {d.due}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Statutory calendar */}
      <StatutoryCalendar />
    </div>
  );
}
