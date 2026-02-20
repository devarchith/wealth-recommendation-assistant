'use client';

import { useState, useEffect } from 'react';
import clsx from 'clsx';
import dynamic from 'next/dynamic';

const BudgetTab     = dynamic(() => import('./BudgetTab'),     { ssr: false });
const InvestmentTab = dynamic(() => import('./InvestmentTab'), { ssr: false });
const TaxTab        = dynamic(() => import('./TaxTab'),        { ssr: false });
const IndiaTaxTab   = dynamic(() => import('./IndiaTaxTab'),   { ssr: false });
const BusinessTab   = dynamic(() => import('./BusinessTab'),   { ssr: false });
const CAPortalTab   = dynamic(() => import('./CAPortalTab'),   { ssr: false });
const RiceMillTab   = dynamic(() => import('./RiceMillTab'),   { ssr: false });
const PricingTab    = dynamic(() => import('./PricingTab'),    { ssr: false });
const PrivacyTab    = dynamic(() => import('./PrivacyTab'),    { ssr: false });

type Tab = 'chat' | 'budget' | 'investment' | 'tax' | 'india-tax' | 'business' | 'ca' | 'ricemill' | 'pricing' | 'privacy';

/** All tabs, in display order */
const ALL_TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'chat',       label: 'AI Chat',    icon: '💬' },
  { id: 'budget',     label: 'Budget',     icon: '📊' },
  { id: 'investment', label: 'Invest',     icon: '📈' },
  { id: 'tax',        label: 'US Tax',     icon: '🧾' },
  { id: 'india-tax',  label: 'India Tax',  icon: '🇮🇳' },
  { id: 'business',   label: 'Business',   icon: '🏪' },
  { id: 'ca',         label: 'CA Portal',  icon: '⚖️' },
  { id: 'ricemill',   label: 'Rice Mill',  icon: '🌾' },
  { id: 'pricing',    label: 'Pricing',    icon: '💎' },
  { id: 'privacy',    label: 'Privacy',    icon: '🔒' },
];

interface TabBarProps {
  chatContent: React.ReactNode;
  /**
   * Subset of tab IDs to show for the active user role.
   * When omitted, all tabs are shown (backwards-compatible).
   */
  visibleTabs?: string[];
  /**
   * Tab to activate initially (role-specific default).
   * Defaults to 'chat'.
   */
  defaultTab?: string;
}

/**
 * Top-level tab navigation bar.
 * Filters visible tabs per user role — CAs see CA Portal by default,
 * Rice Mill owners see Rice Mill, etc. Unused modules are hidden to
 * reduce cognitive overload and feature sprawl.
 */
export default function TabBar({ chatContent, visibleTabs, defaultTab }: TabBarProps) {
  const tabs = visibleTabs && visibleTabs.length > 0
    ? ALL_TABS.filter(t => visibleTabs.includes(t.id))
    : ALL_TABS;

  const resolvedDefault = (defaultTab && tabs.find(t => t.id === defaultTab))
    ? (defaultTab as Tab)
    : (tabs[0]?.id ?? 'chat');

  const [activeTab, setActiveTab] = useState<Tab>(resolvedDefault);

  // When role changes (visibleTabs changes), switch to the new role's default tab
  useEffect(() => {
    if (!tabs.find(t => t.id === activeTab)) {
      setActiveTab(resolvedDefault);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleTabs?.join(',')]);

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Tab row — scrollable on small screens */}
      <div className="flex overflow-x-auto border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex-shrink-0 scrollbar-none">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap shrink-0',
              activeTab === tab.id
                ? 'border-brand-600 text-brand-600 dark:text-brand-400 dark:border-brand-400'
                : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:border-slate-300 dark:hover:border-slate-600'
            )}
          >
            <span className="text-base">{tab.icon}</span>
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden flex flex-col">
        {activeTab === 'chat' && (
          <div className="flex-1 overflow-hidden flex flex-col max-w-4xl w-full mx-auto px-4 pb-4">
            {chatContent}
          </div>
        )}

        {activeTab !== 'chat' && (
          <div className="flex-1 overflow-y-auto chat-scroll">
            <div className="max-w-4xl mx-auto px-4 py-4">
              {activeTab === 'budget'     && <BudgetTab />}
              {activeTab === 'investment' && <InvestmentTab />}
              {activeTab === 'tax'        && <TaxTab />}
              {activeTab === 'india-tax'  && <IndiaTaxTab />}
              {activeTab === 'business'   && <BusinessTab />}
              {activeTab === 'ca'         && <CAPortalTab />}
              {activeTab === 'ricemill'   && <RiceMillTab />}
              {activeTab === 'pricing'    && <PricingTab />}
              {activeTab === 'privacy'    && <PrivacyTab />}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
