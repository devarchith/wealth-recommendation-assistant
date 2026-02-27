/**
 * Streaming client for the /api/chat endpoint.
 *
 * The API gateway is configured to support Server-Sent Events (SSE).
 * This client reads the event stream and calls the onToken callback
 * for each chunk as it arrives, enabling a real-time "typewriter" effect.
 *
 * Falls back to a standard JSON response if the server does not send
 * a stream (e.g., during testing or when the ML service is slow).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export interface StreamEvent {
  type: 'token' | 'sources' | 'done' | 'error';
  data: string;
}

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onSources: (sources: unknown[]) => void;
  onDone: (latencyMs: number, messageId: string) => void;
  onError: (error: string) => void;
}

/**
 * Send a chat message and stream the response token-by-token.
 *
 * Uses the Fetch API with ReadableStream to parse SSE events line-by-line.
 * Each `data:` line is parsed as JSON with a `type` discriminator.
 */
export async function streamChatMessage(
  message: string,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    credentials: 'include',
    signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Request failed' }));
    callbacks.onError(err.error || `HTTP ${response.status}`);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError('Streaming not supported by this environment');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data:')) continue;
      const raw = line.slice(5).trim();
      if (!raw || raw === '[DONE]') continue;

      try {
        const event: StreamEvent = JSON.parse(raw);
        switch (event.type) {
          case 'token':
            callbacks.onToken(event.data);
            break;
          case 'sources':
            callbacks.onSources(JSON.parse(event.data));
            break;
          case 'done': {
            const meta = JSON.parse(event.data);
            callbacks.onDone(meta.latency_ms, meta.message_id);
            break;
          }
          case 'error':
            callbacks.onError(event.data);
            break;
        }
      } catch {
        // Skip malformed SSE lines
      }
    }
  }
}

/**
 * Non-streaming fallback — returns a single JSON response.
 * Used when SSE is not available or for simpler environments.
 */
export async function fetchChatMessage(message: string): Promise<{
  answer: string;
  sources: unknown[];
  latency_ms: number;
  message_id: string;
}> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
    credentials: 'include',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  return res.json();
}
