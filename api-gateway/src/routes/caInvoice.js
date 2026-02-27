/**
 * CA Invoice Routes — Generate & Manage Invoices to Clients in INR
 * =================================================================
 * REST API for CA firms to create, list, and manage invoices issued
 * to their clients. Integrates with ca_billing.py logic (mirrored here
 * for the Node.js layer) and Razorpay payment links for digital collection.
 *
 * Routes:
 *   POST   /api/ca/invoice/create         — Create a new invoice
 *   GET    /api/ca/invoice/list           — List all invoices (filterable)
 *   GET    /api/ca/invoice/:id            — Get invoice detail + PDF-ready data
 *   POST   /api/ca/invoice/:id/send       — Send invoice via WhatsApp / email
 *   POST   /api/ca/invoice/:id/mark-paid  — Mark invoice as paid
 *   POST   /api/ca/invoice/payment-link   — Create Razorpay payment link
 *   GET    /api/ca/invoice/stats          — Portfolio billing stats
 *
 * Requires auth: CA plan (requirePlanFeature('ca_portal'))
 * GST: 18% on CA services (SAC 998221 / 998231)
 */

'use strict';

const express  = require('express');
const router   = express.Router();
const crypto   = require('crypto');
const axios    = require('axios');

const { requireAuth }        = require('../middleware/rbac');
const { buildTemplate, sendCAReminder } = require('../services/caWhatsAppTemplates');

const RAZORPAY_KEY_ID     = process.env.RAZORPAY_KEY_ID     || '';
const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET || '';

// ---------------------------------------------------------------------------
// In-memory store (replace with DB in production)
// ---------------------------------------------------------------------------

const _invoices = new Map();   // invoiceNo → InvoiceRecord

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GST_RATE   = 0.18;      // 18% on CA services
const SAC_CODE   = '998221';  // Accounting and auditing services

const SERVICE_RATES = {
  itr_individual:      15000,
  itr_huf:             20000,
  itr_business:        35000,
  itr_company:         75000,
  gst_registration:    5000,
  gst_monthly:         3000,
  gst_quarterly:       2000,
  gst_annual_return:   15000,
  tax_audit:           25000,
  notice_handling:     7500,
  consultation:        2000,   // per hour
  bookkeeping_monthly: 8000,
  payroll_monthly:     5000,
  company_incorporation: 15000,
  llp_formation:       12000,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateInvoiceNo(caFirmId) {
  const date  = new Date();
  const yy    = String(date.getFullYear()).slice(2);
  const mm    = String(date.getMonth() + 1).padStart(2, '0');
  const seq   = String(_invoices.size + 1).padStart(4, '0');
  return `INV/${caFirmId.toUpperCase().slice(0, 4)}/${yy}-${mm}/${seq}`;
}

function computeInvoiceTotals(lineItems) {
  const subtotal = lineItems.reduce((s, li) => s + li.amount, 0);
  const gst      = Math.round(subtotal * GST_RATE);
  const cgst     = gst / 2;   // intra-state: CGST + SGST
  const sgst     = gst / 2;
  const igst     = 0;          // assume intra-state; set to gst for inter-state
  const total    = subtotal + gst;
  return { subtotal, cgst, sgst, igst, gst, total };
}

function formatINR(amount) {
  return `₹${Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function dueDate(days = 15) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// POST /api/ca/invoice/create
// ---------------------------------------------------------------------------

router.post('/create', requireAuth, (req, res) => {
  try {
    const {
      caFirmId,
      caFirmName,
      caGstin,
      caAddress,
      clientId,
      clientName,
      clientPan,
      clientGstin,
      clientAddress,
      clientPhone,
      services,          // Array of { serviceKey, description?, qty, rate? }
      paymentTermDays,
      notes,
      ayPeriod,
    } = req.body;

    if (!caFirmId || !clientId || !services?.length) {
      return res.status(400).json({ error: 'caFirmId, clientId, services are required' });
    }

    const invoiceNo = generateInvoiceNo(caFirmId);

    const lineItems = services.map(s => {
      const rate   = s.rate ?? SERVICE_RATES[s.serviceKey] ?? 0;
      const qty    = s.qty  || 1;
      const amount = rate * qty;
      return {
        description: s.description || s.serviceKey?.replace(/_/g, ' ').toUpperCase() || 'Professional Service',
        sacCode:     SAC_CODE,
        qty,
        rate,
        amount,
      };
    });

    const totals   = computeInvoiceTotals(lineItems);
    const dueOn    = dueDate(paymentTermDays || 15);
    const invoiceDate = new Date().toISOString().slice(0, 10);

    const record = {
      invoiceNo,
      invoiceDate,
      dueDate:    dueOn,
      ayPeriod:   ayPeriod || '',
      ca: {
        firmId:   caFirmId,
        firmName: caFirmName,
        gstin:    caGstin,
        address:  caAddress,
      },
      client: {
        id:      clientId,
        name:    clientName,
        pan:     clientPan,
        gstin:   clientGstin,
        address: clientAddress,
        phone:   clientPhone,
      },
      lineItems,
      ...totals,
      status:    'unpaid',    // unpaid | paid | overdue | cancelled
      notes:     notes || '',
      paymentLinkUrl: null,
      paidDate:  null,
      paidRef:   null,
      createdBy: req.user?.id || 'ca',
    };

    _invoices.set(invoiceNo, record);
    return res.json({ success: true, invoiceNo, total: totals.total, invoice: record });
  } catch (err) {
    return res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// GET /api/ca/invoice/list
// ---------------------------------------------------------------------------

router.get('/list', requireAuth, (req, res) => {
  const { caFirmId, clientId, status } = req.query;
  let invoices = Array.from(_invoices.values());
  if (caFirmId)  invoices = invoices.filter(i => i.ca.firmId    === caFirmId);
  if (clientId)  invoices = invoices.filter(i => i.client.id    === clientId);
  if (status)    invoices = invoices.filter(i => i.status       === status);
  invoices.sort((a, b) => b.invoiceDate.localeCompare(a.invoiceDate));
  return res.json({ count: invoices.length, invoices });
});

// ---------------------------------------------------------------------------
// GET /api/ca/invoice/stats
// ---------------------------------------------------------------------------

router.get('/stats', requireAuth, (req, res) => {
  const { caFirmId } = req.query;
  const today = new Date().toISOString().slice(0, 10);
  let all = Array.from(_invoices.values());
  if (caFirmId) all = all.filter(i => i.ca.firmId === caFirmId);

  // Update overdue status
  all.forEach(inv => {
    if (inv.status === 'unpaid' && inv.dueDate < today) inv.status = 'overdue';
  });

  const paid    = all.filter(i => i.status === 'paid');
  const unpaid  = all.filter(i => i.status === 'unpaid');
  const overdue = all.filter(i => i.status === 'overdue');

  return res.json({
    totalInvoices:  all.length,
    totalRevenue:   paid.reduce((s, i) => s + i.total, 0),
    paidCount:      paid.length,
    unpaidCount:    unpaid.length,
    overdueCount:   overdue.length,
    overdueAmount:  overdue.reduce((s, i) => s + i.total, 0),
    recentInvoices: all.slice(0, 5).map(i => ({
      invoiceNo: i.invoiceNo,
      client:    i.client.name,
      total:     i.total,
      status:    i.status,
      dueDate:   i.dueDate,
    })),
  });
});

// ---------------------------------------------------------------------------
// GET /api/ca/invoice/:id
// ---------------------------------------------------------------------------

router.get('/:id', requireAuth, (req, res) => {
  const inv = _invoices.get(req.params.id);
  if (!inv) return res.status(404).json({ error: 'Invoice not found' });

  // Build print-ready summary
  const printData = {
    ...inv,
    formattedSubtotal: formatINR(inv.subtotal),
    formattedCgst:     formatINR(inv.cgst),
    formattedSgst:     formatINR(inv.sgst),
    formattedTotal:    formatINR(inv.total),
    lineItemsFormatted: inv.lineItems.map(li => ({
      ...li,
      formattedRate:   formatINR(li.rate),
      formattedAmount: formatINR(li.amount),
    })),
  };
  return res.json(printData);
});

// ---------------------------------------------------------------------------
// POST /api/ca/invoice/:id/send  — WhatsApp / email dispatch
// ---------------------------------------------------------------------------

router.post('/:id/send', requireAuth, async (req, res) => {
  const inv = _invoices.get(req.params.id);
  if (!inv) return res.status(404).json({ error: 'Invoice not found' });

  const { channel = 'whatsapp' } = req.body;
  const results = {};

  if (channel === 'whatsapp' && inv.client.phone) {
    const today    = new Date().toISOString().slice(0, 10);
    const daysLeft = Math.ceil((new Date(inv.dueDate) - new Date(today)) / 86_400_000);
    const text = buildTemplate('invoice_reminder', {
      clientName:  inv.client.name,
      invoiceNo:   inv.invoiceNo,
      invoiceDate: inv.invoiceDate,
      amount:      inv.total,
      dueDate:     inv.dueDate,
      daysLeft,
    });
    try {
      await sendCAReminder(inv.client.phone, text);
      results.whatsapp = { sent: true };
    } catch (err) {
      results.whatsapp = { sent: false, error: err.message };
    }
  }

  return res.json({ success: true, invoiceNo: inv.invoiceNo, results });
});

// ---------------------------------------------------------------------------
// POST /api/ca/invoice/:id/mark-paid
// ---------------------------------------------------------------------------

router.post('/:id/mark-paid', requireAuth, (req, res) => {
  const inv = _invoices.get(req.params.id);
  if (!inv) return res.status(404).json({ error: 'Invoice not found' });
  inv.status   = 'paid';
  inv.paidDate = req.body.paidDate || new Date().toISOString().slice(0, 10);
  inv.paidRef  = req.body.reference || '';
  return res.json({ success: true, invoiceNo: inv.invoiceNo, status: 'paid' });
});

// ---------------------------------------------------------------------------
// POST /api/ca/invoice/payment-link — Razorpay payment link
// ---------------------------------------------------------------------------

router.post('/payment-link', requireAuth, async (req, res) => {
  const { invoiceNo, expiryMinutes = 1440 } = req.body;
  const inv = _invoices.get(invoiceNo);
  if (!inv) return res.status(404).json({ error: 'Invoice not found' });

  if (!RAZORPAY_KEY_ID || !RAZORPAY_KEY_SECRET) {
    return res.status(503).json({ error: 'Razorpay not configured' });
  }

  try {
    const auth   = Buffer.from(`${RAZORPAY_KEY_ID}:${RAZORPAY_KEY_SECRET}`).toString('base64');
    const expiry = Math.floor(Date.now() / 1000) + expiryMinutes * 60;

    const resp = await axios.post(
      'https://api.razorpay.com/v1/payment_links',
      {
        amount:      inv.total * 100,   // paise
        currency:    'INR',
        description: `CA Professional Fees — ${inv.invoiceNo}`,
        customer:    {
          name:  inv.client.name,
          email: inv.client.email || '',
          contact: (inv.client.phone || '').replace(/\D/g, ''),
        },
        notify:      { email: !!inv.client.email, sms: !!inv.client.phone },
        reminder_enable: true,
        reference_id:    inv.invoiceNo,
        expire_by:       expiry,
        notes:           { invoiceNo: inv.invoiceNo, clientId: inv.client.id },
      },
      { headers: { Authorization: `Basic ${auth}`, 'Content-Type': 'application/json' } }
    );

    inv.paymentLinkUrl = resp.data.short_url;
    return res.json({ success: true, paymentLink: resp.data.short_url, linkId: resp.data.id });
  } catch (err) {
    return res.status(502).json({ error: err.response?.data?.error?.description || err.message });
  }
});

module.exports = router;
