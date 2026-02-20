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
  healthScore: number;        // 0–100 from anomaly detector
  anomalyCount: number;
  criticalAnomalies: number;
  itrProgress: number;        // 0–100 doc readiness %
  gstCompliance: 'ok' | 'pending' | 'overdue';
}

interface UrgentItem {
  clientName: string;
  task: string;
  dueDate: string;
  daysRemaining: number;
  type: string;
}

interface AnomalyFlag {
  ruleId: string;
  clientName: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  description: string;
  recommendation: string;
}

// ---------------------------------------------------------------------------
// Sample data (enriched with health scores)
// ---------------------------------------------------------------------------

const SAMPLE_CLIENTS: ClientRow[] = [
  { id: 'C001', name: 'Mahesh Reddy',        type: 'Individual', pan: 'ABCMR1234F', pendingTasks: 2, overdueTasks: 0, nextDue: '31 Jul 2025', nextTask: 'ITR Filing',   annualFee: 15000, status: 'green', healthScore: 92, anomalyCount: 1, criticalAnomalies: 0, itrProgress: 75, gstCompliance: 'ok'      },
  { id: 'C002', name: 'Lakshmi Enterprises', type: 'Proprietor', pan: 'BCDLK5678G', pendingTasks: 3, overdueTasks: 1, nextDue: '20 Mar 2025', nextTask: 'GSTR-3B',      annualFee: 48000, status: 'red',   healthScore: 41, anomalyCount: 5, criticalAnomalies: 2, itrProgress: 30, gstCompliance: 'overdue' },
  { id: 'C003', name: 'Sai Tech Pvt Ltd',    type: 'Pvt Ltd',    pan: 'CDEST9012H', pendingTasks: 4, overdueTasks: 0, nextDue: '15 Jun 2025', nextTask: 'Adv Tax Q1',   annualFee: 85000, status: 'green', healthScore: 78, anomalyCount: 2, criticalAnomalies: 0, itrProgress: 55, gstCompliance: 'ok'      },
  { id: 'C004', name: 'Anand & Co LLP',      type: 'LLP',        pan: 'DEEAN3456I', pendingTasks: 2, overdueTasks: 1, nextDue: '11 Mar 2025', nextTask: 'GSTR-1',       annualFee: 36000, status: 'amber', healthScore: 63, anomalyCount: 3, criticalAnomalies: 1, itrProgress: 45, gstCompliance: 'overdue' },
  { id: 'C005', name: 'Priya Investments',   type: 'Individual', pan: 'EFPRI7890J', pendingTasks: 1, overdueTasks: 0, nextDue: '31 Jul 2025', nextTask: 'ITR (CG)',      annualFee: 8000,  status: 'green', healthScore: 88, anomalyCount: 1, criticalAnomalies: 0, itrProgress: 85, gstCompliance: 'ok'      },
];

const URGENT_ITEMS: UrgentItem[] = [
  { clientName: 'Lakshmi Enterprises', task: 'GSTR-3B Filing',    dueDate: '20 Mar 2025', daysRemaining: 2,  type: 'GST' },
  { clientName: 'Anand & Co LLP',      task: 'GSTR-1 Filing',     dueDate: '11 Mar 2025', daysRemaining: -1, type: 'GST' },
  { clientName: 'Mahesh Reddy',        task: 'Advance Tax Q4',    dueDate: '15 Mar 2025', daysRemaining: 5,  type: 'IT'  },
  { clientName: 'Sai Tech Pvt Ltd',    task: 'TDS Return Q3',     dueDate: '31 Mar 2025', daysRemaining: 21, type: 'TDS' },
];

const SAMPLE_ANOMALIES: AnomalyFlag[] = [
  { ruleId: 'BNK001', clientName: 'Lakshmi Enterprises', severity: 'critical', description: 'Unexplained bank credits ₹4,80,000',               recommendation: 'Obtain source explanation for each credit. May attract section 69A.'  },
  { ruleId: 'GST001', clientName: 'Lakshmi Enterprises', severity: 'critical', description: 'GSTR-1 vs GSTR-3B mismatch: ₹1,20,000 (12.5%)',     recommendation: 'Reconcile GSTR-1 and GSTR-3B immediately. File amendment if needed.' },
  { ruleId: 'ADV001', clientName: 'Anand & Co LLP',      severity: 'high',     description: 'Advance tax shortfall ₹38,000 — interest u/s 234B/C', recommendation: 'Pay balance advance tax immediately and compute interest.'             },
  { ruleId: 'EXP001', clientName: 'Sai Tech Pvt Ltd',    severity: 'high',     description: 'Cash expenses ₹92,000 may attract disallowance u/s 40A(3)', recommendation: 'Review each cash expense. Disallow excess. Advise digital payments.' },
  { ruleId: 'INC002', clientName: 'Mahesh Reddy',        severity: 'medium',   description: 'Income dropped 38% vs prior year',                   recommendation: 'Check if income under-reported. Verify with AIS/26AS.'               },
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

function SeverityBadge({ severity }: { severity: AnomalyFlag['severity'] }) {
  const map = {
    critical: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
    high:     'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
    medium:   'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300',
    low:      'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${map[severity]}`}>
      {severity}
    </span>
  );
}

function HealthScoreRing({ score }: { score: number }) {
  const color = score >= 80 ? '#22c55e' : score >= 60 ? '#f59e0b' : '#ef4444';
  const r = 20, circ = 2 * Math.PI * r;
  const dash = (score / 100) * circ;
  return (
    <svg width="52" height="52" viewBox="0 0 52 52">
      <circle cx="26" cy="26" r={r} fill="none" stroke="#e2e8f0" strokeWidth="5" />
      <circle
        cx="26" cy="26" r={r} fill="none" stroke={color} strokeWidth="5"
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeLinecap="round"
        transform="rotate(-90 26 26)"
      />
      <text x="26" y="30" textAnchor="middle" fontSize="12" fontWeight="700" fill={color}>
        {score}
      </text>
    </svg>
  );
}

function GSTBadge({ status }: { status: ClientRow['gstCompliance'] }) {
  const map = {
    ok:      'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300',
    pending: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300',
    overdue: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${map[status]}`}>
      GST {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function CAPortalTab() {
  const [search, setSearch]         = useState('');
  const [statusFilter, setFilter]   = useState<'all' | 'green' | 'amber' | 'red'>('all');
  const [activeSection, setSection] = useState<'control-center' | 'clients' | 'billing' | 'anomalies'>('control-center');
  const [expandedAnomaly, setExpandedAnomaly] = useState<string | null>(null);

  const filtered = SAMPLE_CLIENTS.filter(c => {
    const matchSearch = c.name.toLowerCase().includes(search.toLowerCase()) ||
                        c.pan.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === 'all' || c.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const totalOverdue    = SAMPLE_CLIENTS.reduce((s, c) => s + c.overdueTasks, 0);
  const totalPending    = SAMPLE_CLIENTS.reduce((s, c) => s + c.pendingTasks, 0);
  const totalRevenue    = SAMPLE_CLIENTS.reduce((s, c) => s + c.annualFee, 0);
  const avgHealth       = Math.round(SAMPLE_CLIENTS.reduce((s, c) => s + c.healthScore, 0) / SAMPLE_CLIENTS.length);
  const criticalClients = SAMPLE_CLIENTS.filter(c => c.criticalAnomalies > 0).length;

  const SECTIONS = ['control-center', 'clients', 'billing', 'anomalies'] as const;

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">CA Professional Portal</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Control center · Compliance tracking · Anomaly detection · Billing
          </p>
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {SECTIONS.map(s => (
            <button
              key={s}
              onClick={() => setSection(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                activeSection === s
                  ? 'bg-brand-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              {s === 'control-center' ? 'Control Center' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label: 'Clients',          value: String(SAMPLE_CLIENTS.length), color: 'blue'   },
          { label: 'Pending Tasks',    value: String(totalPending),          color: 'orange'  },
          { label: 'Overdue',          value: String(totalOverdue),          color: 'red'     },
          { label: 'Avg Health',       value: `${avgHealth}/100`,            color: avgHealth >= 75 ? 'green' : 'orange' },
          { label: 'Annual Revenue',   value: inr(totalRevenue),             color: 'green'   },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-4">
            <p className="text-xs text-slate-500 dark:text-slate-400">{kpi.label}</p>
            <p className={`text-xl font-bold mt-1 text-${kpi.color}-600 dark:text-${kpi.color}-400`}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* ── Control Center ──────────────────────────────────────────────────── */}
      {activeSection === 'control-center' && (
        <>
          {/* Client Health Scores */}
          <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-slate-800 dark:text-slate-100">Client Health Scores</h3>
              {criticalClients > 0 && (
                <span className="px-2.5 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-xs font-semibold rounded-full">
                  {criticalClients} client{criticalClients > 1 ? 's' : ''} need attention
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[...SAMPLE_CLIENTS].sort((a, b) => a.healthScore - b.healthScore).map(c => (
                <div key={c.id} className={`flex items-center gap-3 p-3 rounded-xl border ${
                  c.criticalAnomalies > 0
                    ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10'
                    : c.healthScore < 70
                      ? 'border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/10'
                      : 'border-slate-100 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/30'
                }`}>
                  <HealthScoreRing score={c.healthScore} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">{c.name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{c.type}</p>
                    <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                      <GSTBadge status={c.gstCompliance} />
                      {c.anomalyCount > 0 && (
                        <span className="text-xs text-slate-500 dark:text-slate-400">
                          {c.anomalyCount} flag{c.anomalyCount > 1 ? 's' : ''}
                          {c.criticalAnomalies > 0 && <span className="text-red-500 ml-1">({c.criticalAnomalies} critical)</span>}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="w-full bg-slate-200 dark:bg-slate-600 rounded-full h-1.5 w-16">
                      <div
                        className="h-1.5 rounded-full"
                        style={{
                          width: `${c.itrProgress}%`,
                          backgroundColor: c.itrProgress >= 75 ? '#22c55e' : c.itrProgress >= 40 ? '#f59e0b' : '#ef4444',
                        }}
                      />
                    </div>
                    <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">ITR {c.itrProgress}%</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Urgent this week */}
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
              ITR filing due: <strong>31 July 2025</strong> (non-audit) · <strong>31 Oct 2025</strong> (audit).
              Documents: Form 16, Form 26AS, AIS, bank statements, capital gains statements.
            </p>
          </section>
        </>
      )}

      {/* ── Clients ─────────────────────────────────────────────────────────── */}
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
                  <th className="text-center pb-2">Health</th>
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
                      <span className={`text-sm font-bold ${
                        client.healthScore >= 80 ? 'text-green-600 dark:text-green-400' :
                        client.healthScore >= 60 ? 'text-amber-600 dark:text-amber-400' :
                        'text-red-600 dark:text-red-400'
                      }`}>{client.healthScore}</span>
                    </td>
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

      {/* ── Billing ─────────────────────────────────────────────────────────── */}
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
              { svc: 'GST Monthly Filings',  revenue: 90_000 },
              { svc: 'ITR Filing',           revenue: 54_000 },
              { svc: 'Statutory Audit',      revenue: 50_000 },
              { svc: 'Annual Retainer',      revenue: 24_000 },
              { svc: 'Notice Response',      revenue: 20_000 },
              { svc: 'Bookkeeping',          revenue: 4_000  },
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

      {/* ── Anomalies ───────────────────────────────────────────────────────── */}
      {activeSection === 'anomalies' && (
        <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">Anomaly Flags — AY 2024-25</h3>
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {SAMPLE_ANOMALIES.filter(a => a.severity === 'critical').length} critical · {' '}
              {SAMPLE_ANOMALIES.filter(a => a.severity === 'high').length} high · {' '}
              {SAMPLE_ANOMALIES.length} total
            </span>
          </div>
          <div className="space-y-2">
            {SAMPLE_ANOMALIES.map(flag => (
              <div
                key={flag.ruleId + flag.clientName}
                className={`rounded-lg border p-3 cursor-pointer transition-colors ${
                  flag.severity === 'critical'
                    ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10'
                    : flag.severity === 'high'
                      ? 'border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-900/10'
                      : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/30'
                }`}
                onClick={() => setExpandedAnomaly(
                  expandedAnomaly === flag.ruleId + flag.clientName ? null : flag.ruleId + flag.clientName
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <SeverityBadge severity={flag.severity} />
                    <span className="text-xs font-mono text-slate-500 dark:text-slate-400">{flag.ruleId}</span>
                    <span className="text-xs text-slate-500 dark:text-slate-400">·</span>
                    <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{flag.clientName}</span>
                  </div>
                  <span className="text-xs text-slate-400 dark:text-slate-500 shrink-0">
                    {expandedAnomaly === flag.ruleId + flag.clientName ? '▲' : '▼'}
                  </span>
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-200 mt-1">{flag.description}</p>
                {expandedAnomaly === flag.ruleId + flag.clientName && (
                  <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-600">
                    <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Recommendation</p>
                    <p className="text-xs text-slate-600 dark:text-slate-300 mt-0.5">{flag.recommendation}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
