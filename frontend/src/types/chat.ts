export type Role = 'user' | 'assistant';

export interface Source {
  title: string;
  category: string;
  source: string;
  snippet: string;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  sources?: Source[];
  latency_ms?: number;
  timestamp: string;
  feedback?: 'up' | 'down' | null;
  isStreaming?: boolean;
  /** Confidence score 0–100 from ML pipeline (optional, assistant only) */
  confidence?: number;
  /** Regulation or section cited by the AI, e.g. "Sec 80C IT Act" (optional) */
  regulation_ref?: string;
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  sessionId: string | null;
  error: string | null;
}

export interface ApiChatResponse {
  answer: string;
  sources: Source[];
  latency_ms: number;
  gateway_latency_ms: number;
  session_id: string;
  message_id: string;
  /** Confidence score 0–100 returned by ML service */
  confidence?: number;
  /** Regulation or section cited, e.g. "Sec 80C IT Act 1961" */
  regulation_ref?: string;
}
