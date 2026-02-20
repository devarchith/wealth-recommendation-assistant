'use client';

import { useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MillKPI {
  label:   string;
  value:   string;
  subtext: string;
  color:   'green' | 'orange' | 'red' | 'blue' | 'slate';
  trend?:  'up' | 'down' | 'neutral';
}

interface PenaltyAlert {
  id:       string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  title:    string;
  amount:   number;
  section:  string;
  action:   string;
}

interface StockItem {
  label:   string;
  qtl:     number;
  value:   number;
  color:   string;
}

interface ConversionLot {
  lotId:    string;
  variety:  string;
  paddyQtl: number;
  riceQtl:  number;
  outturn:  number;
  branQtl:  number;
  status:   'completed' | 'milling' | 'pending';
}

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const SAMPLE_KPIS: MillKPI[] = [
  { label: 'Today\'s Milling',  value: '480 qtl',      subtext: 'Paddy processed',    color: 'blue',   trend: 'up'      },
  { label: 'Rice Output',       value: '322 qtl',       subtext: 'Outturn 67.1%',      color: 'green',  trend: 'neutral' },
  { label: 'Cash Runway',       value: '18 days',       subtext: 'At current burn rate',color: 'orange', trend: 'down'    },
  { label: 'FCI Receivable',    value: '₹4.2L',         subtext: '32 days outstanding', color: 'orange', trend: 'neutral' },
  { label: 'Penalty Exposure',  value: '₹38,500',       subtext: '2 critical alerts',   color: 'red',    trend: 'up'      },
  { label: 'Bran Price',        value: '₹380/qtl',      subtext: 'Today\'s rate',       color: 'slate',  trend: 'up'      },
];

const PENALTY_ALERTS: PenaltyAlert[] = [
  { id: 'A1', severity: 'critical', title: 'GSTR-3B overdue 8 days',          amount: 400,    section: 'Sec 47 CGST',    action: 'File GSTR-3B immediately'                   },
  { id: 'A2', severity: 'critical', title: 'Cash payment ₹2.4L to farmer',    amount: 12000,  section: 'Sec 40A(3)',     action: 'Pay via RTGS for future transactions'        },
  { id: 'A3', severity: 'high',     title: 'Advance tax shortfall ₹38,000',   amount: 38000,  section: 'Sec 234B/C',     action: 'Pay Challan 280 before 15 Dec'               },
  { id: 'A4', severity: 'medium',   title: 'TDS 194C: ₹950 deduction missed', amount: 950,    section: 'Sec 194C',       action: 'Deduct from next transport payment'          },
];

const STOCK: StockItem[] = [
  { label: 'Paddy',        qtl: 1820, value: 418600,  color: '#f59e0b' },
  { label: 'Rice (Raw)',   qtl:  640, value: 1408000,  color: '#22c55e' },
  { label: 'Rice Bran',   qtl:  145, value:   55100,  color: '#8b5cf6' },
  { label: 'Husk',        qtl:  360, value:   23400,  color: '#6b7280' },
  { label: 'Broken Rice', qtl:   48, value:   67200,  color: '#f97316' },
];

const LOTS: ConversionLot[] = [
  { lotId: 'LOT042', variety: 'Sona Masoori', paddyQtl: 200, riceQtl: 136, outturn: 68.0, branQtl: 16, status: 'completed' },
  { lotId: 'LOT041', variety: 'Swarna',        paddyQtl: 280, riceQtl: 188, outturn: 67.1, branQtl: 22, status: 'completed' },
  { lotId: 'LOT043', variety: 'MTU-1010',      paddyQtl: 150, riceQtl:  0,  outturn: 0,    branQtl:  0, status: 'milling'   },
  { lotId: 'LOT044', variety: 'Common',         paddyQtl: 320, riceQtl:  0,  outturn: 0,    branQtl:  0, status: 'pending'   },
];

// MSP reference data
const MSP_DATA = {
  paddy_common: 2300,
  paddy_grade_a: 2320,
  prev_year_common: 2183,
  yoy_increase: 117,
  yoy_pct: 5.36,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function inr(n: number) {
  return `₹${n.toLocaleString('en-IN')}`;
}

function SeverityChip({ severity }: { severity: PenaltyAlert['severity'] }) {
  const map = {
    critical: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
    high:     'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300',
    medium:   'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300',
    low:      'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${map[severity]}`}>
      {severity}
    </span>
  );
}

function TrendArrow({ trend }: { trend?: MillKPI['trend'] }) {
  if (!trend || trend === 'neutral') return null;
  return <span className={trend === 'up' ? 'text-green-500' : 'text-red-500'}>{trend === 'up' ? ' ↑' : ' ↓'}</span>;
}

function StatusBadge({ status }: { status: ConversionLot['status'] }) {
  const map = {
    completed: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300',
    milling:   'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
    pending:   'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400',
  };
  return <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${map[status]}`}>{status}</span>;
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const SECTIONS = ['overview', 'penalties', 'stock', 'conversion', 'msp'] as const;
type Section = typeof SECTIONS[number];

export default function RiceMillTab() {
  const [active, setActive] = useState<Section>('overview');
  const [expandedAlert, setExpandedAlert] = useState<string | null>(null);

  const totalStockValue  = STOCK.reduce((s, i) => s + i.value, 0);
  const criticalAlerts   = PENALTY_ALERTS.filter(a => a.severity === 'critical').length;
  const totalPenaltyExp  = PENALTY_ALERTS.reduce((s, a) => s + a.amount, 0);

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Rice Mill Control Center</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Milling operations · GST/TDS compliance · Stock · FCI billing · MSP
          </p>
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {SECTIONS.map(s => (
            <button
              key={s}
              onClick={() => setActive(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                active === s
                  ? 'bg-brand-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              {s === 'msp' ? 'MSP' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {SAMPLE_KPIS.map(kpi => (
          <div key={kpi.label} className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-3">
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{kpi.label}</p>
            <p className={`text-lg font-bold mt-0.5 text-${kpi.color}-600 dark:text-${kpi.color}-400`}>
              {kpi.value}<TrendArrow trend={kpi.trend} />
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 truncate">{kpi.subtext}</p>
          </div>
        ))}
      </div>

      {/* ── Overview ─────────────────────────────────────────────────────── */}
      {active === 'overview' && (
        <>
          {/* Alert bar */}
          {criticalAlerts > 0 && (
            <div className="flex items-center gap-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl">
              <span className="text-xl">🚨</span>
              <div>
                <p className="text-sm font-semibold text-red-800 dark:text-red-200">
                  {criticalAlerts} Critical Alert{criticalAlerts > 1 ? 's' : ''} — Action Required Today
                </p>
                <p className="text-xs text-red-600 dark:text-red-300">
                  Total penalty exposure: {inr(totalPenaltyExp)}. Switch to Penalties tab for details.
                </p>
              </div>
            </div>
          )}

          {/* Today's milling summary */}
          <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Today's Milling Activity</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Paddy In',    value: '480 qtl',  sub: 'Swarna + MTU-1010' },
                { label: 'Rice Out',    value: '322 qtl',  sub: 'Outturn: 67.1%'    },
                { label: 'Bran',        value: '38.4 qtl', sub: '8% recovery'       },
                { label: 'Husk',        value: '96 qtl',   sub: '20% recovery'      },
              ].map(item => (
                <div key={item.label} className="text-center p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                  <p className="text-xs text-slate-500 dark:text-slate-400">{item.label}</p>
                  <p className="text-xl font-bold text-slate-800 dark:text-slate-100 mt-1">{item.value}</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">{item.sub}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Working capital mini */}
          <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-800 dark:text-slate-100">Working Capital Status</h3>
              <span className="px-2 py-1 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 text-xs font-semibold rounded-full">
                Moderate Stress
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { label: 'Current Ratio', value: '1.38',        ok: true  },
                { label: 'Cash Runway',   value: '18 days',     ok: false },
                { label: 'CC Utilised',   value: '74%',         ok: true  },
                { label: 'FCI Dues',      value: '₹4.2L (32d)', ok: false },
                { label: 'Farmer Payable',value: '₹1.8L',       ok: true  },
                { label: 'Stock Value',   value: inr(totalStockValue), ok: true },
              ].map(m => (
                <div key={m.label} className="flex items-center justify-between p-2.5 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                  <span className="text-xs text-slate-500 dark:text-slate-400">{m.label}</span>
                  <span className={`text-sm font-semibold ${m.ok ? 'text-green-600 dark:text-green-400' : 'text-orange-600 dark:text-orange-400'}`}>
                    {m.value}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      {/* ── Penalties ────────────────────────────────────────────────────── */}
      {active === 'penalties' && (
        <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">Penalty & Compliance Alerts</h3>
            <span className="text-sm font-semibold text-red-600 dark:text-red-400">
              Total exposure: {inr(totalPenaltyExp)}
            </span>
          </div>
          <div className="space-y-2">
            {PENALTY_ALERTS.map(alert => (
              <div
                key={alert.id}
                className={`rounded-lg border p-3 cursor-pointer transition-colors ${
                  alert.severity === 'critical'
                    ? 'border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/10'
                    : alert.severity === 'high'
                      ? 'border-orange-200 dark:border-orange-800 bg-orange-50 dark:bg-orange-900/10'
                      : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/30'
                }`}
                onClick={() => setExpandedAlert(expandedAlert === alert.id ? null : alert.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-wrap">
                    <SeverityChip severity={alert.severity} />
                    <span className="text-xs font-mono text-slate-500 dark:text-slate-400">{alert.section}</span>
                  </div>
                  <span className="text-sm font-bold text-slate-700 dark:text-slate-200">{inr(alert.amount)}</span>
                </div>
                <p className="text-sm font-medium text-slate-800 dark:text-slate-100 mt-1">{alert.title}</p>
                {expandedAlert === alert.id && (
                  <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-600">
                    <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">Action Required</p>
                    <p className="text-xs text-slate-700 dark:text-slate-300 mt-0.5">{alert.action}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Stock ───────────────────────────────────────────────────────── */}
      {active === 'stock' && (
        <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">Current Inventory</h3>
            <span className="text-sm text-slate-500 dark:text-slate-400">Total: {inr(totalStockValue)}</span>
          </div>
          <div className="space-y-3">
            {STOCK.map(item => (
              <div key={item.label} className="flex items-center gap-3">
                <span className="text-xs text-slate-600 dark:text-slate-400 w-24 shrink-0">{item.label}</span>
                <div className="flex-1 bg-slate-100 dark:bg-slate-700 rounded-full h-4 overflow-hidden">
                  <div
                    className="h-4 rounded-full flex items-center justify-end pr-2 text-white text-xs font-medium"
                    style={{
                      width: `${Math.min(100, item.qtl / 20)}%`,
                      backgroundColor: item.color,
                      minWidth: '40px',
                    }}
                  >
                    {item.qtl} qtl
                  </div>
                </div>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-200 w-24 text-right">{inr(item.value)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Conversion ──────────────────────────────────────────────────── */}
      {active === 'conversion' && (
        <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Lot-wise Milling Log</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-600">
                  <th className="text-left pb-2">Lot</th>
                  <th className="text-left pb-2">Variety</th>
                  <th className="text-right pb-2">Paddy</th>
                  <th className="text-right pb-2">Rice</th>
                  <th className="text-right pb-2">Outturn</th>
                  <th className="text-right pb-2">Bran</th>
                  <th className="text-center pb-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {LOTS.map(lot => (
                  <tr key={lot.lotId} className="hover:bg-slate-50 dark:hover:bg-slate-700/30">
                    <td className="py-2.5 font-mono text-xs text-slate-600 dark:text-slate-400">{lot.lotId}</td>
                    <td className="py-2.5 text-slate-800 dark:text-slate-100">{lot.variety}</td>
                    <td className="py-2.5 text-right text-slate-600 dark:text-slate-400">{lot.paddyQtl} qtl</td>
                    <td className="py-2.5 text-right text-slate-600 dark:text-slate-400">
                      {lot.riceQtl > 0 ? `${lot.riceQtl} qtl` : '—'}
                    </td>
                    <td className="py-2.5 text-right">
                      {lot.outturn > 0 ? (
                        <span className={`font-medium ${lot.outturn >= 67 ? 'text-green-600 dark:text-green-400' : 'text-orange-600 dark:text-orange-400'}`}>
                          {lot.outturn}%
                        </span>
                      ) : '—'}
                    </td>
                    <td className="py-2.5 text-right text-slate-500 dark:text-slate-400">
                      {lot.branQtl > 0 ? `${lot.branQtl} qtl` : '—'}
                    </td>
                    <td className="py-2.5 text-center"><StatusBadge status={lot.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg text-xs text-slate-500 dark:text-slate-400">
            Standard outturn: 67% (Sona Masoori/BPT: 68%). Below 65% = efficiency alert.
          </div>
        </section>
      )}

      {/* ── MSP ─────────────────────────────────────────────────────────── */}
      {active === 'msp' && (
        <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 space-y-4">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">MSP Reference — Kharif 2024-25</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              { label: 'MSP Common Paddy',  value: `₹${MSP_DATA.paddy_common}/qtl`,   color: 'green'  },
              { label: 'MSP Grade-A Paddy', value: `₹${MSP_DATA.paddy_grade_a}/qtl`,  color: 'green'  },
              { label: 'YoY Increase',      value: `+₹${MSP_DATA.yoy_increase} (+${MSP_DATA.yoy_pct}%)`, color: 'blue' },
              { label: 'Break-even Rice',   value: '₹2,186/qtl',                       color: 'orange' },
              { label: 'FCI Milling Rate',  value: '₹27.50/qtl',                       color: 'slate'  },
              { label: 'FCI Economic Cost', value: '₹2,597/qtl',                       color: 'slate'  },
            ].map(m => (
              <div key={m.label} className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                <p className="text-xs text-slate-500 dark:text-slate-400">{m.label}</p>
                <p className={`text-base font-bold text-${m.color}-600 dark:text-${m.color}-400 mt-0.5`}>{m.value}</p>
              </div>
            ))}
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">MSP History (Common Paddy)</p>
            {Object.entries({
              '2020-21': 1868, '2021-22': 1940, '2022-23': 2015, '2023-24': 2183, '2024-25': 2300
            }).map(([yr, msp]) => (
              <div key={yr} className="flex items-center gap-3 mb-1.5">
                <span className="text-xs text-slate-500 dark:text-slate-400 w-16">{yr}</span>
                <div className="flex-1 bg-slate-100 dark:bg-slate-700 rounded-full h-3">
                  <div
                    className="bg-green-500 h-3 rounded-full"
                    style={{ width: `${((msp - 1800) / 600) * 100}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-slate-700 dark:text-slate-200 w-20 text-right">₹{msp}/qtl</span>
              </div>
            ))}
          </div>
          <div className="p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg text-xs text-amber-700 dark:text-amber-300">
            <strong>Compliance:</strong> Purchasing paddy below MSP in AP/TS is punishable under APMC Act.
            Always pay ≥ MSP and maintain Form-F (APMC purchase receipt).
          </div>
        </section>
      )}
    </div>
  );
}
