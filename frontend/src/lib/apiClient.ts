/**
 * API Client
 * Typed HTTP client for all API gateway endpoints.
 * Uses NEXT_PUBLIC_API_URL from the environment (defaults to localhost:3001).
 */

import { ApiChatResponse, Source } from '@/types/chat';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
};

// ── Core fetch wrapper ────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    credentials: 'include', // Send session cookies cross-origin
    headers: {
      ...DEFAULT_HEADERS,
      ...options.headers,
    },
  });

  if (!res.ok) {
    let message = `API error ${res.status}`;
    try {
      const body = await res.json();
      message = body.error || message;
    } catch { /* ignore parse error */ }
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

// ── Endpoint functions ─────────────────────────────────────────────────────

/**
 * POST /api/chat — send a message and get the full AI response.
 */
export async function sendMessage(message: string): Promise<ApiChatResponse> {
  return apiFetch<ApiChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message }),
  });
}

/**
 * GET /api/history — fetch conversation history for the current session.
 */
export async function getHistory(): Promise<{ messages: unknown[]; session_id: string | null }> {
  return apiFetch('/api/history');
}

/**
 * DELETE /api/session — clear conversation history and destroy session.
 */
export async function clearSession(): Promise<{ cleared: boolean }> {
  return apiFetch('/api/session', { method: 'DELETE' });
}

/**
 * POST /api/feedback — record thumbs-up or thumbs-down rating.
 * Contributes to the 33% user satisfaction improvement metric.
 */
export async function sendFeedback(
  messageId: string,
  rating: 'up' | 'down'
): Promise<{ recorded: boolean }> {
  return apiFetch('/api/feedback', {
    method: 'POST',
    body: JSON.stringify({ message_id: messageId, rating }),
  });
}

/**
 * GET /api/health — check API gateway liveness.
 */
export async function healthCheck(): Promise<{
  status: string;
  activeSessions: number;
}> {
  return apiFetch('/api/health');
}

// ── Type helpers ───────────────────────────────────────────────────────────

export type { ApiChatResponse, Source };
