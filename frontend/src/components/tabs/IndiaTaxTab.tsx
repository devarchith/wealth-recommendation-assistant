'use client';

import { useState, useMemo } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Regime = 'new' | 'old';

interface IncomeInputs {
  salary:          number;
  houseProperty:   number;
  businessIncome:  number;
  capitalGains:    number;
  otherIncome:     number;
}

interface DeductionInputs {
  sec80C:          number;   // Max ₹1,50,000
  nps80CCD:        number;   // Max ₹50,000
  sec80D_self:     number;   // Health insurance self
  sec80D_parents:  number;   // Health insurance parents
  hra:             number;   // HRA exemption claimed
  otherDeductions: number;
}

interface TaxSlab {
  label: string;
  rate: number;
  income: number;
  tax: number;
}

interface RegimeTaxResult {
  grossIncome:     number;
  totalDeductions: number;
  taxableIncome:   number;
  basicTax:        number;
  cess:            number;
  totalTax:        number;
  effectiveRate:   number;
  slabs:           TaxSlab[];
  rebate87A:       number;
}

// ---------------------------------------------------------------------------
// Tax computation
// ---------------------------------------------------------------------------

const NEW_REGIME_SLABS = [
  { max: 300_000,        rate: 0.00, label: 'Up to ₹3 L' },
  { max: 700_000,        rate: 0.05, label: '₹3 L – ₹7 L' },
  { max: 1_000_000,      rate: 0.10, label: '₹7 L – ₹10 L' },
  { max: 1_200_000,      rate: 0.15, label: '₹10 L – ₹12 L' },
  { max: 1_500_000,      rate: 0.20, label: '₹12 L – ₹15 L' },
  { max: Infinity,       rate: 0.30, label: 'Above ₹15 L' },
];

const OLD_REGIME_SLABS = [
  { max: 250_000,        rate: 0.00, label: 'Up to ₹2.5 L' },
  { max: 500_000,        rate: 0.05, label: '₹2.5 L – ₹5 L' },
  { max: 1_000_000,      rate: 0.20, label: '₹5 L – ₹10 L' },
  { max: Infinity,       rate: 0.30, label: 'Above ₹10 L' },
];

function computeRegimeTax(
  income: IncomeInputs,
  deductions: DeductionInputs,
  regime: Regime,
): RegimeTaxResult {
  const gross =
    income.salary + income.houseProperty + income.businessIncome +
    income.capitalGains + income.otherIncome;

  const totalDeductions =
    regime === 'old'
      ? Math.min(deductions.sec80C, 150_000) +
        Math.min(deductions.nps80CCD, 50_000) +
        Math.min(deductions.sec80D_self, 25_000) +
        Math.min(deductions.sec80D_parents, 50_000) +
        deductions.hra +
        deductions.otherDeductions
      : 75_000; // Standard deduction in new regime

  const taxable = Math.max(0, gross - totalDeductions);
  const slabs   = regime === 'new' ? NEW_REGIME_SLABS : OLD_REGIME_SLABS;

  let prev = 0;
  let basicTax = 0;
  const slabDetails: TaxSlab[] = [];

  for (const slab of slabs) {
    if (taxable <= prev) break;
    const incomeInSlab = Math.min(taxable, slab.max === Infinity ? taxable : slab.max) - prev;
    const taxInSlab    = incomeInSlab * slab.rate;
    basicTax += taxInSlab;
    if (incomeInSlab > 0) {
      slabDetails.push({
        label:  slab.label,
        rate:   slab.rate * 100,
        income: incomeInSlab,
        tax:    taxInSlab,
      });
    }
    prev = slab.max === Infinity ? taxable : slab.max;
  }

  // Rebate 87A
  const rebateLimit = regime === 'new' ? 700_000 : 500_000;
  const rebateCap   = regime === 'new' ? 25_000  : 12_500;
  const rebate87A   = taxable <= rebateLimit ? Math.min(basicTax, rebateCap) : 0;
  basicTax -= rebate87A;

  const cess     = Math.max(0, basicTax) * 0.04;
  const totalTax = Math.max(0, basicTax) + cess;
  const effectiveRate = gross > 0 ? (totalTax / gross) * 100 : 0;

  return {
    grossIncome:     gross,
    totalDeductions,
    taxableIncome:   taxable,
    basicTax:        Math.max(0, basicTax),
    cess,
    totalTax,
    effectiveRate,
    slabs:           slabDetails,
    rebate87A,
  };
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

function inr(n: number): string {
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000)    return `₹${(n / 1_00_000).toFixed(2)} L`;
  return `₹${n.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

// ---------------------------------------------------------------------------
// Advance tax schedule
// ---------------------------------------------------------------------------

const ADVANCE_TAX_QUARTERS = [
  { quarter: 'Q1', due: '15 Jun 2024', pct: 15 },
  { quarter: 'Q2', due: '15 Sep 2024', pct: 45 },
  { quarter: 'Q3', due: '15 Dec 2024', pct: 75 },
  { quarter: 'Q4', due: '15 Mar 2025', pct: 100 },
];

// ---------------------------------------------------------------------------
// Section components
// ---------------------------------------------------------------------------

function InputRow({
  label,
  value,
  onChange,
  max,
  note,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  max?: number;
  note?: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-600 dark:text-slate-400">
        {label}
        {note && <span className="ml-1 text-xs text-slate-400">({note})</span>}
      </label>
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">₹</span>
        <input
          type="number"
          min={0}
          max={max}
          value={value || ''}
          onChange={(e) => onChange(Math.max(0, Number(e.target.value)))}
          className="w-full pl-7 pr-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600
                     bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100
                     text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          placeholder="0"
        />
      </div>
    </div>
  );
}

function RegimeCard({
  regime,
  result,
  isRecommended,
  isSelected,
  onSelect,
}: {
  regime: Regime;
  result: RegimeTaxResult;
  isRecommended: boolean;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const label = regime === 'new' ? 'New Regime (FY 2024-25)' : 'Old Regime';
  const color = regime === 'new' ? 'blue' : 'emerald';

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
        isSelected
          ? `border-${color}-500 bg-${color}-50 dark:bg-${color}-900/20`
          : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-semibold text-sm text-slate-800 dark:text-slate-100">{label}</span>
        <div className="flex gap-1">
          {isRecommended && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
              Recommended
            </span>
          )}
          {isSelected && (
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium bg-${color}-100 dark:bg-${color}-900/30 text-${color}-700 dark:text-${color}-300`}>
              Selected
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Taxable Income</p>
          <p className="font-semibold text-slate-800 dark:text-slate-100">{inr(result.taxableIncome)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Total Tax</p>
          <p className={`font-bold text-lg text-${color}-600 dark:text-${color}-400`}>{inr(result.totalTax)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Effective Rate</p>
          <p className="font-semibold text-slate-800 dark:text-slate-100">{result.effectiveRate.toFixed(1)}%</p>
        </div>
        <div>
          <p className="text-xs text-slate-500 dark:text-slate-400">Deductions</p>
          <p className="font-semibold text-slate-800 dark:text-slate-100">{inr(result.totalDeductions)}</p>
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function IndiaTaxTab() {
  const [income, setIncome] = useState<IncomeInputs>({
    salary:         0,
    houseProperty:  0,
    businessIncome: 0,
    capitalGains:   0,
    otherIncome:    0,
  });

  const [deductions, setDeductions] = useState<DeductionInputs>({
    sec80C:         0,
    nps80CCD:       0,
    sec80D_self:    0,
    sec80D_parents: 0,
    hra:            0,
    otherDeductions:0,
  });

  const [selectedRegime, setSelectedRegime] = useState<Regime>('new');
  const [tdsDeducted, setTdsDeducted]       = useState(0);
  const [advPaid, setAdvPaid]               = useState(0);

  // Memoised tax for both regimes
  const newResult = useMemo(() => computeRegimeTax(income, deductions, 'new'), [income, deductions]);
  const oldResult = useMemo(() => computeRegimeTax(income, deductions, 'old'), [income, deductions]);

  const recommended: Regime = newResult.totalTax <= oldResult.totalTax ? 'new' : 'old';
  const saving = Math.abs(newResult.totalTax - oldResult.totalTax);

  const selectedResult = selectedRegime === 'new' ? newResult : oldResult;
  const netTax         = Math.max(0, selectedResult.totalTax - tdsDeducted - advPaid);
  const isRefund       = selectedResult.totalTax - tdsDeducted < 0;

  function setIncomeField(key: keyof IncomeInputs, val: number) {
    setIncome((p) => ({ ...p, [key]: val }));
  }
  function setDeductionField(key: keyof DeductionInputs, val: number) {
    setDeductions((p) => ({ ...p, [key]: val }));
  }

  return (
    <div className="space-y-6 pb-8">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
          India Income Tax Dashboard
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          FY 2024-25 (AY 2025-26) — Compare old vs new regime and plan advance tax
        </p>
      </div>

      {/* Income inputs */}
      <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Income Sources</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <InputRow label="Salary / Pension"       value={income.salary}         onChange={(v) => setIncomeField('salary', v)} />
          <InputRow label="House Property Income"  value={income.houseProperty}  onChange={(v) => setIncomeField('houseProperty', v)} note="Net after 30% deduction" />
          <InputRow label="Business / Freelance"   value={income.businessIncome} onChange={(v) => setIncomeField('businessIncome', v)} />
          <InputRow label="Capital Gains"          value={income.capitalGains}   onChange={(v) => setIncomeField('capitalGains', v)} />
          <InputRow label="Other Income"           value={income.otherIncome}    onChange={(v) => setIncomeField('otherIncome', v)} />
        </div>
        <div className="mt-4 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Gross Total Income: <span className="text-brand-600 dark:text-brand-400 font-bold">{inr(newResult.grossIncome)}</span>
          </p>
        </div>
      </section>

      {/* Deductions (old regime) */}
      <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-1">Deductions (Old Regime)</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          These apply only under old regime. New regime uses ₹75,000 standard deduction.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <InputRow label="Sec 80C (PPF, ELSS, LIC…)" value={deductions.sec80C}         max={150000} onChange={(v) => setDeductionField('sec80C', v)}         note="Max ₹1.5 L" />
          <InputRow label="Sec 80CCD(1B) — NPS"        value={deductions.nps80CCD}       max={50000}  onChange={(v) => setDeductionField('nps80CCD', v)}        note="Max ₹50K" />
          <InputRow label="Sec 80D — Self & Family"    value={deductions.sec80D_self}    max={25000}  onChange={(v) => setDeductionField('sec80D_self', v)}     note="Max ₹25K" />
          <InputRow label="Sec 80D — Parents"          value={deductions.sec80D_parents} max={50000}  onChange={(v) => setDeductionField('sec80D_parents', v)}  note="Max ₹50K (senior)" />
          <InputRow label="HRA Exemption"              value={deductions.hra}                         onChange={(v) => setDeductionField('hra', v)} />
          <InputRow label="Other Deductions (80E, 80G…)" value={deductions.otherDeductions}           onChange={(v) => setDeductionField('otherDeductions', v)} />
        </div>
      </section>

      {/* Regime comparison */}
      <section>
        <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-3">Regime Comparison</h3>
        {saving > 0 && (
          <div className="mb-3 px-4 py-2 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 text-green-800 dark:text-green-200 text-sm">
            {recommended === 'new' ? 'New' : 'Old'} regime saves you <strong>{inr(saving)}</strong> this year.
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <RegimeCard regime="new" result={newResult} isRecommended={recommended === 'new'} isSelected={selectedRegime === 'new'} onSelect={() => setSelectedRegime('new')} />
          <RegimeCard regime="old" result={oldResult} isRecommended={recommended === 'old'} isSelected={selectedRegime === 'old'} onSelect={() => setSelectedRegime('old')} />
        </div>
      </section>

      {/* Slab breakdown for selected regime */}
      {selectedResult.slabs.length > 0 && (
        <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">
            Tax Slab Breakdown — {selectedRegime === 'new' ? 'New' : 'Old'} Regime
          </h3>
          <div className="space-y-2">
            {selectedResult.slabs.map((slab) => (
              <div key={slab.label} className="flex items-center justify-between text-sm">
                <span className="text-slate-600 dark:text-slate-400">{slab.label} @ {slab.rate}%</span>
                <div className="flex gap-6 text-right">
                  <span className="text-slate-500 dark:text-slate-400 w-24">{inr(slab.income)}</span>
                  <span className="font-medium text-slate-800 dark:text-slate-100 w-20">{inr(slab.tax)}</span>
                </div>
              </div>
            ))}
            <div className="border-t border-slate-200 dark:border-slate-600 pt-2 mt-2 space-y-1">
              {selectedResult.rebate87A > 0 && (
                <div className="flex items-center justify-between text-sm text-green-600 dark:text-green-400">
                  <span>Rebate u/s 87A</span>
                  <span className="font-medium">−{inr(selectedResult.rebate87A)}</span>
                </div>
              )}
              <div className="flex items-center justify-between text-sm text-slate-500 dark:text-slate-400">
                <span>Health & Education Cess (4%)</span>
                <span>{inr(selectedResult.cess)}</span>
              </div>
              <div className="flex items-center justify-between font-bold text-slate-900 dark:text-slate-100">
                <span>Total Tax</span>
                <span>{inr(selectedResult.totalTax)}</span>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* TDS and net payable */}
      <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">TDS & Net Tax Payable</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
          <InputRow label="TDS Already Deducted" value={tdsDeducted} onChange={setTdsDeducted} />
          <InputRow label="Advance Tax Paid"     value={advPaid}     onChange={setAdvPaid} />
        </div>
        <div className={`p-4 rounded-xl ${isRefund ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700' : 'bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-700'}`}>
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">
            {isRefund ? 'Refund Due' : 'Tax Payable (Self-Assessment)'}
          </p>
          <p className={`text-3xl font-bold ${isRefund ? 'text-green-600 dark:text-green-400' : 'text-orange-600 dark:text-orange-400'}`}>
            {inr(Math.abs(isRefund ? selectedResult.totalTax - tdsDeducted : netTax))}
          </p>
          {isRefund && (
            <p className="text-xs text-green-600 dark:text-green-400 mt-1">
              File ITR before July 31 to claim refund. Refund + interest u/s 244A if delayed.
            </p>
          )}
        </div>
      </section>

      {/* Advance tax schedule */}
      <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Advance Tax Schedule — FY 2024-25</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          Required when net tax liability &gt; ₹10,000 after TDS. Based on selected regime.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-600">
                <th className="text-left pb-2">Quarter</th>
                <th className="text-left pb-2">Due Date</th>
                <th className="text-right pb-2">Cumulative %</th>
                <th className="text-right pb-2">Amount Due</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {ADVANCE_TAX_QUARTERS.map((q) => {
                const cumAmt = (selectedResult.totalTax * q.pct) / 100;
                return (
                  <tr key={q.quarter}>
                    <td className="py-2.5 font-medium text-slate-800 dark:text-slate-100">{q.quarter}</td>
                    <td className="py-2.5 text-slate-600 dark:text-slate-400">{q.due}</td>
                    <td className="py-2.5 text-right text-slate-600 dark:text-slate-400">{q.pct}%</td>
                    <td className="py-2.5 text-right font-semibold text-slate-800 dark:text-slate-100">
                      {inr(cumAmt)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {selectedResult.totalTax > 10_000 && (
          <p className="text-xs text-orange-600 dark:text-orange-400 mt-3">
            Late payment attracts 1% per month interest u/s 234C. Pay via Challan 280 (Code 100).
          </p>
        )}
      </section>

      {/* Key deadlines */}
      <section className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5">
        <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-4">Key ITR Deadlines — AY 2025-26</h3>
        <div className="space-y-2">
          {[
            { label: 'ITR filing (individuals, no audit)', date: '31 Jul 2025', urgent: true },
            { label: 'ITR filing (audit cases)',            date: '31 Oct 2025', urgent: false },
            { label: 'Belated / Revised ITR',              date: '31 Dec 2025', urgent: false },
            { label: 'Form 16 issuance by employer',       date: '15 Jun 2025', urgent: true },
            { label: 'Form 26AS / AIS available',          date: 'Apr 2025',    urgent: false },
          ].map((d) => (
            <div key={d.label} className={`flex items-center justify-between p-3 rounded-lg ${d.urgent ? 'bg-orange-50 dark:bg-orange-900/20' : 'bg-slate-50 dark:bg-slate-700/50'}`}>
              <span className="text-sm text-slate-700 dark:text-slate-200">{d.label}</span>
              <span className={`text-sm font-medium ${d.urgent ? 'text-orange-700 dark:text-orange-300' : 'text-slate-600 dark:text-slate-400'}`}>{d.date}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
