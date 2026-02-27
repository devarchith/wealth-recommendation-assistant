'use client';

import { useState } from 'react';
import clsx from 'clsx';
import dynamic from 'next/dynamic';

const BudgetTab     = dynamic(() => import('./BudgetTab'),     { ssr: false });
const InvestmentTab = dynamic(() => import('./InvestmentTab'), { ssr: false });
const TaxTab        = dynamic(() => import('./TaxTab'),        { ssr: false });

type Tab = 'chat' | 'budget' | 'investment' | 'tax';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'chat',       label: 'AI Chat',     icon: '💬' },
  { id: 'budget',     label: 'Budget',      icon: '📊' },
  { id: 'investment', label: 'Invest',      icon: '📈' },
  { id: 'tax',        label: 'Tax',         icon: '🧾' },
];

interface TabBarProps {
  chatContent: React.ReactNode;
}

/**
 * Top-level tab navigation bar.
 * Renders the AI Chat, Budget Management, Investment Recommendations,
 * and Tax Assistance panels as described in paper §4.
 */
export default function TabBar({ chatContent }: TabBarProps) {
  const [activeTab, setActiveTab] = useState<Tab>('chat');

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Tab row */}
      <div className="flex border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex-shrink-0">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
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
        {/* Chat tab: overflow is handled inside chatContent (MessageList scrolls) */}
        {activeTab === 'chat' && (
          <div className="flex-1 overflow-hidden flex flex-col max-w-4xl w-full mx-auto px-4 pb-4">
            {chatContent}
          </div>
        )}

        {/* Non-chat tabs: this container scrolls the tab content */}
        {activeTab !== 'chat' && (
          <div className="flex-1 overflow-y-auto chat-scroll">
            <div className="max-w-4xl mx-auto px-4 py-4">
              {activeTab === 'budget'     && <BudgetTab />}
              {activeTab === 'investment' && <InvestmentTab />}
              {activeTab === 'tax'        && <TaxTab />}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
