/**
 * Bilingual i18n — English / Telugu (తెలుగు)
 * Financial terminology glossary and UI string translations.
 */

export type Locale = 'en' | 'te';

export interface TranslationMap {
  // Navigation
  aiChat:         string;
  budget:         string;
  invest:         string;
  usTax:          string;
  indiaTax:       string;
  business:       string;
  caPortal:       string;
  // Common actions
  send:           string;
  clear:          string;
  save:           string;
  cancel:         string;
  calculate:      string;
  reset:          string;
  submit:         string;
  // Financial terms
  income:         string;
  expense:        string;
  tax:            string;
  deduction:      string;
  refund:         string;
  taxPayable:     string;
  grossIncome:    string;
  netIncome:      string;
  capitalGains:   string;
  investment:     string;
  savings:        string;
  insurance:      string;
  loan:           string;
  interest:       string;
  emi:            string;
  salary:         string;
  // Indian tax specific
  newRegime:      string;
  oldRegime:      string;
  advanceTax:     string;
  tds:            string;
  itr:            string;
  gst:            string;
  pan:            string;
  aadhaar:        string;
  // UI messages
  welcome:        string;
  askQuestion:    string;
  loading:        string;
  errorOccurred:  string;
  typingIndicator: string;
  feedbackThanks: string;
}

const translations: Record<Locale, TranslationMap> = {
  en: {
    aiChat:          'AI Chat',
    budget:          'Budget',
    invest:          'Invest',
    usTax:           'US Tax',
    indiaTax:        'India Tax',
    business:        'Business',
    caPortal:        'CA Portal',
    send:            'Send',
    clear:           'Clear',
    save:            'Save',
    cancel:          'Cancel',
    calculate:       'Calculate',
    reset:           'Reset',
    submit:          'Submit',
    income:          'Income',
    expense:         'Expense',
    tax:             'Tax',
    deduction:       'Deduction',
    refund:          'Refund',
    taxPayable:      'Tax Payable',
    grossIncome:     'Gross Income',
    netIncome:       'Net Income',
    capitalGains:    'Capital Gains',
    investment:      'Investment',
    savings:         'Savings',
    insurance:       'Insurance',
    loan:            'Loan',
    interest:        'Interest',
    emi:             'EMI',
    salary:          'Salary',
    newRegime:       'New Regime',
    oldRegime:       'Old Regime',
    advanceTax:      'Advance Tax',
    tds:             'TDS',
    itr:             'ITR',
    gst:             'GST',
    pan:             'PAN',
    aadhaar:         'Aadhaar',
    welcome:         "Hello! I'm WealthAdvisor AI, your personal finance assistant.",
    askQuestion:     'Ask a financial question...',
    loading:         'Loading...',
    errorOccurred:   'An error occurred. Please try again.',
    typingIndicator: 'WealthAdvisor is typing...',
    feedbackThanks:  'Thank you for your feedback!',
  },

  te: {
    aiChat:          'AI చాట్',
    budget:          'బడ్జెట్',
    invest:          'పెట్టుబడి',
    usTax:           'US పన్ను',
    indiaTax:        'భారత పన్ను',
    business:        'వ్యాపారం',
    caPortal:        'CA పోర్టల్',
    send:            'పంపు',
    clear:           'క్లియర్',
    save:            'సేవ్ చేయి',
    cancel:          'రద్దు చేయి',
    calculate:       'లెక్కించు',
    reset:           'రీసెట్',
    submit:          'సమర్పించు',
    income:          'ఆదాయం',
    expense:         'వ్యయం',
    tax:             'పన్ను',
    deduction:       'తగ్గింపు',
    refund:          'వాపసు',
    taxPayable:      'చెల్లించవలసిన పన్ను',
    grossIncome:     'స్థూల ఆదాయం',
    netIncome:       'నికర ఆదాయం',
    capitalGains:    'మూలధన లాభాలు',
    investment:      'పెట్టుబడి',
    savings:         'పొదుపు',
    insurance:       'బీమా',
    loan:            'రుణం',
    interest:        'వడ్డీ',
    emi:             'నెలవారీ వాయిదా (EMI)',
    salary:          'జీతం',
    newRegime:       'కొత్త పద్ధతి',
    oldRegime:       'పాత పద్ధతి',
    advanceTax:      'అడ్వాన్స్ పన్ను',
    tds:             'TDS (మూలంలో పన్ను కోత)',
    itr:             'ITR (ఆదాయపు పన్ను రిటర్న్)',
    gst:             'వస్తు సేవల పన్ను (GST)',
    pan:             'శాశ్వత ఖాతా సంఖ్య (PAN)',
    aadhaar:         'ఆధార్',
    welcome:         'నమస్కారం! నేను WealthAdvisor AI, మీ వ్యక్తిగత ఆర్థిక సహాయకుడు.',
    askQuestion:     'ఆర్థిక ప్రశ్న అడగండి...',
    loading:         'లోడ్ అవుతోంది...',
    errorOccurred:   'లోపం సంభవించింది. దయచేసి మళ్ళీ ప్రయత్నించండి.',
    typingIndicator: 'WealthAdvisor టైప్ చేస్తోంది...',
    feedbackThanks:  'మీ అభిప్రాయానికి ధన్యవాదాలు!',
  },
};

export function t(locale: Locale, key: keyof TranslationMap): string {
  return translations[locale][key] ?? translations['en'][key] ?? key;
}

export function useTranslation(locale: Locale) {
  return {
    t: (key: keyof TranslationMap) => t(locale, key),
    locale,
  };
}

export { translations };
