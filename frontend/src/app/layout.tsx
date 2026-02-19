import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'WealthAdvisor AI — Conversational Finance Assistant',
  description:
    'AI-powered personal finance advisor with RAG-backed financial knowledge, ' +
    'conversational memory, and real-time streaming responses.',
  keywords: ['personal finance', 'AI advisor', 'budgeting', 'investing', 'retirement'],
  authors: [{ name: 'Devarchith Parashara Batchu' }],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
