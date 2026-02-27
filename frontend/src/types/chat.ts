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
}
