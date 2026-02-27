'use strict';

/**
 * Privacy Placeholder Data Seeder
 * Provides realistic-looking but entirely fake placeholder data for each module.
 * Used by the Privacy Reset feature to overwrite real user data in-place.
 *
 * Modules covered: rice_mill | ca | business | budget | investment | personal
 */

const PLACEHOLDERS = {
  rice_mill: {
    description: 'Rice Mill operations data',
    categories: {
      stock: {
        label: 'Stock & Inventory',
        data: {
          paddy_qtl:       1000,
          rice_raw_qtl:    600,
          rice_bran_qtl:   100,
          husk_qtl:        200,
          broken_rice_qtl: 40,
          last_updated:    '2024-01-01',
        },
      },
      financials: {
        label: 'Financial Records',
        data: {
          monthly_revenue_inr:   1_500_000,
          monthly_expenses_inr:  1_200_000,
          fci_receivable_inr:    250_000,
          cc_limit_inr:          2_000_000,
          cc_utilised_pct:       50,
          cash_runway_days:      30,
        },
      },
      compliance: {
        label: 'GST & Compliance Records',
        data: {
          gstin:            'XXXXXXXXXXXX1ZX',
          gstr1_filed:      true,
          gstr3b_filed:     true,
          pending_tax_inr:  0,
          last_filing_date: '2024-01-01',
        },
      },
      milling: {
        label: 'Milling Logs',
        data: {
          lots: [
            { lot_id: 'LOT001', variety: 'Demo Variety', paddy_qtl: 200, rice_qtl: 134, outturn_pct: 67, status: 'completed' },
            { lot_id: 'LOT002', variety: 'Sample Lot',   paddy_qtl: 150, rice_qtl: 0,   outturn_pct: 0,  status: 'pending'   },
          ],
        },
      },
    },
  },

  ca: {
    description: 'CA Portal client and billing data',
    categories: {
      clients: {
        label: 'Client Records',
        data: {
          clients: [
            { id: 'C001', name: 'Demo Client A', type: 'Individual', pan: 'XXXXX0000X', annual_fee: 15000, status: 'green' },
            { id: 'C002', name: 'Demo Client B', type: 'Pvt Ltd',    pan: 'XXXXX0001X', annual_fee: 48000, status: 'green' },
          ],
        },
      },
      billing: {
        label: 'Billing & Revenue Records',
        data: {
          total_billed_inr:       150_000,
          collected_inr:          120_000,
          outstanding_inr:         30_000,
          collection_rate_pct:     80,
          overdue_30d_inr:          0,
        },
      },
      notices: {
        label: 'Tax Notice Records',
        data: {
          notices: [
            { notice_id: 'N001', section: 'Sec 143(1)', client: 'Demo Client A', status: 'resolved', date: '2024-01-01' },
          ],
        },
      },
    },
  },

  business: {
    description: 'Business financial and GST data',
    categories: {
      pl: {
        label: 'P&L Records',
        data: {
          monthly_revenue_inr:  500_000,
          cogs_inr:             300_000,
          opex_inr:             100_000,
          gross_profit_inr:     200_000,
          net_profit_inr:       100_000,
          gross_margin_pct:     40,
          net_margin_pct:       20,
        },
      },
      cashflow: {
        label: 'Receivables & Payables',
        data: {
          accounts_receivable: [
            { name: 'Demo Debtor A', amount: 50_000, days_overdue: 0 },
            { name: 'Demo Debtor B', amount: 30_000, days_overdue: 0 },
          ],
          accounts_payable: [
            { name: 'Demo Supplier A', amount: 40_000, days_to_due: 15 },
          ],
        },
      },
      payroll: {
        label: 'Payroll & Statutory Deposits',
        data: {
          employee_count:  10,
          tds_deposit_inr:  5_000,
          epf_deposit_inr:  8_400,
          esic_deposit_inr: 1_750,
          month:           '2024-01',
        },
      },
      gst: {
        label: 'GST Filing Records',
        data: {
          gstin:            'XXXXXXXXXXXX1ZX',
          gstr1_filed:      true,
          gstr3b_filed:     true,
          pending_tax_inr:  0,
        },
      },
    },
  },

  budget: {
    description: 'Personal budget and spending data',
    categories: {
      income: {
        label: 'Income Records',
        data: {
          monthly_income_inr: 50_000,
          other_income_inr:    5_000,
        },
      },
      spending: {
        label: 'Spending & Category Data',
        data: {
          categories: {
            housing:       10_000,
            food:           6_000,
            transport:      3_000,
            utilities:      2_000,
            entertainment:  2_000,
            healthcare:     1_500,
            savings:        7_500,
            others:         3_000,
          },
        },
      },
    },
  },

  investment: {
    description: 'Investment portfolio and allocation data',
    categories: {
      portfolio: {
        label: 'Portfolio Holdings',
        data: {
          risk_profile:  'moderate',
          allocation: {
            equity_pct:  60,
            debt_pct:    30,
            gold_pct:    10,
          },
          total_invested_inr: 500_000,
          current_value_inr:  525_000,
          xirr_pct:            5.0,
        },
      },
    },
  },

  personal: {
    description: 'User profile and session preferences',
    categories: {
      profile: {
        label: 'Profile Information',
        data: {
          name:      'Demo User',
          email:     'demo@example.com',
          phone:     '+91-XXXXXXXXXX',
          pan:       'XXXXX0000X',
          gstin:     null,
          role:      'individual',
          joined:    '2024-01-01',
        },
      },
    },
  },
};

/**
 * Get placeholder data for a specific module and optional categories.
 * @param {string} module - Module key (rice_mill | ca | business | budget | investment | personal)
 * @param {string[]} [categories] - Optional list of category keys to include. Defaults to all.
 * @returns {{ module: string, seeded: Object, categories_reset: string[] }}
 */
function getPlaceholderData(module, categories) {
  const mod = PLACEHOLDERS[module];
  if (!mod) throw new Error(`Unknown module: ${module}`);

  const allCategories = Object.keys(mod.categories);
  const targetCategories = Array.isArray(categories) && categories.length > 0
    ? categories.filter(c => allCategories.includes(c))
    : allCategories;

  const seeded = {};
  for (const cat of targetCategories) {
    seeded[cat] = mod.categories[cat].data;
  }

  return { module, seeded, categories_reset: targetCategories };
}

/**
 * List all modules and their categories with human-readable labels.
 */
function listModules() {
  return Object.entries(PLACEHOLDERS).map(([key, mod]) => ({
    module:      key,
    description: mod.description,
    categories:  Object.entries(mod.categories).map(([catKey, cat]) => ({
      key:   catKey,
      label: cat.label,
    })),
  }));
}

module.exports = { getPlaceholderData, listModules, PLACEHOLDERS };
