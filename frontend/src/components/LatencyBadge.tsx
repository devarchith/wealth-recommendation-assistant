'use client';

interface LatencyBadgeProps {
  latencyMs: number;
}

/**
 * Displays the ML service response time.
 * Color-coded: green (<= 800ms target), yellow (<= 1500ms), red (> 1500ms).
 */
export default function LatencyBadge({ latencyMs }: LatencyBadgeProps) {
  const label = latencyMs < 1000
    ? `${Math.round(latencyMs)}ms`
    : `${(latencyMs / 1000).toFixed(1)}s`;

  const colorClass =
    latencyMs <= 800
      ? 'text-green-600 dark:text-green-400'
      : latencyMs <= 1500
      ? 'text-yellow-600 dark:text-yellow-400'
      : 'text-red-600 dark:text-red-400';

  return (
    <span
      className={`flex items-center gap-1 text-xs ${colorClass}`}
      title={`ML service latency: ${label}`}
    >
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
          d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
      {label}
    </span>
  );
}
