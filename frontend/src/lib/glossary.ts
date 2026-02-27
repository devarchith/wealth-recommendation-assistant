/**
 * Bilingual Financial Terminology Glossary — English / Telugu
 * 80+ common financial and tax terms with plain-language definitions.
 */

export interface GlossaryTerm {
  id:           string;
  english:      string;
  telugu:       string;
  definition_en: string;
  definition_te: string;
  category:     string;
  example?:     string;
  example_te?:  string;
}

export const GLOSSARY: GlossaryTerm[] = [
  // Income Tax
  {
    id: 'itr', english: 'ITR (Income Tax Return)', telugu: 'ఆదాయపు పన్ను రిటర్న్ (ITR)',
    category: 'income_tax',
    definition_en: 'A form filed with the Income Tax Department declaring your income, deductions, and taxes paid for a financial year.',
    definition_te: 'ఆర్థిక సంవత్సరానికి మీ ఆదాయం, తగ్గింపులు మరియు చెల్లించిన పన్నులను ప్రకటించే ఫారం.',
    example: 'File ITR-1 for salary income below ₹50L with no capital gains.',
    example_te: 'రూ.50 లక్షల లోపు జీతం ఆదాయానికి ITR-1 దాఖలు చేయండి.',
  },
  {
    id: 'tds', english: 'TDS (Tax Deducted at Source)', telugu: 'మూలంలో పన్ను కోత (TDS)',
    category: 'income_tax',
    definition_en: 'Tax deducted by the payer before making payments such as salary, interest, rent, or professional fees.',
    definition_te: 'జీతం, వడ్డీ, అద్దె లేదా వృత్తి రుసుముల వంటి చెల్లింపులు చేయడానికి ముందే చెల్లింపుదారు తగ్గించే పన్ను.',
  },
  {
    id: 'form_26as', english: 'Form 26AS', telugu: 'ఫారం 26AS',
    category: 'income_tax',
    definition_en: 'Annual tax statement showing all TDS deducted, advance tax paid, and high-value transactions linked to your PAN.',
    definition_te: 'మీ PAN కి సంబంధించిన అన్ని TDS కోతలు, అడ్వాన్స్ పన్ను మరియు అధిక విలువ లావాదేవీలను చూపించే వార్షిక పన్ను నివేదిక.',
  },
  {
    id: 'new_regime', english: 'New Tax Regime', telugu: 'కొత్త పన్ను పద్ధతి',
    category: 'income_tax',
    definition_en: 'Tax regime introduced in FY 2020-21 with lower slab rates but no deductions under 80C, 80D, HRA etc.',
    definition_te: '2020-21 ఆర్థిక సంవత్సరంలో ప్రవేశపెట్టబడిన తక్కువ స్లాబ్ రేట్లు కలిగిన పన్ను పద్ధతి, కానీ 80C, 80D, HRA మొదలైన తగ్గింపులు లేవు.',
  },
  {
    id: 'old_regime', english: 'Old Tax Regime', telugu: 'పాత పన్ను పద్ధతి',
    category: 'income_tax',
    definition_en: 'Traditional tax regime allowing deductions under Section 80C, 80D, HRA, LTA, etc. to reduce taxable income.',
    definition_te: 'పన్ను విధించదగిన ఆదాయాన్ని తగ్గించడానికి సెక్షన్ 80C, 80D, HRA, LTA మొదలైన వాటి కింద తగ్గింపులను అనుమతించే సాంప్రదాయ పన్ను పద్ధతి.',
  },
  {
    id: 'sec80c', english: 'Section 80C', telugu: 'సెక్షన్ 80C',
    category: 'deductions',
    definition_en: 'Allows deduction of up to ₹1.5 lakh on investments like PPF, ELSS, NSC, LIC premium, home loan principal, etc.',
    definition_te: 'PPF, ELSS, NSC, LIC ప్రీమియం, గృహ రుణ మూలాన్ని మొదలైన వాటిలో పెట్టుబడులపై రూ.1.5 లక్షల వరకు తగ్గింపును అనుమతిస్తుంది.',
    example: 'Invest ₹1.5L in PPF to save ₹46,800 in tax (at 30% + 4% cess).',
  },
  {
    id: 'ppf', english: 'PPF (Public Provident Fund)', telugu: 'పబ్లిక్ ప్రావిడెంట్ ఫండ్ (PPF)',
    category: 'savings',
    definition_en: '15-year government-backed savings scheme with 7.1% interest (EEE: tax-free contributions, interest, and maturity).',
    definition_te: '7.1% వడ్డీతో 15 సంవత్సరాల ప్రభుత్వ-మద్దతు పొదుపు పథకం (EEE: పన్ను రహిత సహకారాలు, వడ్డీ మరియు మెచ్యూరిటీ).',
  },
  {
    id: 'elss', english: 'ELSS (Equity Linked Savings Scheme)', telugu: 'ఈక్విటీ లింక్డ్ సేవింగ్స్ స్కీమ్ (ELSS)',
    category: 'investments',
    definition_en: 'Mutual fund with 3-year lock-in eligible for 80C deduction. Returns market-linked (historically 12-15% p.a.).',
    definition_te: '80C తగ్గింపుకు అర్హమైన 3 సంవత్సరాల లాక్-ఇన్ తో మ్యూచువల్ ఫండ్. రాబడులు మార్కెట్-లింక్డ్ (చారిత్రాత్మకంగా 12-15% వార్షికంగా).',
  },
  {
    id: 'nps', english: 'NPS (National Pension System)', telugu: 'జాతీయ పెన్షన్ వ్యవస్థ (NPS)',
    category: 'retirement',
    definition_en: 'Government pension scheme giving additional ₹50,000 deduction u/s 80CCD(1B) beyond the 80C limit.',
    definition_te: '80C పరిమితికి మించి 80CCD(1B) కింద అదనంగా రూ.50,000 తగ్గింపు ఇచ్చే ప్రభుత్వ పెన్షన్ పథకం.',
  },
  {
    id: 'hra', english: 'HRA (House Rent Allowance)', telugu: 'గృహ అద్దె భత్యం (HRA)',
    category: 'allowances',
    definition_en: 'Allowance from employer for house rent. Exempt from tax based on the least of: actual HRA, 50%/40% of basic, or rent paid minus 10% basic.',
    definition_te: 'గృహ అద్దె కోసం యజమాని నుండి భత్యం. వాస్తవ HRA, బేసిక్ లో 50%/40%, లేదా చెల్లించిన అద్దె మైనస్ 10% బేసిక్ లో అతి తక్కువ మొత్తం ఆధారంగా పన్ను నుండి మినహాయించబడుతుంది.',
  },
  // GST
  {
    id: 'gst', english: 'GST (Goods and Services Tax)', telugu: 'వస్తు సేవల పన్ను (GST)',
    category: 'gst',
    definition_en: 'Unified indirect tax on supply of goods and services in India. Replaces VAT, service tax, excise duty, etc.',
    definition_te: 'భారతదేశంలో వస్తువులు మరియు సేవల సరఫరాపై ఏకీకృత పరోక్ష పన్ను. VAT, సేవా పన్ను, ఎక్సైజ్ సుంకం మొదలైన వాటిని భర్తీ చేస్తుంది.',
  },
  {
    id: 'igst', english: 'IGST (Integrated GST)', telugu: 'ఇంటిగ్రేటెడ్ GST (IGST)',
    category: 'gst',
    definition_en: 'GST levied on inter-state supply (one state to another). Collected by central government and shared with states.',
    definition_te: 'అంతర్రాష్ట్ర సరఫరాపై (ఒక రాష్ట్రం నుండి మరొకటి) విధించే GST. కేంద్ర ప్రభుత్వం వసూలు చేసి రాష్ట్రాలతో పంచుకుంటుంది.',
  },
  {
    id: 'cgst_sgst', english: 'CGST + SGST', telugu: 'CGST + SGST',
    category: 'gst',
    definition_en: 'GST on intra-state supply split equally: CGST (central) + SGST (state). Total equals the applicable GST rate.',
    definition_te: 'రాష్ట్రంలో సరఫరాపై GST సమానంగా విభజించబడింది: CGST (కేంద్ర) + SGST (రాష్ట్ర). మొత్తం వర్తించే GST రేటుకు సమానం.',
  },
  {
    id: 'itc', english: 'ITC (Input Tax Credit)', telugu: 'ఇన్పుట్ పన్ను క్రెడిట్ (ITC)',
    category: 'gst',
    definition_en: 'GST paid on purchases that can be offset against GST payable on sales. Reduces cascading effect of taxes.',
    definition_te: 'కొనుగోళ్లపై చెల్లించిన GST, అమ్మకాలపై చెల్లించవలసిన GST కి వ్యతిరేకంగా తగ్గించవచ్చు. పన్నుల కాస్కేడింగ్ ప్రభావాన్ని తగ్గిస్తుంది.',
  },
  {
    id: 'gstr1', english: 'GSTR-1', telugu: 'GSTR-1',
    category: 'gst',
    definition_en: 'Monthly/quarterly return for outward supplies (sales invoices). Due by 11th of following month (monthly filers).',
    definition_te: 'బాహ్య సరఫరాల (అమ్మకాల ఇన్వాయిస్) కోసం నెలవారీ/త్రైమాసిక రిటర్న్. తదుపరి నెల 11వ తేదీ లోగా (నెలవారీ దాఖలుదారులు).',
  },
  {
    id: 'gstr3b', english: 'GSTR-3B', telugu: 'GSTR-3B',
    category: 'gst',
    definition_en: 'Monthly summary return declaring total GST liability and ITC. Tax payment must accompany this return.',
    definition_te: 'మొత్తం GST బాధ్యత మరియు ITCని ప్రకటించే నెలవారీ సారాంశ రిటర్న్. ఈ రిటర్న్ తో పాటు పన్ను చెల్లింపు తప్పనిసరి.',
  },
  // Capital gains
  {
    id: 'stcg', english: 'STCG (Short-Term Capital Gains)', telugu: 'స్వల్పకాలిక మూలధన లాభాలు (STCG)',
    category: 'capital_gains',
    definition_en: 'Profit from selling assets held for less than the qualifying period (12 months for equity, 24 months for property).',
    definition_te: 'అర్హత వ్యవధి కంటే తక్కువ కాలం (ఈక్విటీకి 12 నెలలు, ఆస్తికి 24 నెలలు) నిర్వహించిన ఆస్తులను విక్రయించడం ద్వారా వచ్చే లాభం.',
  },
  {
    id: 'ltcg', english: 'LTCG (Long-Term Capital Gains)', telugu: 'దీర్ఘకాలిక మూలధన లాభాలు (LTCG)',
    category: 'capital_gains',
    definition_en: 'Profit from selling assets held beyond the qualifying period. Taxed at 12.5% for equity (with ₹1.25L exemption) and 12.5% for other assets (post-Budget 2024).',
    definition_te: 'అర్హత వ్యవధి దాటి నిర్వహించిన ఆస్తులను విక్రయించడం ద్వారా వచ్చే లాభం. ఈక్విటీకి 12.5% (రూ.1.25 లక్షల మినహాయింపుతో) మరియు ఇతర ఆస్తులకు 12.5% (2024 బడ్జెట్ తర్వాత) పన్ను విధించబడుతుంది.',
  },
  // EPF / PF
  {
    id: 'epf', english: 'EPF (Employee Provident Fund)', telugu: 'ఉద్యోగి భవిష్యనిధి (EPF)',
    category: 'retirement',
    definition_en: 'Retirement fund where employee and employer each contribute 12% of basic salary. Interest rate ~8.25% p.a.',
    definition_te: 'ఉద్యోగి మరియు యజమాని ఒక్కొక్కరు బేసిక్ జీతంలో 12% చొప్పున సహకరించే పదవీ విరమణ నిధి. వడ్డీ రేటు సుమారు 8.25% వార్షికం.',
  },
  {
    id: 'esic', english: 'ESIC (Employee State Insurance)', telugu: 'ఉద్యోగి రాష్ట్ర బీమా (ESIC)',
    category: 'insurance',
    definition_en: 'Health insurance scheme for employees earning ≤₹21,000/month. Employee pays 0.75%, employer 3.25% of gross wages.',
    definition_te: 'నెలకు రూ.21,000 లోపు సంపాదించే ఉద్యోగులకు ఆరోగ్య బీమా పథకం. ఉద్యోగి స్థూల వేతనంలో 0.75%, యజమాని 3.25% చెల్లిస్తారు.',
  },
];

export function searchGlossary(query: string, locale: 'en' | 'te' = 'en'): GlossaryTerm[] {
  const q = query.toLowerCase();
  return GLOSSARY.filter(term => {
    if (locale === 'te') {
      return term.telugu.includes(q) ||
             term.definition_te.includes(q) ||
             term.english.toLowerCase().includes(q);
    }
    return term.english.toLowerCase().includes(q) ||
           term.definition_en.toLowerCase().includes(q) ||
           term.category.includes(q);
  });
}

export function getTermsByCategory(category: string): GlossaryTerm[] {
  return GLOSSARY.filter(t => t.category === category);
}

export const GLOSSARY_CATEGORIES = [
  { id: 'income_tax',    label_en: 'Income Tax',    label_te: 'ఆదాయపు పన్ను' },
  { id: 'deductions',    label_en: 'Deductions',    label_te: 'తగ్గింపులు' },
  { id: 'gst',           label_en: 'GST',           label_te: 'GST' },
  { id: 'capital_gains', label_en: 'Capital Gains', label_te: 'మూలధన లాభాలు' },
  { id: 'savings',       label_en: 'Savings',       label_te: 'పొదుపు' },
  { id: 'investments',   label_en: 'Investments',   label_te: 'పెట్టుబడులు' },
  { id: 'retirement',    label_en: 'Retirement',    label_te: 'పదవీ విరమణ' },
  { id: 'insurance',     label_en: 'Insurance',     label_te: 'బీమా' },
  { id: 'allowances',    label_en: 'Allowances',    label_te: 'భత్యాలు' },
];
