'use client';

import { useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ClientRow {
  id: string;
  name: string;
  type: string;
  pan: string;
  pendingTasks: number;
  overdueTasks: number;
  nextDue: string;
  nextTask: string;
  annualFee: number;
  status: 'green' | 'amber' | 'red';
}

interface UrgentItem {
  clientName: string;
  task: string;
  dueDate: string;
  daysRemaining: number;
  type: string;
}

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const SAMPLE_CLIENTS: ClientRow[] = [
  { id: 'C001', name: 'Mahesh Reddy',        type: 'Individual', pan: 'ABCMR1234F', pendingTasks: 2, overdueTasks: 0, nextDue: '31 Jul 2025', nextTask: 'ITR Filing',   annualFee: 15000, status: 'green' },
  { id: 'C002', name: 'Lakshmi Enterprises', type: 'Proprietor', pan: 'BCDLK5678G', pendingTasks: 3, overdueTasks: 1, nextDue: '20 Mar 2025', nextTask: 'GSTR-3B',      annualFee: 48000, status: 'red'   },
  { id: 'C003', name: 'Sai Tech Pvt Ltd',    type: 'Pvt Ltd',    pan: 'CDEST9012H', pendingTasks: 4, overdueTasks: 0, nextDue: '15 Jun 2025', nextTask: 'Adv Tax Q1',   annualFee: 85000, status: 'green' },
  { id: 'C004', name: 'Anand & Co LLP',      type: 'LLP',        pan: 'DEEAN3456I', pendingTasks: 2, overdueTasks: 1, nextDue: '11 Mar 2025', nextTask: 'GSTR-1',       annualFee: 36000, status: 'amber' },
  { id: 'C005', name: 'Priya Investments',   type: 'Individual', pan: 'EFPRI7890J', pendingTasks: 1, overdueTasks: 0, nextDue: '31 Jul 2025', nextTask: 'ITR (CG)',      annualFee: 8000,  status: 'green' },
];

const URGENT_ITEMS: UrgentItem[] = [
  { clientName: 'Lakshmi Enterprises', task: 'GSTR-3B Filing',    dueDate: '20 Mar 2025', daysRemaining: 2,  type: 'GST' },
  { clientName: 'Anand & Co LLP',      task: 'GSTR-1 Filing',     dueDate: '11 Mar 2025', daysRemaining: -1, type: 'GST' },
  { clientName: 'Mahesh Reddy',        task: 'Advance Tax Q4',    dueDate: '15 Mar 2025', daysRemaining: 5,  type: 'IT'  },
  { clientName: 'Sai Tech Pvt Ltd',    task: 'TDS Return Q3',     dueDate: '31 Mar 2025', daysRemaining: 21, type: 'TDS' },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function inr(n: number) {
  return `₹${n.toLocaleString('en-IN')}`;
}

function StatusDot({ status }: { status: 'green' | 'amber' | 'red' }) {
  const colors = { green: 'bg-green-500', amber: 'bg-amber-500', red: 'bg-red-500' };
  return <span className={`w-2.5 h-2.5 rounded-full ${colors[status]}`} />;
}

function TypeBadge({ type, label }: { type: string; label: string }) {
  const colors: Record<string, string> = {
    GST: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
    IT:  'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
    TDS: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
    ROC: 'bg-teal-100 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[type] || 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300'}`}>
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CAPortalTab() {
  const [search, setSearch]         = useState('');
  const [statusFilter, setFilter]   = useState<'all' | 'green' | 'amber' | 'red'>('all');
  const [activeSection, setSection] = useState<'dashboard' | 'clients' | 'billing'>('dashboard');

  const filtered = SAMPLE_CLIENTS.filter(c => {
    const matchSearch = c.name.toLowerCase().includes(search.toLowerCase()) ||
                        c.pan.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === 'all' || c.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const totalOverdue   = SAMPLE_CLIENTS.reduce((s, c) => s + c.overdueTasks, 0);
  const totalPending   = SAMPLE_CLIENTS.reduce((s, c) => s + c.pendingTasks, 0);
  const totalRevenue   = SAMPLE_CLIENTS.reduce((s, c) => s + c.annualFee, 0);

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">CA Professional Portal</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Client management, compliance tracking, and billing
          </p>
        </div>
        <div className="flex gap-2">
          {(['dashboard', 'clients', 'billing'] as const).map(s => (
            <button
              key={s}
              onClick={() => setSection(s)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${
                activeSection === s
                  ? 'bg-brand-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Clients',    value: String(SAMPLE_CLIENTS.length), color: 'blue'   },
          { label: 'Pending Tasks',    value: String(totalPending),          color: 'orange'  },
          { label: 'Overdue',          value: String(totalOverdue),          color: 'red'     },
          { label: 'Annual Revenue',   value: inr(totalRevenue),             color: 'green'   },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
            <p className="text-xs text-slate-500 dark:text-slate-400">{kpi.label}</p>
            <p className={`text-2xl font-bold mt-1 text-${kpi.color}-600 dark:text-${kpi.color}-400`}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Urgent items */}
      {activeSection === 'dashboard' && (
        <>
          <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Urgent — This Week</h3>
            <div className="space-y-2">
              {URGENT_ITEMS.map((item, i) => (
                <div key={i} className={`flex items-center justify-between p-3 rounded-lg ${
                  item.daysRemaining < 0 ? 'bg-red-50 dark:bg-red-900/20' :
                  item.daysRemaining <= 3 ? 'bg-orange-50 dark:bg-orange-900/20' :
                  'bg-slate-50 dark:bg-slate-700/50'
                }`}>
                  <div className="flex items-center gap-3">
                    <TypeBadge type={item.type} label={item.type} />
                    <div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{item.task}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{item.clientName}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-slate-500 dark:text-slate-400">{item.dueDate}</p>
                    <p className={`text-xs font-medium ${
                      item.daysRemaining < 0 ? 'text-red-600 dark:text-red-400' :
                      item.daysRemaining <= 3 ? 'text-orange-600 dark:text-orange-400' :
                      'text-slate-500 dark:text-slate-400'
                    }`}>
                      {item.daysRemaining < 0 ? `${Math.abs(item.daysRemaining)}d overdue` : `${item.daysRemaining}d left`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ITR readiness */}
          <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">
              ITR Filing Readiness — AY 2025-26
            </h3>
            <div className="grid grid-cols-3 gap-3 mb-4 text-center">
              {[
                { label: 'Not Started', count: 2, color: 'slate' },
                { label: 'In Progress', count: 2, color: 'blue'  },
                { label: 'Ready',       count: 1, color: 'green' },
              ].map(s => (
                <div key={s.label} className={`p-3 bg-${s.color}-50 dark:bg-${s.color}-900/20 rounded-lg`}>
                  <p className={`text-2xl font-bold text-${s.color}-600 dark:text-${s.color}-400`}>{s.count}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{s.label}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              ITR filing due: <strong>31 July 2025</strong>. Documents required: Form 16, Form 26AS, AIS, bank statements, capital gains statements.
            </p>
          </section>
        </>
      )}

      {/* Client list */}
      {activeSection === 'clients' && (
        <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
          <div className="flex flex-col sm:flex-row gap-3 mb-4">
            <input
              type="text"
              placeholder="Search by name or PAN..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="flex-1 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                         bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-slate-100
                         focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <select
              value={statusFilter}
              onChange={e => setFilter(e.target.value as typeof statusFilter)}
              className="px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                         bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-slate-100
                         focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="all">All Status</option>
              <option value="green">Green</option>
              <option value="amber">Amber</option>
              <option value="red">Red</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-600">
                  <th className="text-left pb-2">Client</th>
                  <th className="text-left pb-2 hidden sm:table-cell">Type</th>
                  <th className="text-left pb-2 hidden md:table-cell">PAN</th>
                  <th className="text-center pb-2">Tasks</th>
                  <th className="text-left pb-2 hidden lg:table-cell">Next Due</th>
                  <th className="text-right pb-2">Fee</th>
                  <th className="text-center pb-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {filtered.map(client => (
                  <tr key={client.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                    <td className="py-3">
                      <p className="font-medium text-slate-800 dark:text-slate-100">{client.name}</p>
                      <p className="text-xs text-slate-400 dark:text-slate-500">{client.id}</p>
                    </td>
                    <td className="py-3 hidden sm:table-cell text-slate-600 dark:text-slate-400">{client.type}</td>
                    <td className="py-3 hidden md:table-cell font-mono text-xs text-slate-500 dark:text-slate-400">{client.pan}</td>
                    <td className="py-3 text-center">
                      <span className="font-medium text-slate-800 dark:text-slate-100">{client.pendingTasks}</span>
                      {client.overdueTasks > 0 && (
                        <span className="ml-1 text-xs text-red-500">({client.overdueTasks} OD)</span>
                      )}
                    </td>
                    <td className="py-3 hidden lg:table-cell">
                      <p className="text-slate-700 dark:text-slate-200">{client.nextDue}</p>
                      <p className="text-xs text-slate-400 dark:text-slate-500">{client.nextTask}</p>
                    </td>
                    <td className="py-3 text-right font-medium text-slate-800 dark:text-slate-100">{inr(client.annualFee)}</td>
                    <td className="py-3 text-center">
                      <div className="flex justify-center">
                        <StatusDot status={client.status} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Billing summary */}
      {activeSection === 'billing' && (
        <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 space-y-4">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">Billing Summary — FY 2024-25</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              { label: 'Total Billed',     value: '₹2,42,000', color: 'slate' },
              { label: 'Collected',        value: '₹1,98,000', color: 'green' },
              { label: 'Outstanding',      value: '₹44,000',   color: 'orange'},
              { label: 'Collection Rate',  value: '81.8%',      color: 'blue'  },
              { label: 'Overdue >30 days', value: '₹18,000',   color: 'red'   },
              { label: 'Avg / Client',     value: '₹39,600',   color: 'brand' },
            ].map(m => (
              <div key={m.label} className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                <p className="text-xs text-slate-500 dark:text-slate-400">{m.label}</p>
                <p className={`text-lg font-bold text-${m.color}-600 dark:text-${m.color}-400`}>{m.value}</p>
              </div>
            ))}
          </div>

          <div>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">Revenue by Service</p>
            {[
              { svc: 'GST Monthly Filings',       revenue: 90_000 },
              { svc: 'ITR Filing',                revenue: 54_000 },
              { svc: 'Statutory Audit',           revenue: 50_000 },
              { svc: 'Annual Retainer',           revenue: 24_000 },
              { svc: 'Notice Response',           revenue: 20_000 },
              { svc: 'Bookkeeping',               revenue: 4_000  },
            ].map(r => (
              <div key={r.svc} className="flex items-center gap-3 mb-1.5">
                <span className="text-xs text-slate-600 dark:text-slate-400 w-44 truncate">{r.svc}</span>
                <div className="flex-1 bg-slate-100 dark:bg-slate-700 rounded-full h-2">
                  <div
                    className="bg-brand-500 h-2 rounded-full"
                    style={{ width: `${(r.revenue / 90_000 * 100).toFixed(0)}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-200 w-20 text-right">{inr(r.revenue)}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
